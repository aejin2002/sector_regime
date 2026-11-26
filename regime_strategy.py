"""레짐 전략 페이지 — SAA_REGIME_TILT (성장×인플레 레짐 틸트) 의 레짐·신호만 보여줌.

계산은 SAA_REGIME_TILT 의 strategy.py 를 saa_strategy.py 로 그대로 가져와 사용.
API 키(FRED_API_KEY, FG_KRX_AUTH_KEY)는 st.secrets 에서 읽어 환경변수로 주입.
"""
import os
import tomllib
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from compass_ui import *  # noqa: F401,F403

BASE_DIR = Path(__file__).resolve().parent
VKOSPI_CSV = BASE_DIR / "data" / "vkospi_daily.csv"
# 로컬 편의용: 이 앱 secrets 에 키가 없으면 원본 SAA_REGIME_TILT 앱의 secrets 를 읽음 (클라우드엔 없음 → 무시)
_LEGACY_SECRETS = Path.home() / "Desktop/전략/growth_inflation_regime_tilt_final/streamlit_app/.streamlit/secrets.toml"

REGIME_INFO = {  # 이름, 색, 축 설명
    "Goldilocks": ("골디락스", "#6FA67E", "성장 ↑ · 인플레 ↓"),
    "Reflation": ("리플레이션", "#E89B4C", "성장 ↑ · 인플레 ↑"),
    "Stagflation": ("스태그플레이션", "#E07A5F", "성장 ↓ · 인플레 ↑"),
    "Deflation": ("디플레이션", "#8E9CC9", "성장 ↓ · 인플레 ↓"),
}
KEYS = ("FRED_API_KEY", "FG_KRX_AUTH_KEY")


def _inject_keys():
    """saa_strategy 는 import 시점에 os.environ 에서 키를 읽으므로 그 전에 주입."""
    for k in KEYS:
        if os.environ.get(k):
            continue
        try:
            os.environ[k] = st.secrets[k]
        except Exception:  # noqa: BLE001
            pass
    missing = [k for k in KEYS if not os.environ.get(k)]
    if missing and _LEGACY_SECRETS.exists():
        with open(_LEGACY_SECRETS, "rb") as f:
            sec = tomllib.load(f)
        for k in missing:
            if sec.get(k):
                os.environ[k] = sec[k]


def _load_strategy():
    _inject_keys()
    import saa_strategy
    return saa_strategy


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_all():
    S = _load_strategy()
    d = S.fetch_market_data(str(VKOSPI_CSV))
    bt = S.build_backtest(d)
    _, vote = S.run_crisis_overlay(d["vix_d"], d["vix_ma20"], d["spy_5d"], d["hyg_5d"])
    keep = ["latest_signal_month", "latest_regime", "next_month", "next_month_is_fallback",
            "live_regime_this_month", "cur_month", "crisis_on_today", "fg_on_today", "crisis_state",
            "crisis_runs", "growth_axis", "inflation_axis", "regime_macro", "sfg_df", "sfg_score_latest",
            "sfg_status_text", "sfg_data_asof", "last_trading_day", "fg_ok", "growth_is_vintage",
            "inflation_is_vintage", "recession_fp_rate"]
    out = {k: bt[k] for k in keep}
    out.update(vix=d["vix_d"], vix_ma20=d["vix_ma20"], spy_5d=d["spy_5d"], hyg_5d=d["hyg_5d"], vote=vote)
    cfg = dict(eq=S.REGIME_EQUITY_TARGET, vix_level=S.VIX_LEVEL, vix_spike=S.VIX_SPIKE, spy_thr=S.SPY_5D_THR,
               hyg_thr=S.HYG_5D_THR, min_hold=S.MIN_HOLD_DAYS, min_off=S.MIN_OFF_STREAK,
               sfg_entry=S.SFG_ENTRY, sfg_hold=S.SFG_HOLD, universe=S.ETF_UNIVERSE)
    return out, cfg


# ───────── UI 조각 ─────────
def badge(text, color):
    return f'<span class="flag" style="background:{color}1F;color:{color}">{text}</span>'


def sig_card(label, sub, value, state_html, deltas, alert=False):
    cls = "card gauge" + (" alert" if alert else "")
    return (f'<div class="{cls}"><div class="card-top"><div><div class="label">{label}</div>'
            f'<div class="sub">{sub}</div></div>{state_html}</div>'
            f'<div class="value">{value}</div>'
            f'<div class="deltas">{"".join(pill(t, c) for t, c in deltas)}</div></div>')


