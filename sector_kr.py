"""한국 업종 화면: KOSPI 업종지수 RRG + 업종 수급(외국인·기관·연기금, 1주/1개월/3개월).

데이터: pykrx (KRX, 무료). 업종 = KOSPI 업종지수 18개 (KRX 2025 개편 이름).
수급 = 종목별 순매수거래대금을 업종지수 구성종목으로 합산 → 업종 시총 대비 %.
구성종목은 현재 기준 (과거 기간에도 현재 구성으로 합산 → 근사치).
"""
import datetime as dt
import os

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from compass_common import DEMO, rrg, rrg_figure, rrg_table, demo_prices, equal_weight_bench, auto_focus
from compass_ui import hero, section, chart_box, style_fig, CHART_CFG, INK


def _load_krx_login():
    """.streamlit/secrets.toml 의 KRX_ID / KRX_PW 를 pykrx가 읽는 환경 변수로 넘김 (pykrx 첫 import 전에 실행)."""
    try:
        for k in ("KRX_ID", "KRX_PW"):
            v = st.secrets.get(k)
            if v and not os.environ.get(k):
                os.environ[k] = str(v)
    except Exception:  # secrets 파일 없음
        pass


_load_krx_login()

KR_SECTORS = {
    "1005": "음식료·담배", "1006": "섬유·의류", "1007": "종이·목재", "1008": "화학", "1009": "제약",
    "1010": "비금속", "1011": "금속", "1012": "기계·장비", "1013": "전기전자", "1014": "의료·정밀",
    "1015": "운송장비", "1016": "유통", "1017": "전기·가스", "1018": "건설", "1019": "운송·창고",
    "1020": "통신", "1021": "금융", "1026": "일반서비스",
}
BENCH = "1001"  # KOSPI
INVESTORS = ["외국인", "기관합계", "연기금"]
WINDOWS = {"1주": 5, "1개월": 21, "3개월": 63}


def _reset_index_ticker():
    """pykrx IndexTicker 싱글톤이 첫 조회 실패 시 빈 표를 캐시하는 문제 회피."""
    try:
        from pykrx.website import krx
        if hasattr(krx, "IndexTicker"):
            krx.IndexTicker._instance = None
    except Exception:
        pass


def _retry(fn, *a, **k):
    for i in range(3):
        try:
            return fn(*a, **k)
        except Exception:
            _reset_index_ticker()
            if i == 2:
                raise


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_index_prices(start: str) -> pd.DataFrame:
    codes = [BENCH] + list(KR_SECTORS)
    if DEMO:
        return demo_prices(codes, start, seed=7)
    from pykrx import stock
    end = dt.date.today().strftime("%Y%m%d")
    s = start.replace("-", "")
    out = {}
    for c in codes:
        df = _retry(stock.get_index_ohlcv, s, end, c)
        out[c] = df["종가"]
    return pd.DataFrame(out).sort_index()


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_flows(trading_days: tuple) -> tuple:
    """반환: (flows_pct, flows_amt, asof). flows_* index=업종, columns=(투자자, 기간)."""
    days = list(trading_days)
    end = days[-1]
    if DEMO:
        rng = np.random.default_rng(5)
        cols = pd.MultiIndex.from_product([INVESTORS, WINDOWS])
        pct = pd.DataFrame(rng.normal(0, 0.3, (len(KR_SECTORS), len(cols))),
                           index=list(KR_SECTORS.values()), columns=cols)
        return pct, pct * 1000, end
    from pykrx import stock
    members = {c: _retry(stock.get_index_portfolio_deposit_file, c) for c in KR_SECTORS}
    cap = _retry(stock.get_market_cap, end, market="KOSPI")["시가총액"]
    sec_cap = {KR_SECTORS[c]: cap.reindex(m).sum() for c, m in members.items()}
    pct, amt = {}, {}
    for inv in INVESTORS:
        for w, n in WINDOWS.items():
            start = days[-n] if len(days) >= n else days[0]
            df = _retry(stock.get_market_net_purchases_of_equities, start, end, "KOSPI", inv)
            net = df["순매수거래대금"]
            a = {KR_SECTORS[c]: net.reindex(m).fillna(0).sum() for c, m in members.items()}
            amt[(inv, w)] = pd.Series(a) / 1e8  # 억원
            pct[(inv, w)] = pd.Series({k: a[k] / sec_cap[k] * 100 if sec_cap[k] > 0 else np.nan for k in a})
    return pd.DataFrame(pct), pd.DataFrame(amt), end


