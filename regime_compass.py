"""
레짐 컴파스 (Regime Compass) — 시장 가격으로 보는 경기 기대 체크리스트
실행: streamlit run regime_compass.py
데모(네트워크 없이): REGIME_DEMO=1 streamlit run regime_compass.py

규칙(고정, 튜닝 안 함): 주간(금요일 종가) 기준 13주 변화의 부호만 사용.
  둔화 신호 5개 = 소비비율↓, 규모비율↓, 금/은↑, HY OAS↑, CCC−BB↑
  신용 전이 = CCC−BB 13주Δ와 BB 13주Δ의 부호 조합
참고용 나침반이지 매매 신호가 아님.
"""
import os
import datetime as dt

import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

# ───────────────────────── 설정 ─────────────────────────
SHORT, LONG = 4, 13  # 주

GAUGES = {
    # key: (라벨, 기본 티커쌍, 클린 티커쌍, 둔화 방향)
    "consumer": ("소비 (경기소비재/필수소비재)", ("XLY", "XLP"), ("RSPD", "RSPS"), "down"),
    "size":     ("규모 (소형/대형)",            ("IWM", "SPY"), ("IJR", "SPY"),   "down"),
    "gold_silver": ("금/은",                    ("GC=F", "SI=F"), ("GC=F", "SI=F"), "up"),
}
REF_GAUGES = {  # 표시만, 신호 개수엔 미포함
    "copper_gold": ("구리/금 (참고)", ("HG=F", "GC=F")),
    "ew_cap": ("동일가중/시총가중 (참고)", ("RSP", "SPY")),
}
FRED = {
    "HY": "BAMLH0A0HYM2",   # ICE BofA US High Yield OAS
    "BB": "BAMLH0A1HYBB",   # BB OAS
    "CCC": "BAMLH0A3HYC",   # CCC & Lower OAS
    "IG": "BAMLC0A0CM",     # IG Corporate OAS (참고)
}
DEMO = os.environ.get("REGIME_DEMO") == "1"


# ───────────────────────── 데이터 ─────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(tickers: tuple, start: str) -> pd.DataFrame:
    if DEMO:
        return _demo_frame(list(tickers), start, base=100, vol=0.01)
    import yfinance as yf
    df = yf.download(list(tickers), start=start, auto_adjust=True, progress=False)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(tickers[0])
    return df.dropna(how="all")


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred(series: tuple, start: str) -> pd.DataFrame:
    if DEMO:
        d = _demo_frame(list(series), start, base=4, vol=0.02)
        d[FRED["CCC"]] = d[FRED["CCC"]] * 2.5
        return d
    out = {}
    for sid in series:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        s = pd.read_csv(pd.io.common.StringIO(r.text))
        s.columns = ["date", sid]
        s["date"] = pd.to_datetime(s["date"])
        out[sid] = pd.to_numeric(s.set_index("date")[sid], errors="coerce")
    return pd.DataFrame(out)


def _demo_frame(cols, start, base, vol):
    idx = pd.bdate_range(start, dt.date.today())
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {c: base * np.exp(np.cumsum(rng.normal(0, vol, len(idx)))) for c in cols}, index=idx
    )


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    return df.resample("W-FRI").last()


