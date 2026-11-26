"""미국 섹터 화면: RRG + 유진 4사분면(EPS 수정 × 주가) + 키움 표(이익 vs 멀티플, PEG, 상대 P/E, 분위).

데이터 (무료)
- S&P 500 구성·GICS 섹터: 위키피디아 (현재 구성 → 과거로 돌리면 생존편향, 현황판 용도만)
- 종목별 EPS 컨센서스: yfinance Ticker.eps_trend (현재, 7/30/60/90일 전) + info(시총, 회계연도 말)
- 가격: yfinance (배당 미조정 종가)
매일 스냅샷을 snapshots/에 저장 → 그날부터는 PIT가 보장되는 이력이 쌓임.
"""
import io
import os
import time
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

from compass_common import DEMO, SNAP_DIR, rrg, rrg_figure, rrg_table, demo_prices, auto_focus
from compass_ui import hero, section, chart_box, style_fig, CHART_CFG, INK, MUTED

SECTORS = {  # ETF: (한글, GICS)
    "XLK": ("IT", "Information Technology"),
    "XLC": ("커뮤니케이션", "Communication Services"),
    "XLY": ("경기소비재", "Consumer Discretionary"),
    "XLP": ("필수소비재", "Consumer Staples"),
    "XLV": ("헬스케어", "Health Care"),
    "XLF": ("금융", "Financials"),
    "XLI": ("산업재", "Industrials"),
    "XLE": ("에너지", "Energy"),
    "XLB": ("소재", "Materials"),
    "XLU": ("유틸리티", "Utilities"),
    "XLRE": ("부동산", "Real Estate"),
}
GICS_TO_ETF = {g: e for e, (_, g) in SECTORS.items()}
LABELS = {e: k for e, (k, _) in SECTORS.items()}
H_COLS = {"7일": ("7daysAgo", 7), "30일": ("30daysAgo", 30), "60일": ("60daysAgo", 60), "90일": ("90daysAgo", 90)}
EPS_COLS = ["current"] + [c for c, _ in H_COLS.values()]
HIST_FILE = os.path.join(SNAP_DIR, "us_sector_history.csv")


# ───────────────────────── 데이터 수집 ─────────────────────────
def sp500_members() -> pd.DataFrame:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    df = pd.read_html(io.StringIO(html))[0]
    df = df.rename(columns={"Symbol": "symbol", "GICS Sector": "gics"})
    df["symbol"] = df["symbol"].astype(str).str.replace(".", "-", regex=False)
    df["etf"] = df["gics"].map(GICS_TO_ETF)
    return df[["symbol", "gics", "etf"]].dropna()


def _fetch_one(sym: str) -> dict:
    import yfinance as yf
    row = {"symbol": sym}
    for attempt in range(3):
        try:
            t = yf.Ticker(sym)
            et = t.eps_trend
            info = t.info or {}
            row["mcap"] = info.get("marketCap")
            row["last_fye"] = info.get("lastFiscalYearEnd")
            for per, tag in [("0y", "fy0"), ("+1y", "fy1")]:
                for c in EPS_COLS:
                    v = np.nan
                    if et is not None and per in et.index and c in et.columns:
                        v = et.loc[per, c]
                    row[f"{tag}_{c}"] = v
            return row
        except Exception as e:  # 레이트리밋 등
            row["err"] = str(e)[:80]
            time.sleep(2 * (attempt + 1))
    return row


def fetch_snapshot(progress=None) -> pd.DataFrame:
    """S&P 500 전 종목 EPS 추정치 + 가격 → 종목 단위 스냅샷 DataFrame."""
    if DEMO:
        return _demo_snapshot()
    import yfinance as yf
    mem = sp500_members()
    syms = mem["symbol"].tolist()
    rows = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_fetch_one, s): s for s in syms}
        for i, f in enumerate(as_completed(futs)):
            rows.append(f.result())
            if progress:
                progress.progress((i + 1) / len(syms), text=f"EPS 추정치 {i + 1}/{len(syms)}")
    est = pd.DataFrame(rows)
    px = yf.download(syms, period="6mo", auto_adjust=False, progress=False)["Close"]
    today = px.index.max()
    est["p_now"] = est["symbol"].map(px.ffill().iloc[-1])
    for _, (col, d) in H_COLS.items():
        ref = px.ffill().loc[:today - pd.Timedelta(days=d)].iloc[-1]
        est[f"p_{col}"] = est["symbol"].map(ref)
    snap = mem.merge(est, on="symbol", how="left")
    snap["asof"] = today.date().isoformat()
    return snap


