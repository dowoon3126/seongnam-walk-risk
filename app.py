import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# 1. 페이지 기본 설정
st.set_page_config(page_title="성남시 보행 위험도 대시보드", layout="wide")
st.header("성남시 보행 위험도 대시보드")
st.info("👇 지도에서 동네를 클릭하고 아래로 스크롤하여 진단서를 확인하세요!")

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
df.columns = df.columns.str.strip()
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
        # 1. 폰 화면에 맞춰 자동으로 늘어나는 예쁜 컬러바 그리기
        st.markdown("""
            <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; color: #555; margin-bottom: 5px;">
                <span>🟢 안전 구역</span>
                <span>🚨 위험 구역</span>
            </div>
            <div style="background: linear-gradient(to right, #fee5d9, #fcae91, #fb6a4a, #de2d26, #a50f15); 
                        height: 12px; border-radius: 10px; margin-bottom: 15px;"></div>
        """, unsafe_allow_html=True)
        
        # 2. 지도의 중심점 계산 및 맵 생성 (모바일 스크롤 쾌적화)
        center_lat, center_lon = merged.geometry.centroid.y.mean(), merged.geometry.centroid.x.mean()
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=11.3,         
            tiles="CartoDB positron",
            dragging=False,          # 🔒 스크롤 방해 금지 (모바일 쾌적)
            scrollWheelZoom=False,   
            zoom_control=True        # 우측 상단 줌 버튼 유지
        )
        
        # 3. 지도 붉은색 칠하기
        choro = folium.Choropleth(
            geo_data=merged, data=merged,
            columns=['행정동', '최종 보행 위험도 점수'],
            key_on=f'feature.properties.{map_col}',
            fill_color='Reds', fill_opacity=0.7, line_opacity=0.3
        )
        
        # 4. 기존 못생긴 범례 강제 제거
        for key in list(choro._children.keys()):
            if key.startswith('color_map'):
                del(choro._children[key])
                
        choro.add_to(m)
        
        # 5. 클릭 인식을 위한 투명 레이어
        folium.GeoJson(
            merged,
            style_function=lambda x: {'fillColor': '#000', 'color':'#000', 'fillOpacity': 0.0, 'weight': 0},
            tooltip=folium.features.GeoJsonTooltip(fields=[map_col], aliases=['행정동: ']),
            highlight_function=lambda x: {'weight':3, 'color':'#ff0000', 'fillOpacity': 0.2} 
        ).add_to(m)
        
        # 6. 화면 출력 (단 한 번만 깔끔하게 실행!)
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
                
                st.subheader(f"[{clicked_dong}] 진단서")
                st.write(f"**종합 위험도 {dong_data['위험도 순위']}위** ({dong_data['최종 보행 위험도 점수']}점)")
                
                # 방사형 차트
                # 1. 💡 줄바꿈 스킬: 데이터 찾는 이름(cols)과 화면에 보여줄 이름(labels)을 분리합니다!
                cols = ['평균 기울기', '골목길 비율', '교통약자 거주 인구 밀도', '교통약자 유발 시설 밀도', '안전 시설 밀도']
                labels = ['평균 기울기', '골목길 비율', '교통약자<br>거주 인구 밀도', '교통약자<br>유발 시설 밀도', '안전 시설 밀도']
                values = [dong_data[c] for c in cols]
                
                fig = go.Figure()
                
                # 2. 💡 라벨링 살리기: mode에 text를 추가하고 글씨색을 진하게(black) 바꿉니다!
                fig.add_trace(go.Scatterpolar(
                    r=values, 
                    theta=labels, 
                    fill='toself', 
                    fillcolor='rgba(255, 0, 0, 0.2)', 
                    line_color='red',
                    mode='lines+markers+text',       # 점과 선, 그리고 텍스트까지 보여줘!
                    text=[f"{v}점" for v in values],   # 숫자 뒤에 '점'을 붙여서 더 친절하게
                    textposition='top center',       # 글자를 점 위쪽에 배치
                    textfont=dict(color='black', size=11, weight='bold') # 까만색 굵은 글씨!
                ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True, 
                            range=[0, 100], 
                            tickfont=dict(color='#999999') # 배경의 0, 20, 40 축 숫자는 연한 회색으로 안 거슬리게
                        ),
                        angularaxis=dict(
                            tickfont=dict(color='black', size=12) # 겉 테두리 카테고리 글자도 까맣고 선명하게
                        )
                    ), 
                    showlegend=False, 
                    margin=dict(l=60, r=60, t=40, b=40), # 줄바꿈을 했으니 좌우 여백을 조금 줄여서 차트를 키워줍니다!
                    height=350
                )
                
                st.plotly_chart(fig, use_container_width=True, config={
                    'displayModeBar': False, 
                    'staticPlot': True       
                })