# ───────────────────────── 계산 ─────────────────────────
def build(prices_w: pd.DataFrame, fred_w: pd.DataFrame, mode: str) -> pd.DataFrame:
    w = pd.DataFrame(index=prices_w.index)
    for k, (_, cap, clean, _) in GAUGES.items():
        a, b = clean if mode == "클린" else cap
        w[k] = prices_w[a] / prices_w[b]
    for k, (_, (a, b)) in REF_GAUGES.items():
        if a in prices_w and b in prices_w:
            w[k] = prices_w[a] / prices_w[b]

    w = w.join(fred_w.rename(columns={v: k for k, v in FRED.items()}), how="left")
    w["CCC_BB"] = (w["CCC"] - w["BB"]) * 100  # bp

    for k in list(GAUGES) + list(REF_GAUGES):
        if k in w:
            w[f"{k}_{SHORT}w"] = w[k].pct_change(SHORT, fill_method=None)
            w[f"{k}_{LONG}w"] = w[k].pct_change(LONG, fill_method=None)
    for k in ["HY", "BB", "CCC", "IG"]:
        if k in w:
            w[f"{k}_{SHORT}w"] = w[k].diff(SHORT) * 100
            w[f"{k}_{LONG}w"] = w[k].diff(LONG) * 100
    w[f"CCC_BB_{LONG}w"] = w["CCC_BB"].diff(LONG)

    sig = pd.DataFrame({
        "consumer": w[f"consumer_{LONG}w"] < 0,
        "size": w[f"size_{LONG}w"] < 0,
        "gold_silver": w[f"gold_silver_{LONG}w"] > 0,
        "HY": w[f"HY_{LONG}w"] > 0,
        "CCC_BB": w[f"CCC_BB_{LONG}w"] > 0,
    })
    needed = [f"consumer_{LONG}w", f"size_{LONG}w", f"gold_silver_{LONG}w", f"HY_{LONG}w", f"CCC_BB_{LONG}w"]
    complete = w[needed].notna().all(axis=1)
    w["signals"] = sig.sum(axis=1).where(complete)

    s, t = w[f"CCC_BB_{LONG}w"], w[f"BB_{LONG}w"]
    state = np.select(
        [(t > 0) & (s > 0), (t > 0) & (s <= 0), (t <= 0) & (s > 0)],
        ["전이 경보", "전반 확대", "하위층 국지"], default="평온")
    w["transfer"] = pd.Series(state, index=w.index).where(s.notna() & t.notna())
    return w


from compass_ui import *  # noqa: E402,F401,F403


