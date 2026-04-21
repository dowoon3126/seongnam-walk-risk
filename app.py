import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# 1. 페이지 기본 설정
st.set_page_config(page_title="성남시 보행 위험도 대시보드", page_icon="🚨", layout="wide")
st.header("🚨 성남시 보행 위험도 대시보드 (지도 클릭형)")
st.info("아래 지도에서 동네를 클릭하시면 오른쪽에서 맞춤형 진단서가 켜집니다!")

# 2. 데이터 불러오기 (한글 깨짐 방지)
@st.cache_data
def load_data():
    try:
        return pd.read_csv("score.csv", encoding='utf-8')
    except UnicodeDecodeError:
        return pd.read_csv("score.csv", encoding='euc-kr')

@st.cache_data
def load_map():
    try:
        gdf = gpd.read_file("BND_ADM_DONG_PG.shp", encoding='euc-kr')
    except UnicodeDecodeError:
        gdf = gpd.read_file("BND_ADM_DONG_PG.shp", encoding='utf-8')
    
    # 웹 지도(Folium) 규격에 맞게 좌표계 변환
    if gdf.crs is None:
        gdf.set_crs(epsg=5179, inplace=True)
    gdf = gdf.to_crs(epsg=4326)
    return gdf

df = load_data()
try:
    gdf = load_map()
    map_loaded = True
except Exception as e:
    st.error("⚠️ 'BND_ADM_DONG_PG.shp' 파일과 짝꿍 파일들(.shx, .dbf, .prj)이 같은 폴더에 있는지 확인해주세요!")
    map_loaded = False

if map_loaded:
    # 📌 코랩에서 찾았던 정확한 동네 이름 열(ADM_NM) 고정 적용!
    map_col = 'ADM_NM'
        
    # 지도와 데이터 병합
    merged = gdf.merge(df, left_on=map_col, right_on='행정동', how='inner')
    
    col_map, col_info = st.columns([1.5, 1])
    
    with col_map:
        st.subheader("🗺️ 성남시 인터랙티브 맵")
        center_lat, center_lon = merged.geometry.centroid.y.mean(), merged.geometry.centroid.x.mean()
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=11.3,         
            tiles="CartoDB positron",
            dragging=False,          # ☝️ 맵 이동 금지 (손가락으로 페이지 스크롤이 가능해짐!)
            scrollWheelZoom=False,   # ☝️ 맵 줌 금지
            zoom_control=False       # ☝️ 좌측 상단 +/- 버튼 숨기기 (모바일 화면을 더 넓게)
        )
        
        # 붉은색 단계구분도 칠하기
        with col_map:
            st.subheader("🗺️ 성남시 인터랙티브 맵")
        
        # 1. 폰 화면에 맞춰 자동으로 늘어나는 예쁜 컬러바 그리기 (스트림릿 네이티브)
        st.markdown("""
            <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; color: #555; margin-bottom: 5px;">
                <span>🟢 안전 구역</span>
                <span>🚨 위험 구역</span>
            </div>
            <div style="background: linear-gradient(to right, #fee5d9, #fcae91, #fb6a4a, #de2d26, #a50f15); 
                        height: 12px; border-radius: 10px; margin-bottom: 15px;"></div>
        """, unsafe_allow_html=True)
        
        center_lat, center_lon = merged.geometry.centroid.y.mean(), merged.geometry.centroid.x.mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=11.3, tiles="CartoDB positron", dragging=False, scrollWheelZoom=False, zoom_control=False)
        
        # 2. 지도 색칠하기
        choro = folium.Choropleth(
            geo_data=merged, data=merged,
            columns=['행정동', '최종 보행 위험도 점수'],
            key_on=f'feature.properties.{map_col}',
            fill_color='Reds', fill_opacity=0.7, line_opacity=0.3
        )
        
        # 3. [핵심] 기존에 잘리던 못생긴 기본 범례 강제로 끄기
        for key in list(choro._children.keys()):
            if key.startswith('color_map'):
                del(choro._children[key])
                
        choro.add_to(m)
        
        # 클릭 인식을 위한 투명 레이어
        folium.GeoJson(
            merged,
            style_function=lambda x: {'fillColor': '#000', 'color':'#000', 'fillOpacity': 0.0, 'weight': 0},
            tooltip=folium.features.GeoJsonTooltip(fields=[map_col], aliases=['행정동: ']),
            highlight_function=lambda x: {'weight':3, 'color':'#ff0000', 'fillOpacity': 0.2} 
        ).add_to(m)
        
        map_output = st_folium(m, use_container_width=True, height=350)
        
        # 클릭 인식을 위한 투명 레이어
        folium.GeoJson(
            merged,
            style_function=lambda x: {'fillColor': '#000', 'color':'#000', 'fillOpacity': 0.0, 'weight': 0},
            tooltip=folium.features.GeoJsonTooltip(fields=[map_col], aliases=['행정동: ']),
            highlight_function=lambda x: {'weight':3, 'color':'#ff0000', 'fillOpacity': 0.2} 
        ).add_to(m)
        
        map_output = st_folium(m, use_container_width=True, height=350) 
        
    with col_info:
        clicked_dong = None
        # 클릭 이벤트 감지
        if map_output and map_output.get("last_active_drawing"):
            clicked_dong = map_output["last_active_drawing"]["properties"][map_col]
            
        if clicked_dong:
            match_df = df[df['행정동'] == clicked_dong]
            if len(match_df) > 0:
                dong_data = match_df.iloc[0]
                
                st.subheader(f"📌 [{clicked_dong}] 진단서")
                st.write(f"**종합 위험도 {dong_data['위험도 순위']}위** ({dong_data['최종 보행 위험도 점수']}점)")
                
                # 방사형 차트
                categories = ['평균 기울기(100점)', '골목길 비율(100점)', '교통약자 거주 인구 밀도(100점)', '교통약자 유발 시설 밀도(100점)', '안전 시설 밀도(100점)']
                values = [dong_data[c] for c in categories]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(r=values, theta=categories, fill='toself', fillcolor='rgba(255, 0, 0, 0.2)', line_color='red'))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, margin=dict(l=20, r=20, t=20, b=20), height=300)
                st.plotly_chart(fig, use_container_width=True)
                
                # 맞춤형 처방전 로직
                st.markdown("### 💡 맞춤형 정책 제언")
                if dong_data['안전 시설 밀도(100점)'] < 30:
                    st.error("🚨 **[안전 비상]** 제설함 및 보행자 펜스 확충 시급")
                if dong_data['평균 기울기(100점)'] >= 70:
                    st.warning("⛰️ **[지형 한계]** 열선(발열매트) 설치 우선 검토")
                if dong_data['골목길 비율(100점)'] >= 80:
                    st.warning("⚠️ **[보차혼용]** 미끄럼 방지 포장 및 스마트 보안등 필요")
                if dong_data['안전 시설 밀도(100점)'] >= 50 and dong_data['평균 기울기(100점)'] < 50:
                    st.success("✅ 인프라 양호 구역 (현행 유지보수 집중)")
            else:
                st.warning(f"선택하신 '{clicked_dong}' 데이터가 성적표에 없습니다.")
        else:
            st.info("왼쪽 지도에서 궁금한 동네를 클릭해보세요!")

# python3 -m streamlit run app.py 실행
