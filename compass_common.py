"""공통: RRG(상대 회전 그래프) 계산·차트, 데모 플래그, 스냅샷 폴더."""
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from compass_ui import style_fig, SECTOR_COLORS, INK, MUTED

DEMO = os.environ.get("REGIME_DEMO") == "1"
SNAP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)

# RRG 파라미터 (고정). JdK RS-Ratio/Momentum은 비공개 산식이라 공개 근사식 사용
RRG_N, RRG_M, RRG_TAIL = 10, 4, 8  # 주


RRG_SMOOTH = 3  # 주, 상대강도 평활


def _z(s: pd.DataFrame, n: int) -> pd.DataFrame:
    sd = s.rolling(n).std()
    return (s - s.rolling(n).mean()) / sd.where(sd > 0)


def rrg(prices_w: pd.DataFrame, bench_w: pd.Series, n=RRG_N, m=RRG_M, smooth=RRG_SMOOTH, normalize=True):
    """주간 종가 → (RS-Ratio, RS-Momentum). 둘 다 100 중심.
    normalize=True (기본, JdK식 근사):
      RS = 섹터/벤치를 smooth주 평활 → Ratio = 100 + z(RS, n주)
      Momentum = 100 + z(Ratio의 m주 변화, n주)  → 대략 97~103 범위로 모임
    normalize=False: 예전 식 (Ratio = 100·RS/SMA(RS,n), Momentum = 100·Ratio/Ratio(m주 전))."""
    rs = prices_w.div(bench_w, axis=0)
    if not normalize:
        ratio = 100 * rs / rs.rolling(n).mean()
        return ratio, 100 * ratio / ratio.shift(m)
    rs = rs.rolling(smooth).mean()
    ratio = 100 + _z(rs, n)
    mom = 100 + _z(ratio.diff(m), n)
    return ratio, mom


def equal_weight_bench(prices_w: pd.DataFrame) -> pd.Series:
    """업종 동일가중 지수 (주간 수익률 평균을 누적). 대형 업종 쏠림을 빼는 벤치마크."""
    ret = prices_w.pct_change(fill_method=None).mean(axis=1).fillna(0)
    return 100 * (1 + ret).cumprod()


def auto_focus(ratio: pd.DataFrame, mom: pd.DataFrame, tail=RRG_TAIL, k=5) -> list:
    """꼬리 그릴 업종 자동 선택: 최근 2주 안에 사분면이 바뀐 업종 우선, 그다음 꼬리 이동거리 큰 순."""
    r_t, m_t = ratio.tail(tail), mom.tail(tail)
    score = {}
    for c in ratio.columns:
        x, y = r_t[c], m_t[c]
        ok = x.notna() & y.notna()
        if ok.sum() < 2:
            continue
        x, y = x[ok], y[ok]
        q = [rrg_quadrant(a, b) for a, b in zip(x.tail(3), y.tail(3))]
        switched = len(set(q)) > 1
        dist = float(np.hypot(x.diff(), y.diff()).sum())
        score[c] = (switched, dist)
    return sorted(score, key=lambda c: score[c], reverse=True)[:k]


QUAD = {  # (ratio>100, mom>100)
    (True, True): "선도", (True, False): "약화", (False, False): "부진", (False, True): "개선"}


def rrg_quadrant(r, m):
    if pd.isna(r) or pd.isna(m):
        return "—"
    return QUAD[(r > 100, m > 100)]


