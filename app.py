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
    raise FileNotFoundError("데이터 파일을 찾을 수 없습니다. 'score.csv' 파일이 폴더에 있는지 확인해주세요.")

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
        
        # 2. 지도의 중심점 계산 및 맵 생성 (모바일 스크롤 쾌적화)
        center_lat, center_lon = merged.geometry.centroid.y.mean(), merged.geometry.centroid.x.mean()
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=11.3,         
            tiles="CartoDB positron",
            dragging=True,
            scrollWheelZoom=True,   
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
                st.markdown(f"### **종합 위험도 {int(dong_data['위험도 순위'])}위** (상위 점수: {dong_data['최종 보행 위험도 점수']}점)")
                
                # =======================================================
                # [안전장치] 컬럼명이 미세하게 달라도 작동하도록 키워드 매핑 함수
                # =======================================================
                def get_val(keyword):
                    for c in dong_data.index:
                        if keyword in c: return dong_data[c]
                    return 0

                # [허점 D 솔루션] 안전 시설은 '부족도'로 역산하여 시각화의 직관성 극대화
                safety_score = get_val('안전 시설')
                safety_lack_score = 100 - safety_score if safety_score > 0 else 0

                # 방사형 차트 8개 카테고리 설정
                categories = [
                    '평균 기울기', 
                    '골목길 비율', 
                    '노인 인구 밀도', 
                    '복지 시설 밀도', 
                    '불법주정차 CCTV', 
                    '보행 장애물 밀도', 
                    '건축물 노후도',
                    '안전 시설 (부족도)' # 직관성을 위한 역산
                ]
                
                values = [
                    get_val('기울기'),
                    get_val('골목길'),
                    get_val('인구'),
                    get_val('시설'),
                    get_val('CCTV'),
                    get_val('적치물'),
                    get_val('연령'),
                    safety_lack_score
                ]
                
                # 마지막 빨간 선분을 연결하기 위해 첫 번째 데이터를 맨 끝에 복사해서 붙임 (도형 닫기)
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
                    paper_bgcolor='rgba(0,0,0,0)',  # 차트 바깥쪽 배경 투명 (#0E1117이 비쳐보임)
                    polar=dict(
                        bgcolor='#1E2127',          # 차트 안쪽 원은 배경보다 살짝 밝은 다크톤으로 구분
                        radialaxis=dict(
                            visible=True, 
                            range=[0, 100],
                            tickvals=[0, 20, 40, 60, 80],   # 0부터 80까지만 표시 (100 제외)
                            showticklabels=True,
                            tickfont=dict(color='#cccccc')  # 어두운 배경에 잘 보이도록 숫자 색상을 밝은 회색으로 변경
                        ),
                        angularaxis=dict(
                            color='white',                  # 항목 이름 글자색을 흰색으로 유지
                            tickfont=dict(size=11)          # 지표 개수가 늘어나 폰트를 살짝 조정
                        )
                    ), 
                    showlegend=False, 
                    margin=dict(l=60, r=60, t=30, b=30), # 라벨이 잘리지 않도록 좌우 여백 확보
                    height=350
                )
                
                # 차트 출력
                st.plotly_chart(fig, use_container_width=True, config={
                    'displayModeBar': False, # 거슬리는 상단 메뉴바 숨김
                    'staticPlot': True       # 차트를 찌그러지지 않는 이미지 모드로 고정
                })
                
                # ==========================================
                # [신규] 8개 지표 기반 맞춤형 처방전 (Custom Policy)
                # ==========================================
                st.markdown("### **💡 맞춤형 정책 제언**")
                
                # 지표별 조건부 출력 (점수가 높은 70점 이상인 것들 위주로 경고)
                if get_val('기울기') >= 70:
                    st.error("🚨 **[지형 한계]** 급경사 구간 열선(발열매트) 및 미끄럼 방지 포장 최우선 검토")
                
                if get_val('골목길') >= 70:
                    st.warning("⚠️ **[보차혼용]** 차량 속도 저감 기법(Traffic Calming) 및 보행자 우선도로 지정 필요")
                    
                if get_val('인구') >= 70 or get_val('시설') >= 70:
                    st.warning("⚠️ **[교통약자 집중]** 노인 보호구역(Silver Zone) 확대 및 보행 신호 시간 연장 추진")

                if get_val('CCTV') >= 70:
                    st.warning("⚠️ **[불법주차 상습]** 불법주정차 단속 강화 및 사각지대 반사경, 시선유도봉 확충")
                    
                if get_val('적치물') >= 70:
                    st.warning("⚠️ **[보행 장애물]** 가로 정비 특별 단속 및 적치물 방지용 스마트 플랜터 설치")
                    
                if get_val('연령') >= 70:
                    st.warning("⚠️ **[환경 노후도]** 셉테드(CPTED) 환경 개선 기법 적용 및 스마트 안심 보안등 설치 요망")
                    
                if safety_score < 30: # 부족도가 아닌 원본 점수 기준으로 측정
                    st.error("🚨 **[안전 인프라 부재]** 야간 조명, 제설함, 보행자 펜스 등 기초 안전 시설 확충 시급")
                
                # 모든 지표가 양호할 경우 (경고 메시지가 하나도 없을 때를 대비)
                if all(get_val(col) < 70 for col in ['기울기', '골목길', '인구', '시설', 'CCTV', '적치물', '연령']) and safety_score >= 50:
                    st.success("✅ **[인프라 양호]** 현재의 보행 안전 인프라 유지보수 집중 및 모니터링")
                    
            else:
                st.warning(f"선택하신 '{clicked_dong}' 데이터가 성적표에 없습니다.")