def _demo_snapshot() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    rows = []
    for e, (_, g) in SECTORS.items():
        for i in range(40):
            eps0 = rng.uniform(1, 10)
            p = eps0 * rng.uniform(10, 35)
            r = {"symbol": f"{e}{i}", "gics": g, "etf": e, "mcap": p * rng.uniform(1e8, 3e9),
                 "last_fye": int(pd.Timestamp("2025-12-31").timestamp()), "p_now": p}
            drift = rng.normal(0, 0.03)
            for c, d in [("current", 0)] + list(H_COLS.values()):
                k = "current" if c == "current" else c
                f = 1 - drift * d / 90 + rng.normal(0, 0.005)
                r[f"fy0_{k}"] = eps0 * f
                r[f"fy1_{k}"] = eps0 * 1.1 * f
                if c != "current":
                    r[f"p_{k}"] = p * (1 - rng.normal(0.01, 0.05) * d / 90)
            rows.append(r)
    s = pd.DataFrame(rows)
    s["asof"] = dt.date.today().isoformat()
    return s


def snapshot_path(d: str) -> str:
    return os.path.join(SNAP_DIR, f"us_stocks_{d}.csv")


def latest_snapshot():
    files = sorted(f for f in os.listdir(SNAP_DIR) if f.startswith("us_stocks_"))
    if not files:
        return None
    return pd.read_csv(os.path.join(SNAP_DIR, files[-1]))


# ───────────────────────── 계산 ─────────────────────────
def _blend_12mf(snap: pd.DataFrame, col: str, days_ago: int) -> pd.Series:
    """12MF EPS = w·FY0 + (1−w)·FY1, w = 현재 회계연도 남은 비율 (h일 전 시점 기준)."""
    asof = pd.Timestamp(snap["asof"].iloc[0])
    fye = pd.to_datetime(snap["last_fye"], unit="s", errors="coerce") + pd.DateOffset(years=1)
    w = ((fye - (asof - pd.Timedelta(days=days_ago))).dt.days / 365).clip(0, 1).fillna(0.5)
    return w * snap[f"fy0_{col}"] + (1 - w) * snap[f"fy1_{col}"]


def _agg(g: pd.DataFrame, hcol: str) -> dict:
    s = g["mcap"] / g["p_now"]  # 주식 수 (현재 기준 고정)
    ok = g[["mcap", "p_now", f"p_{hcol}", "e_now", "e_h"]].notna().all(axis=1) & (g["p_now"] > 0)
    s, gg = s[ok], g[ok]
    e_now, e_h = (s * gg["e_now"]).sum(), (s * gg["e_h"]).sum()
    cap_now, cap_h = gg["mcap"].sum(), (s * gg[f"p_{hcol}"]).sum()
    okg = ok & g["fy0_current"].notna() & g["fy1_current"].notna()
    e0 = (g.loc[okg, "mcap"] / g.loc[okg, "p_now"] * g.loc[okg, "fy0_current"]).sum()
    e1 = (g.loc[okg, "mcap"] / g.loc[okg, "p_now"] * g.loc[okg, "fy1_current"]).sum()
    pe_now = cap_now / e_now if e_now > 0 else np.nan
    pe_h = cap_h / e_h if e_h > 0 else np.nan
    growth = e1 / e0 - 1 if e0 > 0 else np.nan
    return {
        "eps_chg": e_now / e_h - 1 if e_h > 0 else np.nan,
        "price_chg": cap_now / cap_h - 1 if cap_h > 0 else np.nan,
        "pe_now": pe_now, "pe_h": pe_h,
        "pe_chg": pe_now / pe_h - 1 if pe_h and pe_h > 0 else np.nan,
        "growth": growth,
        "peg": pe_now / (growth * 100) if growth and growth > 0 else np.nan,
        "coverage": gg["mcap"].sum() / g["mcap"].sum() if g["mcap"].sum() > 0 else np.nan,
        "n": int(ok.sum()),
    }