def rrg_figure(ratio: pd.DataFrame, mom: pd.DataFrame, labels: dict, tail=RRG_TAIL, title="RRG", focus=None):
    """focus 없음: 모든 업종의 현재 위치(점+이름)만.
    focus 있음: 고른 업종만 진한 꼬리, 나머지는 회색 점."""
    fig = go.Figure()
    r_t, m_t = ratio.tail(tail), mom.tail(tail)
    cols = [c for c in ratio.columns if r_t[c].notna().any() and m_t[c].notna().any()]
    if not cols:
        return fig
    focus = [c for c in (focus or []) if c in cols]
    heads_x = pd.Series({c: r_t[c].dropna().iloc[-1] for c in cols})
    heads_y = pd.Series({c: m_t[c].dropna().iloc[-1] for c in cols})
    # 축 범위: 현재 위치 전부 + 고른 업종의 꼬리 (옅은 꼬리는 잘려도 됨)
    xs = pd.concat([heads_x, r_t[focus].stack()]) if focus else heads_x
    ys = pd.concat([heads_y, m_t[focus].stack()]) if focus else heads_y
    xa, xb = min(xs.min(), 99), max(xs.max(), 101)
    ya, yb = min(ys.min(), 99), max(ys.max(), 101)
    px_, py_ = (xb - xa) * 0.12, (yb - ya) * 0.12
    x0, x1, y0, y1 = xa - px_, xb + px_, ya - py_, yb + py_
    shades = [("선도", 100, x1, 100, y1, "rgba(111,166,126,0.13)"),
              ("약화", 100, x1, y0, 100, "rgba(230,180,34,0.14)"),
              ("부진", x0, 100, y0, 100, "rgba(224,122,95,0.11)"),
              ("개선", x0, 100, 100, y1, "rgba(91,155,213,0.11)")]
    for name, qa, qb, ra, rb, c in shades:
        fig.add_shape(type="rect", x0=qa, x1=qb, y0=ra, y1=rb, fillcolor=c, line_width=0, layer="below")
    for name, x, y, xanc, yanc in [("개선", x0, y1, "left", "top"), ("선도", x1, y1, "right", "top"),
                                   ("부진", x0, y0, "left", "bottom"), ("약화", x1, y0, "right", "bottom")]:
        fig.add_annotation(x=x, y=y, text=f"<b>{name}</b>", showarrow=False, xanchor=xanc, yanchor=yanc,
                           xshift=8 if xanc == "left" else -8, yshift=-6 if yanc == "top" else 6,
                           font=dict(size=13, color=MUTED))
    fig.add_hline(y=100, line_color="#D8C89A", line_width=1)
    fig.add_vline(x=100, line_color="#D8C89A", line_width=1)

    allcols = list(ratio.columns)
    for col in cols:
        color = SECTOR_COLORS[allcols.index(col) % len(SECTOR_COLORS)]
        name = labels.get(col, col)
        x, y = r_t[col], m_t[col]
        ok = x.notna() & y.notna()
        x, y = x[ok], y[ok]
        n = len(x)
        hov = f"{name}<br>Ratio %{{x:.2f}}<br>Mom %{{y:.2f}}<extra></extra>"
        if focus and col not in focus:      # 고르지 않은 업종: 회색 점
            fig.add_trace(go.Scatter(x=[x.iloc[-1]], y=[y.iloc[-1]], mode="markers", hovertemplate=hov,
                                     marker=dict(size=8, color="#DCD3BC", line=dict(width=1, color="white"))))
            fig.add_annotation(x=x.iloc[-1], y=y.iloc[-1], text=name, showarrow=False, yshift=11,
                               font=dict(size=10, color="#B8AE94"))
            continue
        strong = bool(focus)
        if strong:
            fig.add_trace(go.Scatter(
                x=x, y=y, mode="lines+markers", hovertemplate=hov,
                line=dict(width=2.4, color=color, shape="spline", smoothing=0.6), opacity=0.9,
                marker=dict(size=[4 + 3 * k / max(n - 1, 1) for k in range(n)], color=color,
                            opacity=[0.3 + 0.7 * k / max(n - 1, 1) for k in range(n)])))
        fig.add_trace(go.Scatter(x=[x.iloc[-1]], y=[y.iloc[-1]], mode="markers", hovertemplate=hov,
                                 marker=dict(size=14 if strong else 11, color=color,
                                             line=dict(width=2, color="white"))))
        fig.add_annotation(x=x.iloc[-1], y=y.iloc[-1], text=f"<b>{name}</b>" if strong else name,
                           showarrow=False, yshift=14, font=dict(size=12 if strong else 11, color=color if strong else INK))
    style_fig(fig, title, height=560)
    fig.update_layout(xaxis_title="RS-Ratio (상대강도 수준)", yaxis_title="RS-Momentum (상대강도 변화)",
                      xaxis_range=[x0, x1], yaxis_range=[y0, y1], showlegend=False, hovermode="closest")
    fig.update_xaxes(showgrid=True, gridcolor="#F5EDD3")
    return fig


def rrg_table(ratio, mom, labels):
    last_r, last_m = ratio.iloc[-1], mom.iloc[-1]
    prev_r, prev_m = ratio.iloc[-2], mom.iloc[-2]
    rows = []
    for c in ratio.columns:
        rows.append({"섹터": labels.get(c, c), "티커": c,
                     "현재": rrg_quadrant(last_r[c], last_m[c]),
                     "1주 전": rrg_quadrant(prev_r[c], prev_m[c]),
                     "RS-Ratio": last_r[c], "RS-Mom": last_m[c]})
    order = {"선도": 0, "약화": 1, "개선": 2, "부진": 3, "—": 4}
    df = pd.DataFrame(rows)
    return df.sort_values(["현재", "RS-Ratio"], key=lambda s: s.map(order) if s.name == "현재" else -s)


def demo_prices(cols, start, base=100.0, vol=0.012, seed=0):
    idx = pd.bdate_range(start, pd.Timestamp.today())
    rng = np.random.default_rng(seed)
    return pd.DataFrame({c: base * np.exp(np.cumsum(rng.normal(0.0002, vol, len(idx)))) for c in cols}, index=idx)