def render():
    hero("한국 업종", "KOSPI 업종지수 18개 로테이션 · 외국인/기관/연기금 수급",
         [("🇰🇷 KOSPI 대비", True), ("pykrx", False)])
    st.caption("처음 불러올 때 KRX 호출이 30회 정도라 1~2분 걸리고, 이후 6시간 캐시.")

    if not st.session_state.get("kr_loaded"):
        if st.button("📥 업종 데이터 불러오기", type="primary"):
            st.session_state["kr_loaded"] = True
            st.rerun()
        return

    with st.spinner("업종지수 불러오는 중…"):
        try:
            px = load_index_prices((dt.date.today() - dt.timedelta(days=3 * 365)).isoformat())
        except Exception as e:
            st.error(f"pykrx 업종지수 실패: {e}")
            return

    # ── RRG
    pw = px.resample("W-FRI").last()
    bench_name = st.radio("벤치마크", ["업종 동일가중", "KOSPI"], horizontal=True, key="kr_bench",
                          help="KOSPI는 전기전자(반도체) 비중이 커서, 반도체가 움직이면 나머지 업종이 "
                               "한꺼번에 같은 방향으로 쏠려 보여요. 동일가중은 그 쏠림을 뺀 기준이에요.")
    bench = equal_weight_bench(pw[list(KR_SECTORS)]) if bench_name == "업종 동일가중" else pw[BENCH]
    section("🔄 업종 로테이션", f"RRG · {bench_name} 대비 · 주간 · 정규화")
    ratio, mom = rrg(pw[list(KR_SECTORS)], bench)
    names = {c: KR_SECTORS[c] for c in ratio.columns}
    k1, k2 = st.columns([4, 1], gap="medium")
    tail = k2.slider("꼬리 (주)", 2, 12, 5, key="kr_tail")
    auto = auto_focus(ratio, mom, tail=tail, k=5)
    picked = k1.pills("꼬리 볼 업종 (기본: 최근 사분면이 바뀌었거나 많이 움직인 5개 자동 선택)",
                      list(names.values()), selection_mode="multi", default=[names[c] for c in auto],
                      key=f"kr_focus_{bench_name}_{tail}")
    focus = [c for c, nm in names.items() if nm in (picked or [])]
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1, chart_box("kr_rrg"):
        st.plotly_chart(rrg_figure(ratio, mom, KR_SECTORS, tail=tail, title="업종 RRG", focus=focus), config=CHART_CFG)
    with c2, chart_box("kr_rrg_tbl"):
        st.dataframe(rrg_table(ratio, mom, KR_SECTORS).style.format({"RS-Ratio": "{:.2f}", "RS-Mom": "{:.2f}"}),
                     hide_index=True, height=520)

    # ── 수급
    section("💸 업종 수급", "순매수 ÷ 업종 시총")
    days = tuple(d.strftime("%Y%m%d") for d in px.index[-70:])
    with st.spinner("투자자별 순매수 불러오는 중…"):
        try:
            pct, amt, asof = load_flows(days)
        except Exception as e:
            st.error(f"pykrx 수급 실패: {e}")
            return
    st.caption(f"기준 {asof} · 단위: 업종 시총 대비 % (괄호 안 표는 억원). 구성종목은 현재 기준.")

    inv = st.radio("투자자", INVESTORS, horizontal=True)
    view = pct[inv].copy()
    view = view.sort_values("1개월", ascending=False)
    fig = go.Figure(go.Heatmap(z=view.values, x=list(view.columns), y=list(view.index),
                               colorscale=[[0, "#E07A5F"], [0.5, "#FFFBEA"], [1, "#6FA67E"]], zmid=0,
                               text=np.round(view.values, 2), xgap=3, ygap=3,
                               texttemplate="%{text}", textfont=dict(color=INK),
                               hovertemplate="%{y} %{x}: %{z:.2f}%<extra></extra>"))
    style_fig(fig, f"{inv} 순매수 / 시총 (%)", height=600)
    fig.update_layout(yaxis=dict(autorange="reversed"), hovermode="closest")
    fig.update_yaxes(showgrid=False)
    c1, c2 = st.columns([2, 3], gap="medium")
    with c1, chart_box("kr_heat"):
        st.plotly_chart(fig, config=CHART_CFG)

    both = pd.DataFrame({
        "외국인 1M": pct[("외국인", "1개월")], "기관 1M": pct[("기관합계", "1개월")],
        "연기금 1M": pct[("연기금", "1개월")], "외국인 1W": pct[("외국인", "1주")],
        "외국인 3M": pct[("외국인", "3개월")], "기관 3M": pct[("기관합계", "3개월")],
    })
    both["외+기 동시 순매수(1M)"] = np.where((both["외국인 1M"] > 0) & (both["기관 1M"] > 0), "✅", "")
    both["외국인 가속"] = np.where(both["외국인 1W"] * 4 > both["외국인 1M"], "↑", "↓")
    with c2, chart_box("kr_flow_tbl"):
        st.dataframe(both.sort_values("외국인 1M", ascending=False).style.format(
        {c: "{:+.2f}" for c in ["외국인 1M", "기관 1M", "연기금 1M", "외국인 1W", "외국인 3M", "기관 3M"]}, na_rep="—"))
    c2.caption("외국인 가속 = 최근 1주 순매수 페이스(×4)가 1개월 평균보다 빠른지. "
               "리포트(유안타)는 외국인·기관 동시 순매수 업종을 따로 봄. "
               "참고: 우리 검증에서 외국인 순매수 추종은 구간마다 부호가 바뀌어 불안정했고, "
               "기관 60일 순매수 상위는 외국인 매도 국면에서 역효과(대신 리포트).")
    with st.expander("🧾 억원 기준 표"):
        st.dataframe(amt.round(0))