def sector_table(snap: pd.DataFrame, hlabel: str) -> pd.DataFrame:
    hcol, d = H_COLS[hlabel]
    snap = snap.copy()
    snap["e_now"] = _blend_12mf(snap, "current", 0)
    snap["e_h"] = _blend_12mf(snap, hcol, d)
    rows = {e: _agg(snap[snap["etf"] == e], hcol) for e in SECTORS}
    rows["SPX"] = _agg(snap, hcol)
    df = pd.DataFrame(rows).T
    df["rel_pe"] = df["pe_now"] / df.loc["SPX", "pe_now"]
    return df


def verdict(r):
    if pd.isna(r["eps_chg"]) or pd.isna(r["pe_chg"]):
        return "—"
    if r["eps_chg"] >= 0 and r["pe_chg"] < 0:
        return "이익↑·멀티플↓ (키움 OW형)"
    if r["eps_chg"] <= 0 and r["pe_chg"] > 0:
        return "이익 없는 리레이팅 (UW형)"
    if r["eps_chg"] > 0 and r["pe_chg"] >= 0:
        return "이익·멀티플 동반↑"
    return "이익↓·멀티플↓"


def quadrant(r):
    if pd.isna(r["eps_chg"]) or pd.isna(r["price_chg"]):
        return "—"
    up_e, up_p = r["eps_chg"] > 0, r["price_chg"] > 0
    return {(True, True): "1 모멘텀 유지", (False, True): "2 오버슈팅 우려",
            (False, False): "3 최악", (True, False): "4 반등 후보"}[(up_e, up_p)]


def update_history(tables: dict, asof: str):
    rows = []
    for h, t in tables.items():
        for sec, r in t.iterrows():
            rows.append({"date": asof, "sector": sec, "h": h, "eps_chg": r["eps_chg"],
                         "price_chg": r["price_chg"], "pe_now": r["pe_now"], "rel_pe": r["rel_pe"]})
    new = pd.DataFrame(rows)
    if os.path.exists(HIST_FILE):
        old = pd.read_csv(HIST_FILE)
        old = old[old["date"] != asof]
        new = pd.concat([old, new], ignore_index=True)
    new.to_csv(HIST_FILE, index=False)


def load_history():
    return pd.read_csv(HIST_FILE) if os.path.exists(HIST_FILE) else pd.DataFrame()


# ───────────────────────── 가격 (RRG) ─────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_etf_prices(start: str) -> pd.DataFrame:
    tick = list(SECTORS) + ["SPY"]
    if DEMO:
        return demo_prices(tick, start, seed=3)
    import yfinance as yf
    return yf.download(tick, start=start, auto_adjust=True, progress=False)["Close"].dropna(how="all")


# ───────────────────────── UI ─────────────────────────
GLOSSARY = """
- **멀티플 (P/E)** = 시가총액 ÷ 향후 12개월 예상이익(12MF). "이익 1달러에 몇 달러를 내나".
  주가 변화 = 이익 변화 × 멀티플 변화 (항등식) → 키움 표는 주가 움직임을 이 두 조각으로 쪼갠 것.
- **PEG** = P/E ÷ 이익성장률(%). 성장까지 감안한 가격. 1 근처면 성장 대비 적정, 높을수록 비쌈.
  여기선 성장률 = 내년 vs 올해 EPS(1년)라 리포트(보통 2~3년 CAGR)보다 들쭉날쭉함.
- **상대 P/E** = 섹터 P/E ÷ S&P 500 P/E. 섹터마다 '정상' P/E가 달라서(IT 25배, 에너지 12배) 시장 대비 프리미엄으로 봄.
- **P/E 분위** = 자기 과거 대비 몇 % 위치. 무료 데이터엔 과거 컨센서스가 없어서 **매일 스냅샷으로 쌓는 중** (20일 이상부터 표시).
"""


