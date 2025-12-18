import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정 및 한글 폰트 CSS 주입
st.set_page_config(page_title="🌱 극지식물 최적 EC 농도 연구", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# Plotly 기본 폰트 설정
PLOTLY_FONT = dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# 2. 데이터 로딩 함수 (NFC/NFD 호환 및 캐싱)
@st.cache_data
def load_data():
    data_path = Path("data")
    if not data_path.exists():
        st.error(f"❌ '{data_path}' 디렉토리가 존재하지 않습니다.")
        return None, None

    env_dfs = {}
    growth_df_dict = {}
    
    # 학교별 설정 정보
    school_info = {
        "송도고": {"ec_target": 1.0, "color": "#AB63FA"},
        "하늘고": {"ec_target": 2.0, "color": "#EF553B"}, # 최적
        "아라고": {"ec_target": 4.0, "color": "#00CC96"},
        "동산고": {"ec_target": 8.0, "color": "#636EFA"}
    }

    # 파일 목록 정규화 및 로드
    files = list(data_path.iterdir())
    
    # 환경 데이터 (CSV) 로드
    for school_name in school_info.keys():
        target_nfc = unicodedata.normalize("NFC", f"{school_name}_환경데이터.csv")
        target_nfd = unicodedata.normalize("NFD", f"{school_name}_환경데이터.csv")
        
        match = next((f for f in files if f.name == target_nfc or f.name == target_nfd), None)
        
        if match:
            df = pd.read_csv(match)
            df['time'] = pd.to_datetime(df['time'])
            df['school'] = school_name
            env_dfs[school_name] = df

    # 생육 데이터 (XLSX) 로드
    xlsx_target_nfc = unicodedata.normalize("NFC", "4개교_생육결과데이터.xlsx")
    xlsx_target_nfd = unicodedata.normalize("NFD", "4개교_생육결과데이터.xlsx")
    xlsx_match = next((f for f in files if f.name == xlsx_target_nfc or f.name == xlsx_target_nfd), None)

    if xlsx_match:
        xls = pd.ExcelFile(xlsx_match)
        # 시트명 정규화 비교
        for sheet_name in xls.sheet_names:
            norm_sheet = unicodedata.normalize("NFC", sheet_name)
            for school_name in school_info.keys():
                if school_name in norm_sheet:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    df['school'] = school_name
                    df['ec_target'] = school_info[school_name]['ec_target']
                    growth_df_dict[school_name] = df
    
    return env_dfs, growth_df_dict, school_info

# 데이터 불러오기 수행
with st.spinner('데이터를 불러오는 중입니다...'):
    env_data, growth_data, school_config = load_data()

if not env_data or not growth_data:
    st.stop()

# 전역 데이터 병합
all_growth_df = pd.concat(growth_data.values(), ignore_index=True)

# 3. 사이드바
st.sidebar.header("📍 필터링")
selected_school = st.sidebar.selectbox(
    "비교할 학교 선택",
    ["전체", "송도고", "하늘고", "아라고", "동산고"]
)

st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")

# 4. 탭 구성
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# --- Tab 1: 실험 개요 ---
with tab1:
    st.subheader("연구 배경 및 목적")
    st.info("본 연구는 극지 식물의 생장 효율을 극대화하기 위한 최적의 양액 EC(전기전도도) 농도를 분석합니다. 4개 고등학교와의 협업을 통해 각기 다른 EC 조건에서 식물을 재배하였습니다.")
    
    col1, col2 = st.columns([2, 3])
    with col1:
        st.markdown("### 학교별 실험 조건")
        cond_data = []
        for name, info in school_config.items():
            count = len(growth_data[name]) if name in growth_data else 0
            cond_data.append({"학교명": name, "EC 목표": info['ec_target'], "개체수": count, "색상": info['color']})
        st.table(pd.DataFrame(cond_data))

    with col2:
        st.markdown("### 주요 지표")
        m1, m2 = st.columns(2)
        m3, m4 = st.columns(2)
        
        avg_temp = pd.concat(env_data.values())['temperature'].mean()
        avg_hum = pd.concat(env_data.values())['humidity'].mean()
        
        m1.metric("총 개체수", f"{len(all_growth_df)} 개")
        m2.metric("평균 온도", f"{avg_temp:.1f} °C")
        m3.metric("평균 습도", f"{avg_hum:.1f} %")
        m4.metric("최적 EC 농도", "2.0 (하늘고)", delta="Best", delta_color="normal")

# --- Tab 2: 환경 데이터 ---
with tab2:
    st.subheader("학교별 환경 지표 비교")
    
    # 2x2 서브플롯 생성
    fig_env = make_subplots(
        rows=2, cols=2,
        subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC")
    )

    env_stats = []
    for school, df in env_data.items():
        env_stats.append({
            'School': school,
            'Temp': df['temperature'].mean(),
            'Hum': df['humidity'].mean(),
            'pH': df['ph'].mean(),
            'EC_Actual': df['ec'].mean(),
            'EC_Target': school_config[school]['ec_target']
        })
    stat_df = pd.DataFrame(env_stats)

    fig_env.add_trace(go.Bar(x=stat_df['School'], y=stat_df['Temp'], name='온도', marker_color='#FFA15A'), row=1, col=1)
    fig_env.add_trace(go.Bar(x=stat_df['School'], y=stat_df['Hum'], name='습도', marker_color='#19D3F3'), row=1, col=2)
    fig_env.add_trace(go.Bar(x=stat_df['School'], y=stat_df['pH'], name='pH', marker_color='#FECB52'), row=2, col=1)
    
    fig_env.add_trace(go.Bar(x=stat_df['School'], y=stat_df['EC_Target'], name='목표 EC', marker_color='lightgray'), row=2, col=2)
    fig_env.add_trace(go.Bar(x=stat_df['School'], y=stat_df['EC_Actual'], name='실측 EC', marker_color='#EF553B'), row=2, col=2)

    fig_env.update_layout(height=600, font=PLOTLY_FONT, showlegend=False, barmode='group')
    st.plotly_chart(fig_env, use_container_width=True)

    # 시계열 차트
    st.divider()
    school_to_plot = selected_school if selected_school != "전체" else "하늘고"
    st.subheader(f"📈 {school_to_plot} 시계열 상세 분석")
    
    target_df = env_data[school_to_plot]
    
    fig_line = make_subplots(specs=[[{"secondary_y": True}]])
    fig_line.add_trace(go.Scatter(x=target_df['time'], y=target_df['temperature'], name="온도(°C)"), secondary_y=False)
    fig_line.add_trace(go.Scatter(x=target_df['time'], y=target_df['humidity'], name="습도(%)", line=dict(dash='dot')), secondary_y=True)
    fig_line.update_layout(title=f"{school_to_plot} 온/습도 변화", font=PLOTLY_FONT)
    st.plotly_chart(fig_line, use_container_width=True)

    fig_ec = px.line(target_df, x='time', y='ec', title=f"{school_to_plot} EC 실측 변화")
    fig_ec.add_hline(y=school_config[school_to_plot]['ec_target'], line_dash="dash", line_color="red", annotation_text="목표 EC")
    fig_ec.update_layout(font=PLOTLY_FONT)
    st.plotly_chart(fig_ec, use_container_width=True)

    with st.expander("📥 환경 데이터 원본 보기 및 다운로드"):
        st.dataframe(target_df)
        csv = target_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("CSV 다운로드", data=csv, file_name=f"{school_to_plot}_env_data.csv", mime='text/csv')

# --- Tab 3: 생육 결과 ---
with tab3:
    st.subheader("EC 농도별 생육 성과 비교")
    
    # 핵심 결과 카드
    best_school = "하늘고" # 시나리오 상 최적
    avg_weight_best = growth_data[best_school]['생중량(g)'].mean()
    
    st.success(f"🥇 최적 조건 도출: **{best_school} (EC {school_config[best_school]['ec_target']})**에서 평균 생중량 **{avg_weight_best:.2f}g**으로 가장 우수한 성장을 보임")

    # 2x2 생육 비교
    growth_agg = all_growth_df.groupby('school').mean(numeric_only=True).reset_index()
    # EC 순서대로 정렬
    growth_agg['ec_val'] = growth_agg['school'].map(lambda x: school_config[x]['ec_target'])
    growth_agg = growth_agg.sort_values('ec_val')

    fig_growth = make_subplots(rows=2, cols=2, subplot_titles=("평균 생중량 (g) ⭐", "평균 잎 수 (장)", "평균 지상부 길이 (mm)", "학교별 개체수 (N)"))
    
    colors = ['#EF553B' if s == '하늘고' else '#636EFA' for s in growth_agg['school']]

    fig_growth.add_trace(go.Bar(x=growth_agg['school'], y=growth_agg['생중량(g)'], marker_color=colors), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=growth_agg['school'], y=growth_agg['잎 수(장)'], marker_color='#00CC96'), row=1, col=2)
    fig_growth.add_trace(go.Bar(x=growth_agg['school'], y=growth_agg['지상부 길이(mm)'], marker_color='#AB63FA'), row=2, col=1)
    
    counts = all_growth_df['school'].value_counts().reindex(growth_agg['school'])
    fig_growth.add_trace(go.Bar(x=counts.index, y=counts.values, marker_color='#FFA15A'), row=2, col=2)

    fig_growth.update_layout(height=700, font=PLOTLY_FONT, showlegend=False)
    st.plotly_chart(fig_growth, use_container_width=True)

    # 분포 및 상관관계
    col_a, col_b = st.columns(2)
    with col_a:
        fig_box = px.box(all_growth_df, x="school", y="생중량(g)", color="school", title="학교별 생중량 분포")
        fig_box.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig_box, use_container_width=True)
    
    with col_b:
        fig_scatter = px.scatter(all_growth_df, x="지상부 길이(mm)", y="생중량(g)", color="school", title="지상부 길이 vs 생중량 상관관계")
        fig_scatter.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig_scatter, use_container_width=True)

    with st.expander("📥 생육 데이터 원본 보기 및 다운로드"):
        display_df = all_growth_df if selected_school == "전체" else growth_data[selected_school]
        st.dataframe(display_df)
        
        # XLSX 다운로드 로직 (BytesIO 필수 사용)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            display_df.to_excel(writer, index=False, sheet_name="Growth_Data")
        
        st.download_button(
            label="Excel (.xlsx) 다운로드",
            data=buffer.getvalue(),
            file_name=f"Growth_Result_{selected_school}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
