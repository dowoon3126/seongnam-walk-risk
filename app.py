import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# 1. 페이지 기본 설정 (와이드 레이아웃 유지)
st.set_page_config(page_title="성남시 보행 위험도 대시보드", layout="wide")

# 강제 다크모드 지정 색상(#0E1117) 설정 및 상단 여백/제목 간격 축소
st.markdown("""
    <style>
    /* 전체 배경을 #0E1117, 텍스트를 흰색으로 강제 고정 */
    .stApp {
        background-color: #0E1117;
        color: #ffffff;
    }
    /* Streamlit 기본 상단 여백 줄이기 */
    .block-container {
        padding-top: 2rem !important;
    }
    /* HTML 요소들 글자색 흰색으로 강제 */
    p, div, span, h1, h2, h3, h4, h5, h6, li {
        color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)

# 제목과 아래 요소 간의 간격(margin) 최소화
st.markdown('<h2 style="margin-top: 0px; margin-bottom: 5px;">성남시 보행 위험도 대시보드</h2>', unsafe_allow_html=True)
st.info("지도 상의 지역을 클릭하시면 하단에 맞춤형 분석 리포트가 생성됩니다.")

# 2. 데이터 불러오기 (한글 깨짐 방지 및 다중 파일명 지원)
@st.cache_data
def load_data():
    # 2차 전처리 후 저장하신 파일명에 맞게 유연하게 불러옵니다.
    filenames = ["score.csv", "성남시_최종보행위험도_성적표_최종.csv", "성남시_최종보행위험도_성적표.csv"]
    for fname in filenames:
        try:
            return pd.read_csv(fname, encoding='utf-8-sig')
        except FileNotFoundError:
            continue
        except UnicodeDecodeError:
            try:
                return pd.read_csv(fname, encoding='euc-kr')
            except Exception:
                continue
    raise FileNotFoundError("데이터 파일을 찾을 수 없습니다. 성적표 CSV 파일이 같은 폴더에 있는지 확인해주세요.")

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

try:
    df = load_data()
    data_loaded = True
except Exception as e:
    st.error(f"데이터 로드 오류: {e}")
    data_loaded = False

try:
    gdf = load_map()
    map_loaded = True
except Exception as e:
    st.error("'BND_ADM_DONG_PG.shp' 파일과 짝꿍 파일들(.shx, .dbf, .prj)이 같은 폴더에 있는지 확인해주세요!")
    map_loaded = False

if data_loaded and map_loaded:
    # 코랩에서 찾았던 정확한 동네 이름 열(ADM_NM) 고정 적용
    map_col = 'ADM_NM'
        
    # 지도와 데이터 병합
    merged = gdf.merge(df, left_on=map_col, right_on='행정동', how='inner')
    
    col_map, col_info = st.columns([1.5, 1])
    
    with col_map:
        # 1. 폰 화면에 맞춰 자동으로 늘어나는 예쁜 컬러바 그리기
        st.markdown("""
            <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; color: #aaaaaa; margin-bottom: 5px;">
                <span>안전 구역</span>
                <span>위험 구역</span>
            </div>
            <div style="background: linear-gradient(to right, #fee5d9, #fcae91, #fb6a4a, #de2d26, #a50f15); 
                        height: 12px; border-radius: 10px; margin-bottom: 15px;"></div>
        """, unsafe_allow_html=True)
        
        # 2. 지도의 중심점 계산 및 맵 생성
        center_lat, center_lon = merged.geometry.centroid.y.mean(), merged.geometry.centroid.x.mean()
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=11.3,         
            tiles="CartoDB positron",
            dragging=True,
            scrollWheelZoom=True,   
            zoom_control=True        
        )
        
        # 3. 지도 붉은색 칠하기
        choro = folium.Choropleth(
            geo_data=merged, data=merged,
            columns=['행정동', '최종 보행 위험도 점수'],
            key_on=f'feature.properties.{map_col}',
            fill_color='Reds', fill_opacity=0.7, line_opacity=0.3
        )
        
        # 4. 기존 범례 강제 제거
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
        
        # 6. 화면 출력
        map_output = st_folium(m, use_container_width=True, height=480)
        
    with col_info:
        clicked_dong = None
        # 클릭 이벤트 감지
        if map_output and map_output.get("last_active_drawing"):
            clicked_dong = map_output["last_active_drawing"]["properties"][map_col]
            
        if clicked_dong:
            match_df = df[df['행정동'] == clicked_dong]
            if len(match_df) > 0:
                dong_data = match_df.iloc[0]
                
                st.subheader(f"[{clicked_dong}] 보행 안전 진단서")
                st.markdown(f"### **종합 위험도 {int(dong_data['위험도 순위'])}위** (위험 점수: {dong_data['최종 보행 위험도 점수']}점)")
                
                # =======================================================
                # [강력 보완] 컬럼명이 달라도 무조건 찾아내는 다중 키워드 매칭 함수
                # =======================================================
                def get_val(keywords):
                    for c in dong_data.index:
                        # 여러 키워드 중 하나라도 컬럼명에 포함되어 있으면 그 값을 가져옵니다.
                        if any(k in c for k in keywords):
                            return float(dong_data[c])
                    return 0.0 # 못 찾으면 0 반환

                # 방어: '시설' 키워드가 중복되지 않도록 안전 시설부터 명확히 추출
                safety_score = get_val(['안전'])
                safety_lack_score = 100 - safety_score if safety_score > 0 else 0

                # 8개 지표 데이터 매핑 (여러 키워드를 배열로 넣어 철벽 방어!)
                values = [
                    get_val(['기울기', '경사']),
                    get_val(['골목길']),
                    get_val(['인구', '거주']),
                    get_val(['유발', '복지시설']),  # '시설' 대신 유발이나 복지 키워드 사용
                    get_val(['CCTV', '주차']),
                    get_val(['적치물', '장애물']),
                    get_val(['연령', '노후', '나이', '건축물']),
                    safety_lack_score
                ]
                
                categories = [
                    '평균 기울기', 
                    '골목길 비율', 
                    '노인 인구 밀도', 
                    '복지 시설 밀도', 
                    '불법주정차 CCTV', 
                    '보행 장애물 밀도', 
                    '건축물 노후도',
                    '안전 시설 (부족도)' 
                ]
                
                # 마지막 선분을 연결하기 위해 첫 번째 데이터를 맨 끝에 복사
                categories_closed = categories + [categories[0]]
                values_closed = values + [values[0]]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=values_closed, 
                    theta=categories_closed, 
                    fill='toself', 
                    fillcolor='rgba(255, 0, 0, 0.2)', 
                    line_color='red'
                ))
                
                # 차트 배경색 설정 및 라벨링 커스텀
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',  
                    polar=dict(
                        bgcolor='#1E2127',          
                        radialaxis=dict(
                            visible=True, 
                            range=[0, 100],
                            tickvals=[0, 20, 40, 60, 80],   
                            showticklabels=True,
                            tickfont=dict(color='#cccccc')  
                        ),
                        angularaxis=dict(
                            color='white',                  
                            tickfont=dict(size=11)          
                        )
                    ), 
                    showlegend=False, 
                    margin=dict(l=60, r=60, t=30, b=30), 
                    height=350
                )
                
                st.plotly_chart(fig, use_container_width=True, config={
                    'displayModeBar': False, 
                    'staticPlot': True       
                })
                
                # ==========================================
                # [신규] 8개 지표 기반 맞춤형 처방전 (Custom Policy)
                # ==========================================
                st.markdown("### **💡 맞춤형 정책 제언**")
                
                # 경고 메시지를 담을 리스트 (70점 이상인 취약 지표 색출)
                warnings = []
                
                if get_val(['기울기', '경사']) >= 70:
                    warnings.append("🚨 **[지형 한계]** 급경사 구간 열선(발열매트) 및 미끄럼 방지 포장 최우선 검토")
                if get_val(['골목길']) >= 70:
                    warnings.append("⚠️ **[보차혼용]** 차량 속도 저감 기법(Traffic Calming) 및 보행자 우선도로 지정 필요")
                if get_val(['인구', '거주']) >= 70 or get_val(['유발', '복지시설']) >= 70:
                    warnings.append("⚠️ **[교통약자 집중]** 노인 보호구역(Silver Zone) 확대 및 보행 신호 시간 연장 추진")
                if get_val(['CCTV', '주차']) >= 70:
                    warnings.append("⚠️ **[불법주차 상습]** 불법주정차 단속 강화 및 사각지대 반사경, 시선유도봉 확충")
                if get_val(['적치물', '장애물']) >= 70:
                    warnings.append("⚠️ **[보행 장애물]** 가로 정비 특별 단속 및 적치물 방지용 스마트 플랜터 설치")
                if get_val(['연령', '노후', '나이', '건축물']) >= 70:
                    warnings.append("⚠️ **[환경 노후도]** 셉테드(CPTED) 환경 개선 기법 적용 및 스마트 안심 보안등 설치 요망")
                if safety_score < 30: 
                    warnings.append("🚨 **[안전 인프라 부재]** 야간 조명, 제설함, 보행자 펜스 등 기초 안전 시설 확충 시급")
                
                # 경고 출력 (해당되는 것만 화면에 뿌림)
                if warnings:
                    for w in warnings:
                        if "🚨" in w:
                            st.error(w)
                        else:
                            st.warning(w)
                else:
                    if safety_score >= 50:
                        st.success("✅ **[인프라 양호]** 현재의 보행 안전 인프라 유지보수 집중 및 모니터링")
                    else:
                        st.info("📊 전반적으로 보통 수준의 보행 환경을 보이고 있습니다.")
                    
            else:
                st.warning(f"선택하신 '{clicked_dong}' 데이터가 성적표에 없습니다.")