def render():
    hero("미국 섹터", "S&P 500 섹터 로테이션 · 이익 수정 × 주가 · 이익 vs 멀티플",
         [("🇺🇸 SPY 대비", True), ("섹터 ETF 11개", False)])
    with st.expander("📖 용어: 멀티플 · PEG · 상대 P/E · 분위", expanded=False):
        st.markdown(GLOSSARY)

    # ── RRG
    section("🔄 가격 로테이션", "RRG · SPY 대비 · 주간 · 정규화")
    px = load_etf_prices((dt.date.today() - dt.timedelta(days=3 * 365)).isoformat())
    pw = px.resample("W-FRI").last()
    ratio, mom = rrg(pw[list(SECTORS)], pw["SPY"])
    names = {c: LABELS[c] for c in ratio.columns}
    k1, k2 = st.columns([4, 1], gap="medium")
    tail = k2.slider("꼬리 (주)", 2, 12, 5, key="us_tail")
    auto = auto_focus(ratio, mom, tail=tail, k=5)
    picked = k1.pills("꼬리 볼 업종 (기본: 최근 사분면이 바뀌었거나 많이 움직인 5개 자동 선택)",
                      list(names.values()), selection_mode="multi", default=[names[c] for c in auto],
                      key=f"us_focus_{tail}")
    focus = [c for c, nm in names.items() if nm in (picked or [])]
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1, chart_box("us_rrg"):
        st.plotly_chart(rrg_figure(ratio, mom, LABELS, tail=tail, title="섹터 RRG", focus=focus), config=CHART_CFG)
    with c2, chart_box("us_rrg_tbl"):
        st.dataframe(rrg_table(ratio, mom, LABELS).style.format({"RS-Ratio": "{:.2f}", "RS-Mom": "{:.2f}"}),
                     hide_index=True, height=460)
    c2.caption("회전 방향: 개선 → 선도 → 약화 → 부진 (시계방향). '다음 섹터' 후보 = 개선 사분면에서 오른쪽으로 가는 섹터. "
               "예측력 근거는 약함 — 현황판용.")

    # ── EPS 스냅샷
    section("📊 이익 수정 × 주가 / 이익 vs 멀티플", "유진 4사분면 · 키움 표")
    today = dt.date.today().isoformat()
    snap = None
    if os.path.exists(snapshot_path(today)):
        snap = pd.read_csv(snapshot_path(today))
    else:
        prev = latest_snapshot()
        col_a, col_b = st.columns([1, 3])
        if col_a.button("📥 오늘 EPS 스냅샷 받기 (3~6분)", type="primary"):
            bar = st.progress(0.0, text="S&P 500 구성 불러오는 중…")
            snap = fetch_snapshot(bar)
            snap.to_csv(snapshot_path(snap["asof"].iloc[0]), index=False)
            bar.empty()
        elif prev is not None:
            snap = prev
            col_b.info(f"마지막 스냅샷 {prev['asof'].iloc[0]} 기준으로 표시 중")
        else:
            col_b.info("아직 스냅샷이 없어. 버튼을 누르면 S&P 500 전 종목 EPS 추정치를 받아와.")
    if snap is None:
        return

    asof = str(snap["asof"].iloc[0])
    tables = {h: sector_table(snap, h) for h in H_COLS}
    update_history(tables, asof)
    hist = load_history()

    hl = st.radio("비교 기간", list(H_COLS), index=3, horizontal=True)
    T = tables[hl]
    spx = T.loc["SPX"]
    st.caption(f"기준 {asof} · S&P 500: 12MF P/E {spx['pe_now']:.1f}배, {hl} EPS {spx['eps_chg']:+.1%}, "
               f"주가 {spx['price_chg']:+.1%} · 데이터 커버리지(시총) {spx['coverage']:.0%}")

    # 4사분면
    S = T.drop("SPX")
    fig = go.Figure()
    for lab, x0, x1, y0, y1, c in [("1 모멘텀 유지", 0, 1, 0, 1, "rgba(111,166,126,0.13)"),
                                   ("2 오버슈팅 우려", -1, 0, 0, 1, "rgba(230,180,34,0.14)"),
                                   ("3 최악", -1, 0, -1, 0, "rgba(224,122,95,0.11)"),
                                   ("4 반등 후보", 0, 1, -1, 0, "rgba(91,155,213,0.11)")]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=c, line_width=0, layer="below")
    # 꼬리: 스냅샷 이력
    if not hist.empty:
        hh = hist[(hist["h"] == hl) & (hist["sector"] != "SPX")]
        for sec, g in hh.groupby("sector"):
            g = g.sort_values("date").tail(20)
            if len(g) > 1:
                fig.add_trace(go.Scatter(x=g["eps_chg"], y=g["price_chg"], mode="lines",
                                         line=dict(width=1, color="#E3D7B2"), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=S["eps_chg"], y=S["price_chg"], mode="markers+text",
                             text=[LABELS[e] for e in S.index], textposition="top center",
                             marker=dict(size=14, color="#D9A21B", line=dict(width=2, color="white")),
                             textfont=dict(color=INK, size=12), showlegend=False,
                             hovertemplate="%{text}<br>EPS %{x:+.1%}<br>주가 %{y:+.1%}<extra></extra>"))
    lim_x = max(0.02, S["eps_chg"].abs().max() * 1.3)
    lim_y = max(0.02, S["price_chg"].abs().max() * 1.3)
    fig.add_hline(y=0, line_color="#D8C89A")
    fig.add_vline(x=0, line_color="#D8C89A")
    for txt, x, y in [("1 모멘텀 유지", 1, 1), ("2 오버슈팅 우려", -1, 1), ("3 최악", -1, -1), ("4 반등 후보", 1, -1)]:
        fig.add_annotation(x=x * lim_x * 0.8, y=y * lim_y * 0.92, text=txt, showarrow=False, font=dict(color=MUTED, size=13))
    style_fig(fig, f"유진 4사분면 — 12MF EPS 변화 × 주가 변화 ({hl})", height=520)
    fig.update_layout(hovermode="closest",
                      xaxis=dict(title=f"12MF EPS 변화 ({hl})", tickformat="+.0%", range=[-lim_x, lim_x]),
                      yaxis=dict(title=f"주가 변화 ({hl})", tickformat="+.0%", range=[-lim_y, lim_y]))
    with chart_box("us_quad"):
        st.plotly_chart(fig, config=CHART_CFG)

    # 키움 표
    pct_rank = {}
    if not hist.empty:
        hh = hist[hist["h"] == hl]
        for sec, g in hh.groupby("sector"):
            if g["date"].nunique() >= 20:
                cur = g.loc[g["date"] == asof, "pe_now"]
                if not cur.empty:
                    pct_rank[sec] = (g["pe_now"] <= cur.iloc[0]).mean()
    n_days = hist["date"].nunique() if not hist.empty else 0

    tbl = pd.DataFrame({
        "섹터": [LABELS.get(e, "S&P 500") for e in T.index],
        "유진 사분면": [quadrant(r) for _, r in T.iterrows()],
        "키움 판정": [verdict(r) for _, r in T.iterrows()],
        f"EPS Δ": T["eps_chg"], "P/E 현재": T["pe_now"], f"P/E {hl} 전": T["pe_h"], "P/E Δ": T["pe_chg"],
        "주가 Δ": T["price_chg"], "이익성장(내년)": T["growth"], "PEG": T["peg"], "상대 P/E": T["rel_pe"],
        "P/E 분위": [pct_rank.get(e, np.nan) for e in T.index], "커버리지": T["coverage"],
    }, index=T.index)

    def color_verdict(v):
        return ("background-color: #E6F2E9; color: #3F7A50; font-weight: 700" if "OW형" in str(v) else
                "background-color: #FBE5DE; color: #B8553A; font-weight: 700" if "UW형" in str(v) else "")

    with chart_box("us_kiwoom"):
        st.dataframe(tbl.style.format({
        "EPS Δ": "{:+.1%}", "P/E 현재": "{:.1f}", f"P/E {hl} 전": "{:.1f}", "P/E Δ": "{:+.1%}",
        "주가 Δ": "{:+.1%}", "이익성장(내년)": "{:+.1%}", "PEG": "{:.2f}", "상대 P/E": "{:.2f}",
        "P/E 분위": "{:.0%}", "커버리지": "{:.0%}"}, na_rep="—").map(color_verdict, subset=["키움 판정"]),
        hide_index=True)
    st.caption(f"P/E 분위는 스냅샷 20일 이상부터 표시 (현재 {n_days}일). "
               "주가 Δ = 구성종목 시총 합 변화 (ETF 수익률과 약간 다름: 캡 비중·배당). "
               "구성은 현재 S&P 500 → 과거 비교에 생존편향 있음.")
    st.download_button("⬇️ 종목 스냅샷 CSV", snap.to_csv(index=False).encode("utf-8-sig"), f"us_stocks_{asof}.csv")