# ───────────────────────── UI ─────────────────────────
def render_cross_asset():
    with st.sidebar:
        st.markdown("### 🐤 설정")
        start = st.date_input("데이터 시작", dt.date(2015, 1, 1)).isoformat()
        mode = st.radio("비율 버전", ["클린", "기본"], horizontal=True, help=(
            "클린: RSPD/RSPS(동일가중 소비), IJR/SPY(흑자요건 소형주)\n"
            "기본: XLY/XLP, IWM/SPY — 시총 집중·적자 소형주 효과가 섞임"))
        if st.button("🔄 데이터 새로고침", width="stretch"):
            st.cache_data.clear()
        st.caption(f"규칙 고정: {LONG}주 변화 부호, 보조 {SHORT}주. 임계치 튜닝 없음.")
        if DEMO:
            st.warning("데모 모드 (가짜 데이터)")

    tickers = sorted({t for _, cap, clean, _ in GAUGES.values() for t in cap + clean}
                     | {t for _, pair in REF_GAUGES.values() for t in pair})
    with st.spinner("데이터 불러오는 중…"):
        try:
            px = load_prices(tuple(tickers), start)
        except Exception as e:
            st.error(f"가격 데이터 실패: {e}")
            return
        try:
            fr = load_fred(tuple(FRED.values()), start)
        except Exception as e:
            st.error(f"FRED 실패: {e}")
            return

    missing = [t for t in tickers if t not in px or px[t].dropna().empty]
    if missing:
        st.warning(f"가격 없음: {', '.join(missing)}")

    W = build(to_weekly(px), to_weekly(fr), mode)
    W = W[W.index <= pd.Timestamp.today() + pd.offsets.Week(weekday=4)]
    last = W.dropna(subset=["signals"]).iloc[-1] if W["signals"].notna().any() else W.iloc[-1]
    last_date = last.name.date()
    partial = last.name.date() > dt.date.today()


    # ───────── 헤더 ─────────
    _n = last["signals"]
    mood = "none" if pd.isna(_n) else "good" if _n <= 1 else "warn" if _n <= 3 else "bad"
    MOOD_TIP = {"good": "레몬이 신났어요 · 안정", "warn": "레몬이 갸우뚱 · 주의", "bad": "레몬이 걱정 중 · 경계", "none": "데이터 부족"}
    price_last = px.dropna(how="all").index.max().date()
    fred_last = fr.dropna(how="all").index.max().date()
    st.markdown(f"""
    <div class="hero">
      <div>
        <h1><span class="lemon-icon">🍋</span> 레짐 컴파스</h1>
        <p>시장 가격으로 보는 경기 기대 체크리스트 · 참고용 나침반이지 매매 신호가 아닙니다</p>
      </div>
      <div class="chips">
        <span class="chip live">📅 기준 주 <b>{last_date}</b>{' · 진행 중' if partial else ''}</span>
        <span class="chip">가격 최신 <b>{price_last}</b></span>
        <span class="chip">FRED 최신 <b>{fred_last}</b></span>
        <span class="chip">비율 <b>{mode}</b></span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ───────── 요약 ─────────
    n = last["signals"]
    sig_now = {
        "소비": last[f"consumer_{LONG}w"] < 0,
        "규모": last[f"size_{LONG}w"] < 0,
        "금/은": last[f"gold_silver_{LONG}w"] > 0,
        "HY": last[f"HY_{LONG}w"] > 0,
        "CCC−BB": last[f"CCC_BB_{LONG}w"] > 0,
    }
    if pd.isna(n):
        lvl_color, lvl_text, n_txt, lit = MUTED, "데이터 부족", "—", 0
    else:
        lit = int(n)
        lvl_color, lvl_text = ((GOOD, "안정") if lit <= 1 else (WARN, "주의") if lit <= 3 else (BAD, "경계"))
        n_txt = str(lit)
    meter = "".join(f'<span style="background:{lvl_color if i < lit else "#F3ECD6"}"></span>' for i in range(5))
    chips = "".join(f'<span class="sigchip{" on" if v else ""}">{k}</span>' for k, v in sig_now.items())

    state = last["transfer"] if isinstance(last["transfer"], str) else "—"
    STATE_INFO = {
        "평온": (GOOD, "BB도, CCC−BB 격차도 줄어드는 중. 신용 쪽은 조용합니다."),
        "하위층 국지": (WARN, "CCC만 벌어지고 BB는 안정. 부실이 하위 등급에 머무는 중."),
        "전반 확대": ("#E89B4C", "BB 스프레드는 커지지만 CCC−BB 격차는 축소. 전반적 위험회피."),
        "전이 경보": (BAD, "CCC−BB 격차와 BB가 함께 확대. 하위층 스트레스가 위로 번지는 중."),
    }
    s_color, s_desc = STATE_INFO.get(state, (MUTED, "데이터 부족"))
    quad = "".join(
        f'<div class="{"on" if state == k else ""}" style="{f"background:{STATE_INFO[k][0]}" if state == k else ""}">{k}</div>'
        for k in ["하위층 국지", "전이 경보", "평온", "전반 확대"])

    c1, c2 = st.columns([1.15, 1], gap="medium")
    c1.markdown(f"""
    <div class="card summary">
      <div class="card-top"><div class="label">둔화 신호</div>
        <span class="pill" style="background:{lvl_color}22;color:{lvl_color}">{lvl_text}</span></div>
      <div class="big" style="margin-top:12px">{n_txt}<small> / 5</small></div>
      <div class="meter">{meter}</div>
      <div class="sigchips">{chips}</div>
      <div class="desc">{LONG}주 변화가 둔화 방향인 지표 수 · 빨간 칩이 켜진 신호</div>
    </div>""", unsafe_allow_html=True)
    c2.markdown(f"""
    <div class="card summary">
      <div class="label">신용 전이</div>
      <div class="state"><span class="dot" style="background:{s_color}"></span>{state}</div>
      <div class="desc">{s_desc}<br>CCC−BB {LONG}주 <b>{bp(last[f'CCC_BB_{LONG}w'])}</b> · BB {LONG}주 <b>{bp(last[f'BB_{LONG}w'])}</b></div>
      <div class="quad">{quad}</div>
    </div>""", unsafe_allow_html=True)

    # ───────── 계기판 ─────────
    section("🌼 핵심 계기판", f"둔화 신호 5개 · {LONG}주 / {SHORT}주 변화")
    SIG_NAME = {"consumer": "소비", "size": "규모", "gold_silver": "금/은"}
    cards = []
    for k in GAUGES:
        label, cap, clean, bad = GAUGES[k]
        a, b = clean if mode == "클린" else cap
        v13, v4 = last[f"{k}_{LONG}w"], last[f"{k}_{SHORT}w"]
        short, _, desc = label.partition(" (")
        desc = desc.replace("경기소비재/필수소비재", "경기소비/필수소비")
        cards.append(gauge_card(short, f"{desc.rstrip(')') + ' · ' if desc else ''}{a} / {b}", f"{last[k]:.3f}" if pd.notna(last[k]) else "—",
                                [(f"{LONG}주 {pct(v13)}", tone(v13, bad)), (f"{SHORT}주 {pct(v4)}", tone(v4, bad))],
                                flag=bool(sig_now[SIG_NAME[k]])))
    cards.append(gauge_card("HY OAS", "하이일드 스프레드", f"{last['HY']:.2f}%" if pd.notna(last["HY"]) else "—",
                            [(f"{LONG}주 {bp(last[f'HY_{LONG}w'])}", tone(last[f'HY_{LONG}w'], "up")),
                             (f"{SHORT}주 {bp(last[f'HY_{SHORT}w'])}", tone(last[f'HY_{SHORT}w'], "up"))],
                            flag=bool(sig_now["HY"])))
    cards.append(gauge_card("CCC − BB", "하위등급 격차", f"{last['CCC_BB']:.0f}bp" if pd.notna(last["CCC_BB"]) else "—",
                            [(f"{LONG}주 {bp(last[f'CCC_BB_{LONG}w'])}", tone(last[f'CCC_BB_{LONG}w'], "up")),
                             (f"BB {LONG}주 {bp(last[f'BB_{LONG}w'])}", tone(last[f'BB_{LONG}w'], "up"))],
                            flag=bool(sig_now["CCC−BB"])))
    for col, html in zip(st.columns(5, gap="small"), cards):
        col.markdown(html, unsafe_allow_html=True)

    # ───────── 참고 지표 ─────────
    section("🍋 참고 지표", "신호 개수에는 포함되지 않음")
    ref_cards = []
    for k in REF_GAUGES:
        if k in W:
            a, b = REF_GAUGES[k][1]
            v13 = last[f"{k}_{LONG}w"]
            ref_cards.append(gauge_card(REF_GAUGES[k][0].replace(" (참고)", ""), f"{a} / {b}",
                                        f"{last[k]:.4f}" if pd.notna(last[k]) else "—",
                                        [(f"{LONG}주 {pct(v13)}", tone(v13, "down"))], ref=True))
    if "IG" in W:
        ref_cards.append(gauge_card("IG OAS", "투자등급 스프레드", f"{last['IG']:.2f}%" if pd.notna(last["IG"]) else "—",
                                    [(f"{LONG}주 {bp(last[f'IG_{LONG}w'])}", tone(last[f'IG_{LONG}w'], "up"))], ref=True))
    for col, html in zip(st.columns(len(ref_cards), gap="small"), ref_cards):
        col.markdown(html, unsafe_allow_html=True)

    # ───────── 해석 가이드 (접힘) ─────────
    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    with st.expander("📖 지표 해석하는 법", expanded=False):
        g1, g2 = st.columns(2, gap="large")
        g1.markdown(f"""
    <div class="guide">
    <h4>둔화 신호 5개 — 이렇게 움직이면 ON</h4>
    <table>
    <tr><th>지표</th><th>둔화 방향</th><th>의미</th></tr>
    <tr><td>소비 (경기소비재/필수소비재)</td><td>↓</td><td>방어적 소비로 이동</td></tr>
    <tr><td>규모 (소형/대형)</td><td>↓</td><td>경기 민감 소형주 약세</td></tr>
    <tr><td>금/은</td><td>↑</td><td>산업 수요보다 안전자산 선호</td></tr>
    <tr><td>HY OAS</td><td>↑</td><td>하이일드 신용 위험 확대</td></tr>
    <tr><td>CCC − BB</td><td>↑</td><td>최하위 등급 스트레스</td></tr>
    </table>
    <ul>
    <li><b>0–1개</b> 안정 · <b>2–3개</b> 주의 · <b>4–5개</b> 경계</li>
    <li>방향이 같으면 확신↑, 엇갈리면 <b>먼저 움직인 축</b> 확인</li>
    </ul>
    </div>""", unsafe_allow_html=True)
        g2.markdown(f"""
    <div class="guide">
    <h4>신용 전이 — CCC−BB와 BB {LONG}주 변화의 조합</h4>
    <table>
    <tr><th></th><th>BB 축소</th><th>BB 확대</th></tr>
    <tr><th>CCC−BB 확대</th><td>🟡 하위층 국지</td><td>🔴 전이 경보</td></tr>
    <tr><th>CCC−BB 축소</th><td>🟢 평온</td><td>🟠 전반 확대</td></tr>
    </table>
    <ul>
    <li>CCC만 벌어지면 하위층 국지, <b>BB까지 따라 벌어지면 전이</b></li>
    </ul>
    <h4 style="margin-top:14px">주의할 점</h4>
    <ul>
    <li><b>규칙 고정</b>: {LONG}주 변화의 부호만 사용. 임계치·룩백을 성과 보고 바꾸면 스누핑.</li>
    <li><b>PIT</b>: 주간 = 그 주 금요일까지 마지막 종가. FRED OAS는 다음 영업일 업데이트 → 최신 1일은 비어 있을 수 있음.</li>
    <li><b>해석 함정</b>: XLY/XLP·IWM/SPY는 주식 비율이라 <i>경기</i>보다 <i>주식시장 분위기</i>를 반영 → 신용 축과 교차확인.</li>
    <li><b>금/은</b>: 2022년 이후 중앙은행 금 매수로 레벨 비교 어려움 → 변화 위주로.</li>
    <li><b>역할</b>: 참고용 나침반. 비중 조절 신호로 쓰려면 별도 IS/OOS 검증 필요.</li>
    </ul>
    </div>""", unsafe_allow_html=True)

    # ───────── 차트 / 기록 ─────────
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📈 차트", "🗂 주간 기록"])

    with tab1:
        def line(series: dict, title, yfmt=None, ma=True):
            fig = go.Figure()
            for i, (name, s) in enumerate(series.items()):
                s = s.dropna()
                fig.add_trace(go.Scatter(x=s.index, y=s, name=name, mode="lines",
                                         line=dict(width=2.2, color=CHART_COLORS[i % len(CHART_COLORS)])))
                if ma and len(series) == 1:
                    fig.add_trace(go.Scatter(x=s.index, y=s.rolling(LONG).mean(), name=f"{LONG}주 평균",
                                             mode="lines", line=dict(dash="dot", width=1.6, color="#B8A77E")))
            fig.update_yaxes(tickformat=yfmt)
            return style_fig(fig, title)

        charts = []
        for k in GAUGES:
            a, b = GAUGES[k][2] if mode == "클린" else GAUGES[k][1]
            charts.append(line({GAUGES[k][0].split(" (")[0]: W[k]}, f"{GAUGES[k][0]} · {a}/{b}"))
        charts.append(line({"HY": W["HY"], "BB": W["BB"], "IG": W.get("IG", pd.Series(dtype=float))},
                           "OAS (%)", ma=False))
        charts.append(line({"CCC−BB": W["CCC_BB"]}, "CCC − BB 격차 (bp)"))
        sig_colors = W["signals"].map(lambda v: "#CFC6AE" if pd.isna(v) else GOOD if v <= 1 else WARN if v <= 3 else BAD)
        sig_s = W["signals"].loc[W["signals"].first_valid_index():] if W["signals"].notna().any() else W["signals"]
        fig = go.Figure(go.Bar(x=sig_s.index, y=sig_s, marker=dict(color=sig_colors.loc[sig_s.index], line=dict(width=0)),
                               name="둔화 신호", hovertemplate="%{y:.0f}개<extra></extra>"))
        fig.update_xaxes(range=[sig_s.index.min() - pd.Timedelta(days=4), sig_s.index.max() + pd.Timedelta(days=4)])
        fig.update_yaxes(range=[0, 5], dtick=1)
        charts.append(style_fig(fig, "둔화 신호 개수 (0–5)"))

        for i in range(0, len(charts), 2):
            row = st.columns(2, gap="medium")
            for j, (col, f) in enumerate(zip(row, charts[i:i + 2])):
                with col.container(border=True, key=f"chartbox_{i + j}"):
                    st.plotly_chart(f, config=CHART_CFG)

    with tab2:
        top = st.columns([3, 1])
        n_weeks = top[0].slider("최근 몇 주", 8, 104, 26)
        view = W[["signals", "transfer", "consumer", f"consumer_{LONG}w", "size", f"size_{LONG}w",
                  "gold_silver", f"gold_silver_{LONG}w", "HY", f"HY_{LONG}w", "BB", f"BB_{LONG}w",
                  "CCC_BB", f"CCC_BB_{LONG}w"]].tail(n_weeks).iloc[::-1].copy()
        view.index = view.index.date
        view.columns = ["둔화신호", "신용전이", "소비", "소비13주", "규모", "규모13주", "금/은", "금/은13주",
                        "HY%", "HY13주bp", "BB%", "BB13주bp", "CCC−BB", "CCC−BB13주"]

        def sig_bg(v):
            if pd.isna(v):
                return ""
            return f"background-color: {'#E6F2E9' if v <= 1 else '#FFF0B8' if v <= 3 else '#FBE5DE'}; font-weight: 700"

        styled = view.style.format({
            "둔화신호": "{:.0f}", "소비": "{:.3f}", "규모": "{:.3f}", "금/은": "{:.1f}",
            "소비13주": "{:+.1%}", "규모13주": "{:+.1%}", "금/은13주": "{:+.1%}",
            "HY%": "{:.2f}", "BB%": "{:.2f}", "HY13주bp": "{:+.0f}", "BB13주bp": "{:+.0f}",
            "CCC−BB": "{:.0f}", "CCC−BB13주": "{:+.0f}"}, na_rep="—").map(sig_bg, subset=["둔화신호"])
        st.dataframe(styled, height=min(38 + 35 * n_weeks, 640))
        top[1].markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        top[1].download_button("⬇️ CSV 다운로드", W.to_csv().encode("utf-8-sig"), "regime_compass_weekly.csv",
                               width="stretch")


# ───────────────────────── 페이지 ─────────────────────────
def render_us():
    import sector_us
    sector_us.render()


def render_kr():
    import sector_kr
    sector_kr.render()


def render_regime():
    import regime_strategy
    regime_strategy.render()


st.set_page_config(page_title="Regime Compass", page_icon="🍋", layout="wide")
inject_css()
st.navigation([
    st.Page(render_cross_asset, title="크로스에셋", icon="🧭", url_path="cross-asset", default=True),
    st.Page(render_us, title="미국 섹터", icon="🇺🇸", url_path="us-sector"),
    st.Page(render_kr, title="한국 업종", icon="🇰🇷", url_path="kr-sector"),
    st.Page(render_regime, title="레짐 전략", icon="🧩", url_path="regime-tilt"),
], position="top").run()