def quad_html(cur):
    cells = []
    for k in ["Goldilocks", "Reflation", "Deflation", "Stagflation"]:
        name, color, _ = REGIME_INFO[k]
        on = k == cur
        cells.append(f'<div class="{"on" if on else ""}" style="{f"background:{color}" if on else ""}">{name}</div>')
    return ('<div style="display:flex;justify-content:space-between;font-size:0.68rem;color:#B3A98F;margin-top:12px">'
            '<span>← 인플레 ↓</span><span>인플레 ↑ →</span></div>'
            f'<div class="quad" style="margin-top:4px">{"".join(cells)}</div>'
            '<div style="font-size:0.68rem;color:#B3A98F;margin-top:3px">위: 성장 ↑ · 아래: 성장 ↓</div>')


def ym(ts):
    return f"{ts.year}년 {ts.month}월" if ts is not None and pd.notna(ts) else "—"


def rinfo(k):
    return REGIME_INFO.get(k, (str(k), MUTED, ""))


# ───────── 페이지 ─────────
def render():
    with st.spinner("FRED 실시간 빈티지 · 가격 · VKOSPI 불러오는 중… (처음엔 10초쯤 걸려요)"):
        try:
            R, C = load_all()
        except Exception as e:  # noqa: BLE001
            st.error(f"데이터를 불러오지 못했어요: {e}")
            return

    reg = R["latest_regime"]
    name, color, axes = rinfo(reg)
    live_name, live_color, _ = rinfo(R["live_regime_this_month"])
    eq_next = C["eq"].get(reg, 0.6)
    eq_live = C["eq"].get(R["live_regime_this_month"], 0.6)
    crisis_on, fg_on = R["crisis_on_today"], R["fg_on_today"]

    with st.sidebar:
        st.markdown("### 🐤 레짐 전략")
        if st.button("🔄 데이터 새로고침", width="stretch", key="rs_refresh"):
            load_all.clear()
            st.rerun()
        st.caption("SAA_REGIME_TILT 의 strategy.py 로 계산 · 6시간 캐시")

    hero("레짐 전략", "SAA Regime Tilt · 성장(INDPRO) × 인플레(CPI) 레짐 + 위기 오버레이 + 간단 F&G",
         chips=[(f"레짐 <b>{name}</b>", True),
                (f"위기 오버레이 <b>{'ON' if crisis_on else 'OFF'}</b>", crisis_on),
                (f"가격 기준 {R['last_trading_day']:%Y-%m-%d}", False)])

    # ───────── 오늘의 시그널 ─────────
    section("🧭 오늘의 시그널", f"신호월 {ym(R['latest_signal_month'])} · 실시간 빈티지(발표 시점 기준) 데이터")
    g = R["growth_axis"].iloc[-1]
    i = R["inflation_axis"].iloc[-1]
    c1, c2, c3 = st.columns([1.25, 1, 1], gap="medium")
    fb = "⚠ 데이터 부족 → 균등비중 폴백" if R["next_month_is_fallback"] else f"{ym(R['next_month'])} 배분에 적용"
    c1.markdown(f"""
    <div class="card summary">
      <div class="card-top"><div class="label">현재 레짐 · {ym(R['latest_signal_month'])} 신호</div>
        {badge(axes, color)}</div>
      <div class="state" style="font-size:2.1rem"><span class="dot" style="background:{color}"></span>{name}</div>
      <div class="desc">{fb} · 목표 주식비중 <b>{eq_next:.0%}</b><br>
        이번 달({ym(R['cur_month'])}) 배분은 <b style="color:{live_color}">{live_name}</b> 기준 (주식 {eq_live:.0%})</div>
      {quad_html(reg)}
    </div>""", unsafe_allow_html=True)

    vote_now = int(R["vote"].iloc[-1]) if pd.notna(R["vote"].iloc[-1]) else 0
    v, vm = R["vix"].iloc[-1], R["vix_ma20"].iloc[-1]
    s5, h5 = R["spy_5d"].iloc[-1], R["hyg_5d"].iloc[-1]
    shocks = [("VIX", (v > C["vix_level"]) and (v / vm - 1 > C["vix_spike"])),
              ("SPY 5일", s5 <= C["spy_thr"]), ("HYG 5일", h5 <= C["hyg_thr"])]
    chips = "".join(f'<span class="sigchip{" on" if on else ""}">{k}</span>' for k, on in shocks)
    run_txt = ""
    if crisis_on and R["crisis_runs"]:
        run_txt = f"{R['crisis_runs'][-1][0]:%m/%d}부터 방어 중 · "
    c2.markdown(f"""
    <div class="card summary">
      <div class="card-top"><div class="label">위기 오버레이 · {R['last_trading_day']:%m/%d}</div>
        {badge("ON · 위험회피" if crisis_on else "OFF · 정상", BAD if crisis_on else GOOD)}</div>
      <div class="big" style="margin-top:12px;font-size:2.6rem">{vote_now}<small> / 3 투표</small></div>
      <div class="meter">{"".join(f'<span style="background:{BAD if k < vote_now else "#F3ECD6"}"></span>' for k in range(3))}</div>
      <div class="sigchips">{chips}</div>
      <div class="desc">{run_txt}2표 이상이면 다음 날부터 SPY·QQQ·KODEX200·DBC → BIL<br>
        최소 {C['min_hold']}일 유지, OFF {C['min_off']}일 연속이면 해제</div>
    </div>""", unsafe_allow_html=True)

    sc = R["sfg_score_latest"]
    sc_txt = f"{sc:.1f}" if sc is not None else "—"
    sfg_col = GOOD if fg_on else MUTED
    c3.markdown(f"""
    <div class="card summary">
      <div class="card-top"><div class="label">간단 F&amp;G · KODEX200</div>
        {badge("보유중" if fg_on else "미보유 → SPY", sfg_col)}</div>
      <div class="big" style="margin-top:12px;font-size:2.6rem">{sc_txt}<small> / 100</small></div>
      <div class="meter">{"".join(f'<span style="background:{HONEY if sc is not None and k < round(sc / 20) else "#F3ECD6"}"></span>' for k in range(5))}</div>
      <div class="desc">{R['sfg_status_text']}<br>점수 {C['sfg_entry']} 미만(공포) → 다음 날 진입, {C['sfg_hold']}거래일 보유
        <span style="color:#B3A98F">· 기준 {R['sfg_data_asof']:%m/%d}</span></div>
    </div>""" if R["sfg_data_asof"] is not None else """
    <div class="card summary"><div class="label">간단 F&amp;G · KODEX200</div>
      <div class="desc">VKOSPI 데이터를 불러오지 못해 항상 보유로 처리돼요.</div></div>""", unsafe_allow_html=True)

    # ───────── 레짐 신호 ─────────
    section("📡 레짐 신호", "YoY가 직전 12개월 평균(추세)보다 높으면 ↑")
    sfg = R["sfg_df"]
    last_sfg = sfg.iloc[-1] if len(sfg) else None

    def axis_card(label, sub, row, up_good):
        up = bool(row["rising"])
        gap = row["value"] - row["trend"]
        good = up if up_good else not up
        return sig_card(label, sub, f"{row['value']:.2f}%",
                        badge(("↑ 상승" if up else "↓ 둔화"), GOOD if good else BAD),
                        [(f"추세 {row['trend']:.2f}%", "flat"), (f"괴리 {gap:+.2f}%p", "good" if good else "bad"),
                         (f"{row['obs']:%Y-%m} 관측 · {row['pub']:%m/%d} 발표", "flat")])

    cards = [
        axis_card("성장 · 산업생산 YoY", "INDPRO 실시간 빈티지", g, True),
        axis_card("인플레 · CPI YoY", "CPIAUCSL 실시간 빈티지", i, False),
        sig_card("VIX", f"> {C['vix_level']} & MA20 대비 +{C['vix_spike']:.0%}", f"{v:.1f}",
                 badge("쇼크" if shocks[0][1] else "정상", BAD if shocks[0][1] else GOOD),
                 [(f"MA20 {vm:.1f}", "flat"), (f"괴리 {v / vm - 1:+.0%}", "bad" if v > vm else "good")],
                 alert=shocks[0][1]),
        sig_card("SPY · HYG 5일", f"≤ {C['spy_thr']:.0%} / ≤ {C['hyg_thr']:.0%} 이면 쇼크",
                 f"{s5:+.1%}", badge("쇼크" if (shocks[1][1] or shocks[2][1]) else "정상",
                                     BAD if (shocks[1][1] or shocks[2][1]) else GOOD),
                 [(f"SPY {s5:+.1%}", "bad" if shocks[1][1] else "flat"),
                  (f"HYG {h5:+.1%}", "bad" if shocks[2][1] else "flat")],
                 alert=shocks[1][1] or shocks[2][1]),
    ]
    for col, html in zip(st.columns(4, gap="small"), cards):
        col.markdown(html, unsafe_allow_html=True)

    with st.expander("📖 전략 규칙 한눈에 보기"):
        eq = C["eq"]
        st.markdown(f"""
<div class="guide">
<h4>1) 월별 레짐 배분</h4>
<table><tr><th></th><th>인플레 ↓</th><th>인플레 ↑</th></tr>
<tr><th>성장 ↑</th><td>🟢 골디락스 · 주식 {eq['Goldilocks']:.0%}</td><td>🟠 리플레이션 · 주식 {eq['Reflation']:.0%}</td></tr>
<tr><th>성장 ↓</th><td>🔵 디플레이션 · 주식 {eq['Deflation']:.0%}</td><td>🔴 스태그플레이션 · 주식 {eq['Stagflation']:.0%}</td></tr></table>
<ul>
<li><b>주식</b> = SPY · QQQ · KODEX200 균등, <b>비주식</b> = DBC · GLD · IEF · TLT · LQD · TIP 균등</li>
<li>성장 = INDPRO YoY, 인플레 = CPI YoY. 각각 직전 12개월 평균보다 높으면 ↑ (ALFRED 실시간 빈티지, 발표일 기준)</li>
<li>신호월 레짐은 <b>다음 달</b> 배분에 적용. 표본이 부족한 레짐(이력 36개월 미만, 같은 레짐 6회 미만)은 균등비중</li>
</ul>
<h4>2) 일별 위기 오버레이</h4>
<ul><li>VIX &gt; {C['vix_level']} & MA20 대비 +{C['vix_spike']:.0%}, SPY 5일 ≤ {C['spy_thr']:.0%}, HYG 5일 ≤ {C['hyg_thr']:.0%} 중 2개 → 다음 날 위험자산을 BIL로</li>
<li>최소 {C['min_hold']}거래일 유지, OFF {C['min_off']}일 연속이면 해제</li></ul>
<h4>3) 간단 F&amp;G (KODEX200 전용)</h4>
<ul><li>점수 = VKOSPI 역백분위와 KOSPI 20일 모멘텀 백분위 가중합 (252일)</li>
<li>점수 {C['sfg_entry']} 미만이면 다음 날 진입해 {C['sfg_hold']}거래일 보유, 미보유 시 KODEX200 몫은 SPY로</li></ul>
</div>""", unsafe_allow_html=True)

    # ───────── 차트 ─────────
    section("📈 흐름", "")
    t1, t2, t3, t4 = st.tabs(["🗺 레짐 히스토리", "📡 성장 · 인플레", "🚨 위기 신호", "🇰🇷 간단 F&G"])

    with t1:
        H = R["regime_macro"].loc["2000-01-01":]
        keys = list(REGIME_INFO)
        n = len(keys)
        scale = []
        for k_i, k in enumerate(keys):
            scale += [[k_i / n, REGIME_INFO[k][1]], [(k_i + 1) / n, REGIME_INFO[k][1]]]
        fig = go.Figure(go.Heatmap(
            z=[[keys.index(r) for r in H["regime"]]], x=H.index, y=["레짐"],
            text=[[REGIME_INFO[r][0] for r in H["regime"]]], colorscale=scale, zmin=-0.5, zmax=n - 0.5,
            showscale=False, xgap=0.5, hovertemplate="%{x|%Y-%m} 신호<br><b>%{text}</b><extra></extra>"))
        for k in keys:
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name=REGIME_INFO[k][0],
                                     marker=dict(size=11, color=REGIME_INFO[k][1], symbol="square")))
        style_fig(fig, "월별 레짐 (신호월 기준 · 다음 달 배분에 적용)", height=200)
        fig.update_layout(hovermode="closest")
        fig.update_yaxes(showticklabels=False)
        with chart_box("rs_hist"):
            st.plotly_chart(fig, width="stretch", config=CHART_CFG)

        T = R["regime_macro"].tail(12).iloc[::-1]
        ga, ia = R["growth_axis"], R["inflation_axis"]
        tbl = pd.DataFrame({
            "신호월": T.index.strftime("%Y-%m"),
            "성장 YoY / 추세": [f"{ga.loc[d, 'value']:.2f}% / {ga.loc[d, 'trend']:.2f}%" if d in ga.index else "—" for d in T.index],
            "인플레 YoY / 추세": [f"{ia.loc[d, 'value']:.2f}% / {ia.loc[d, 'trend']:.2f}%" if d in ia.index else "—" for d in T.index],
            "레짐": T["regime"].map(lambda r: REGIME_INFO[r][0]),
            "주식비중": T["regime"].map(lambda r: f"{C['eq'][r]:.0%}"),
        })

        def paint(val):
            for nm, c, _ in REGIME_INFO.values():
                if val == nm:
                    return f"background-color:{c}26;color:{c};font-weight:700"
            return ""
        with chart_box("rs_tbl"):
            st.dataframe(tbl.style.map(paint, subset=["레짐"]), hide_index=True, width="stretch")

    with t2:
        a, b = st.columns(2, gap="medium")
        for col, ax, title, key in [(a, R["growth_axis"], "성장: 산업생산 YoY vs 12개월 추세", "g"),
                                    (b, R["inflation_axis"], "인플레: CPI YoY vs 12개월 추세", "i")]:
            A = ax.loc["2015-01-01":]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=A.index, y=A["trend"], name="추세(12M 평균)",
                                     line=dict(color="#8C6D46", width=1.6, dash="dot")))
            fig.add_trace(go.Scatter(x=A.index, y=A["value"], name="YoY", line=dict(color=HONEY, width=2.2)))
            fig.update_yaxes(ticksuffix="%")
            with col, chart_box(f"rs_{key}"):
                st.plotly_chart(style_fig(fig, title), width="stretch", config=CHART_CFG)

    with t3:
        start = R["last_trading_day"] - pd.DateOffset(years=2)
        vx = R["vix"].loc[start:]
        fig = go.Figure(go.Scatter(x=vx.index, y=vx, name="VIX", line=dict(color=HONEY, width=2)))
        fig.add_trace(go.Scatter(x=vx.index, y=R["vix_ma20"].loc[start:], name="MA20",
                                 line=dict(color="#8C6D46", width=1.4, dash="dot")))
        fig.add_hline(y=C["vix_level"], line_color=BAD, line_dash="dash", line_width=1,
                      annotation_text=str(C["vix_level"]), annotation_font_color=BAD)
        for s0, s1 in R["crisis_runs"]:
            if s1 >= start:
                fig.add_vrect(x0=max(s0, start), x1=s1 + pd.Timedelta(days=1), fillcolor=BAD, opacity=0.12, line_width=0)
        with chart_box("rs_vix"):
            st.plotly_chart(style_fig(fig, "VIX (빨간 음영 = 위기 오버레이 ON)"), width="stretch", config=CHART_CFG)
        a, b = st.columns(2, gap="medium")
        for col, key, th, title in [(a, "spy_5d", C["spy_thr"], "SPY 5일 수익률"), (b, "hyg_5d", C["hyg_thr"], "HYG 5일 수익률")]:
            s = R[key].loc[start:] * 100
            fig = go.Figure(go.Scatter(x=s.index, y=s, name=title, line=dict(color=HONEY, width=1.6),
                                       fill="tozeroy", fillcolor="rgba(230,180,34,0.12)"))
            fig.add_hline(y=th * 100, line_color=BAD, line_dash="dash", line_width=1,
                          annotation_text=f"{th:.0%}", annotation_font_color=BAD)
            fig.update_yaxes(ticksuffix="%")
            with col, chart_box(f"rs_{key}"):
                st.plotly_chart(style_fig(fig, title, height=260), width="stretch", config=CHART_CFG)

    with t4:
        if len(sfg):
            F = sfg.loc[R["last_trading_day"] - pd.DateOffset(years=2):]
            fig = go.Figure(go.Scatter(x=F.index, y=F["score"], name="F&G 점수", line=dict(color=HONEY, width=2)))
            fig.add_hline(y=C["sfg_entry"], line_color=GOOD, line_dash="dash", line_width=1,
                          annotation_text=f"진입 {C['sfg_entry']}", annotation_font_color=GOOD)
            fig.update_yaxes(range=[0, 100])
            with chart_box("rs_sfg"):
                st.plotly_chart(style_fig(fig, "간단 F&G 점수 (낮을수록 공포 → 매수 기회)"), width="stretch", config=CHART_CFG)
            if last_sfg is not None and {"v_score", "m_score"} <= set(sfg.columns):
                st.caption(f"VKOSPI 점수 {last_sfg['v_score']:.1f} · KOSPI 모멘텀 점수 {last_sfg['m_score']:.1f}")
        else:
            st.info("VKOSPI 데이터를 불러오지 못했어요.")

    st.markdown('<div class="foot">레짐 전략 · SAA_REGIME_TILT strategy.py 로 실시간 계산 · 과거 성과·신호이며 투자 조언 아님</div>',
                unsafe_allow_html=True)
