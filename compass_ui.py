"""공통 UI: 파스텔 옐로 팔레트, 레몬 마스코트, CSS, 카드/섹션/차트 스타일 헬퍼."""
import pandas as pd
import streamlit as st


# 팔레트 (파스텔 옐로)
INK, MUTED, LINE = "#3B3529", "#8A8170", "#F1E4B8"
CARD, BUTTER, HONEY = "#FFFFFF", "#FFF3C4", "#E6B422"
GOOD, WARN, BAD = "#6FA67E", "#E6B422", "#E07A5F"
CHART_COLORS = ["#D9A21B", "#8C6D46", "#7FA88B", "#E07A5F", "#9C8AC4"]

LEMON_FACES = {
    # 안정: 웃는 눈 ^ ^ + 활짝 웃는 입
    "good": """<path d="M21.5 37 Q24.5 33.5 27.5 37" stroke="#4A3F2E" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M36.5 37 Q39.5 33.5 42.5 37" stroke="#4A3F2E" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M28 41 Q32 47 36 41 Z" fill="#D9675B"/>""",
    # 주의: 동그란 눈 + 삐뚤한 입
    "warn": """<ellipse cx="24.5" cy="36" rx="2.4" ry="3" fill="#4A3F2E"/><ellipse cx="39.5" cy="36" rx="2.4" ry="3" fill="#4A3F2E"/>
  <circle cx="25.3" cy="34.8" r="0.8" fill="#fff"/><circle cx="40.3" cy="34.8" r="0.8" fill="#fff"/>
  <path d="M28.5 43.5 Q30.5 41.8 32 43.5 Q33.5 45.2 35.5 43.5" stroke="#4A3F2E" stroke-width="1.6" fill="none" stroke-linecap="round"/>""",
    # 경계: 걱정 눈썹 + 시무룩 입 + 땀방울
    "bad": """<path d="M20 31.5 L26.5 29.5" stroke="#4A3F2E" stroke-width="1.6" stroke-linecap="round"/>
  <path d="M37.5 29.5 L44 31.5" stroke="#4A3F2E" stroke-width="1.6" stroke-linecap="round"/>
  <ellipse cx="24.5" cy="36.5" rx="2.4" ry="3" fill="#4A3F2E"/><ellipse cx="39.5" cy="36.5" rx="2.4" ry="3" fill="#4A3F2E"/>
  <circle cx="25.3" cy="35.3" r="0.8" fill="#fff"/><circle cx="40.3" cy="35.3" r="0.8" fill="#fff"/>
  <path d="M28.5 45 Q32 41.5 35.5 45" stroke="#4A3F2E" stroke-width="1.7" fill="none" stroke-linecap="round"/>
  <path d="M50 22 C48 25.5 47.5 27 49 28.3 C50.5 29.3 52.3 28 51.8 26.2 C51.5 25 50.8 23.6 50 22 Z" fill="#9ED3F0"/>""",
    # 데이터 없음: 무표정
    "none": """<ellipse cx="24.5" cy="36" rx="2.2" ry="2.8" fill="#4A3F2E"/><ellipse cx="39.5" cy="36" rx="2.2" ry="2.8" fill="#4A3F2E"/>
  <path d="M29.5 43 L34.5 43" stroke="#4A3F2E" stroke-width="1.6" stroke-linecap="round"/>""",
}


def lemon(mood="none", size=58):
    """오리지널 레몬 마스코트. mood: good / warn / bad / none"""
    return f"""<svg class="mascot" viewBox="0 0 64 64" width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">
  <path d="M35 18 C35.5 14.5 37 12.5 38.5 11" stroke="#6E9F5E" stroke-width="2" fill="none" stroke-linecap="round"/>
  <path d="M38 12 C42 7 50 7.5 52 10.5 C47.5 14.5 41.5 14.5 38 12 Z" fill="#8CC47A"/>
  <path d="M40 11.6 C44 10 48 10 51 10.6" stroke="#6E9F5E" stroke-width="0.9" fill="none" stroke-linecap="round"/>
  <path d="M5 36 C5 34 6 32.7 8.5 32 C11 22 20 17 32 17 C44 17 53 22 55.5 32 C58 32.7 59 34 59 36
           C59 38 58 39.3 55.5 40 C53 50 44 55 32 55 C20 55 11 50 8.5 40 C6 39.3 5 38 5 36 Z"
        fill="#FFE15A" stroke="#E2B023" stroke-width="2"/>
  <path d="M15 27 C18 22.5 23 20.5 28 20" stroke="#FFF5C2" stroke-width="3" fill="none" stroke-linecap="round"/>
  <circle cx="47" cy="45" r="0.9" fill="#F2C53A"/><circle cx="43" cy="49" r="0.9" fill="#F2C53A"/>
  <circle cx="50" cy="40" r="0.9" fill="#F2C53A"/><circle cx="14" cy="44" r="0.9" fill="#F2C53A"/>
  <ellipse cx="18.5" cy="42" rx="3.8" ry="2.3" fill="#F7A99A" opacity="0.6"/>
  <ellipse cx="45.5" cy="42" rx="3.8" ry="2.3" fill="#F7A99A" opacity="0.6"/>
  {LEMON_FACES.get(mood, LEMON_FACES["none"])}
</svg>"""


def inject_css():
    st.markdown(f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
    html, body, [class*="css"], .stApp, button, input, textarea, select {{
      font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', sans-serif !important;
    }}
    .stApp {{ background: linear-gradient(180deg, #FFF8DC 0%, #FFFBEA 260px); }}
    header[data-testid="stHeader"] {{ background: rgba(255, 248, 220, 0.88); backdrop-filter: blur(8px); border-bottom: 1px solid #F6EAC2; }}
    .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }}
    [data-testid="stSidebar"] {{ background: {BUTTER}; border-right: 1px solid {LINE}; }}
    #MainMenu, footer {{ visibility: hidden; }}

    .hero {{
      position: relative; overflow: hidden;
      background:
        radial-gradient(circle at 1px 1px, rgba(230,180,34,0.16) 1.2px, transparent 0) 0 0 / 18px 18px,
        linear-gradient(120deg, #FFE38A 0%, #FFF1BA 50%, #FFFDF3 100%);
      border: 1px solid #F2D77A; border-radius: 26px; padding: 28px 32px 26px 32px;
      display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 14px;
      box-shadow: 0 6px 24px rgba(214, 170, 40, 0.12); margin-bottom: 18px;
    }}
    .hero > div {{ position: relative; z-index: 1; }}
    .hero h1 {{ display: flex; align-items: center; gap: 10px; }}
    .mascot {{ display: block; filter: drop-shadow(0 3px 4px rgba(200,150,20,0.25)); }}
    .lemon-icon {{ display: inline-block; font-size: 2.1rem; line-height: 1; }}
    .hero h1 {{ font-size: 2.0rem; font-weight: 800; color: {INK}; margin: 0; padding: 0; letter-spacing: -0.02em; }}
    .hero p {{ color: {MUTED}; margin: 4px 0 0; font-size: 0.95rem; }}
    .chips {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .chip {{ background: rgba(255,255,255,0.75); border: 1px solid {LINE}; border-radius: 999px;
      padding: 5px 12px; font-size: 0.8rem; color: {INK}; white-space: nowrap; }}
    .chip b {{ font-weight: 700; }}
    .chip.live {{ background: #FFE08A; border-color: #F2CF5B; }}

    .card {{
      background: {CARD}; border: 1px solid {LINE}; border-radius: 18px; padding: 18px 20px;
      box-shadow: 0 2px 12px rgba(160, 130, 40, 0.07); box-sizing: border-box;
    }}
    .card {{ transition: transform .18s ease, box-shadow .18s ease; }}
    .card:hover {{ transform: translateY(-3px); box-shadow: 0 10px 26px rgba(214, 170, 40, 0.18); }}
    .card.gauge {{ min-height: 200px; display: flex; flex-direction: column; }}
    .card.gauge .deltas {{ margin-top: auto; }}
    .card.summary {{ min-height: 236px; }}
    .card .label {{ font-size: 0.82rem; color: {MUTED}; font-weight: 600; letter-spacing: 0.01em; }}
    .card .sub {{ font-size: 0.72rem; color: #B3A98F; margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .card-top > div {{ min-width: 0; }}
    .card .value {{ font-size: 1.75rem; font-weight: 800; color: {INK}; margin: 8px 0 6px; letter-spacing: -0.02em; }}
    .card .deltas {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .pill {{ display: inline-block; border-radius: 999px; padding: 3px 10px; font-size: 0.76rem; font-weight: 600; }}
    .pill.good {{ background: #E6F2E9; color: #3F7A50; }}
    .pill.bad  {{ background: #FBE5DE; color: #B8553A; }}
    .pill.flat {{ background: #F4EFE1; color: {MUTED}; }}
    .card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }}
    .flag {{ font-size: 0.7rem; font-weight: 700; border-radius: 8px; padding: 3px 8px; white-space: nowrap; }}
    .flag.on  {{ background: {BAD}; color: white; }}
    .flag.off {{ background: #EEF5EF; color: #4E8A5E; }}
    .card.alert {{ border-color: #F3C2B2; box-shadow: 0 2px 14px rgba(224, 122, 95, 0.12); }}
    .card.ref .value {{ font-size: 1.35rem; }}
    .card.gauge.ref {{ min-height: 140px; }}

    .big {{ font-size: 3.1rem; font-weight: 800; line-height: 1; letter-spacing: -0.03em; color: {INK}; }}
    .big small {{ font-size: 1.2rem; color: {MUTED}; font-weight: 600; }}
    .meter {{ display: flex; gap: 6px; margin: 14px 0 10px; }}
    .meter span {{ flex: 1; height: 10px; border-radius: 999px; background: #F3ECD6; }}
    .sigchips {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .sigchip {{ font-size: 0.74rem; border-radius: 999px; padding: 3px 10px; border: 1px solid {LINE}; color: {MUTED}; background: #FFFDF5; }}
    .sigchip.on {{ background: #FBE5DE; border-color: #F3C2B2; color: #B8553A; font-weight: 700; }}
    .state {{ display: inline-flex; align-items: center; gap: 10px; font-size: 1.7rem; font-weight: 800; color: {INK}; margin-top: 8px; }}
    .dot {{ width: 16px; height: 16px; border-radius: 50%; display: inline-block; box-shadow: 0 0 0 5px rgba(0,0,0,0.04); }}
    .desc {{ color: {MUTED}; font-size: 0.86rem; margin-top: 10px; line-height: 1.5; }}
    .quad {{ display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-top: 12px; }}
    .quad div {{ font-size: 0.72rem; text-align: center; padding: 5px 4px; border-radius: 8px; background: #FAF6EA; color: #B3A98F; }}
    .quad div.on {{ color: white; font-weight: 700; }}

    .section {{ display: flex; align-items: baseline; gap: 10px; margin: 28px 0 12px; }}
    .section h3 {{ font-size: 1.15rem; font-weight: 800; color: {INK}; margin: 0; padding: 0; }}
    .section span {{ font-size: 0.82rem; color: {MUTED}; }}


    [data-testid="stExpander"] details {{ background: {CARD}; border: 1px solid {LINE} !important; border-radius: 16px; }}
    [data-testid="stExpander"] summary {{ font-weight: 700; }}
    [data-testid="stExpander"] summary:hover {{ color: #B8860B; }}
    .guide h4 {{ font-size: 0.95rem; margin: 6px 0 8px; color: {INK}; }}
    .guide table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 8px; }}
    .guide td, .guide th {{ border-bottom: 1px solid #F4ECD2; padding: 7px 8px; text-align: left; vertical-align: top; }}
    .guide th {{ color: {MUTED}; font-weight: 600; font-size: 0.78rem; }}
    .guide ul {{ margin: 0; padding-left: 1.1rem; font-size: 0.86rem; line-height: 1.7; }}

    [role="tablist"] {{ gap: 8px; box-shadow: none !important; border: none !important; padding-bottom: 6px; }}
    [role="tablist"]::before, [role="tablist"]::after {{ display: none !important; }}
    [data-testid="stTab"] {{ background: #FFF6D6; border-radius: 999px; padding: 8px 20px !important;
      border: 1px solid {LINE}; box-shadow: none !important; transition: background .15s; }}
    [data-testid="stTab"]::after, [data-testid="stTab"]::before {{ display: none !important; }}
    [data-testid="stTab"]:hover {{ background: #FFEDB0; }}
    [data-testid="stTab"][data-selected="true"] {{ background: #FFE08A; border-color: #F2CF5B; }}
    .react-aria-SelectionIndicator {{ display: none !important; }}
    [data-testid="stTab"] p {{ font-weight: 700 !important; color: {INK} !important; }}
    [class*="st-key-chartbox"] {{ background: {CARD}; border-radius: 20px !important; border: 1px solid {LINE} !important;
      box-shadow: 0 2px 12px rgba(160, 130, 40, 0.07); padding: 10px 12px 4px !important; }}
    .foot {{ text-align: center; color: #B3A98F; font-size: 0.8rem; margin-top: 36px; }}
    </style>
    """, unsafe_allow_html=True)


# ───────── 헬퍼 ─────────
def pct(x): return "—" if pd.isna(x) else f"{x:+.1%}"
def bp(x): return "—" if pd.isna(x) else f"{x:+.0f}bp"


def tone(x, bad_dir):
    """변화값 x가 둔화 방향이면 bad, 반대면 good."""
    if pd.isna(x) or x == 0:
        return "flat"
    worse = (x < 0) if bad_dir == "down" else (x > 0)
    return "bad" if worse else "good"


def pill(text, cls): return f'<span class="pill {cls}">{text}</span>'


def section(title, sub=""):
    st.markdown(f'<div class="section"><h3>{title}</h3><span>{sub}</span></div>', unsafe_allow_html=True)


def gauge_card(label, sub, value, deltas, flag=None, ref=False):
    """deltas: [(텍스트, 톤)], flag: True=신호 ON / False=OFF / None=참고지표"""
    flag_html = "" if flag is None else (
        '<span class="flag on">둔화 신호</span>' if flag else '<span class="flag off">정상</span>')
    cls = "card gauge" + (" ref" if ref else "") + (" alert" if flag else "")
    return (f'<div class="{cls}"><div class="card-top"><div><div class="label">{label}</div>'
            f'<div class="sub">{sub}</div></div>{flag_html}</div>'
            f'<div class="value">{value}</div>'
            f'<div class="deltas">{"".join(pill(t, c) for t, c in deltas)}</div></div>')


def style_fig(fig, title, height=310):
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=INK), x=0.01, y=0.97),
        height=height, margin=dict(l=8, r=8, t=46, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Pretendard, sans-serif", color=MUTED, size=12),
        colorway=CHART_COLORS, hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFDF3", bordercolor=LINE, font=dict(color=INK)),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    )
    fig.update_xaxes(showgrid=False, linecolor=LINE, tickcolor=LINE)
    fig.update_yaxes(gridcolor="#F5EDD3", zeroline=False, linecolor=LINE)
    return fig


CHART_CFG = {"displayModeBar": False}



SECTOR_COLORS = ["#D9A21B", "#8C6D46", "#6FA67E", "#E07A5F", "#9C8AC4", "#5B9BD5",
                 "#E89B4C", "#C46D8E", "#4FA3A5", "#B5A642", "#7A7468", "#A65E3A"]


def hero(title, subtitle, chips=(), mood="good"):
    """페이지 상단 배너. chips: [(텍스트, live여부)]"""
    chip_html = "".join(f'<span class="chip{" live" if live else ""}">{t}</span>' for t, live in chips)
    st.markdown(f"""
<div class="hero">
  <div>
    <h1><span class="lemon-icon">🍋</span> {title}</h1>
    <p>{subtitle}</p>
  </div>
  <div class="chips">{chip_html}</div>
</div>
""", unsafe_allow_html=True)


def chart_box(key):
    """흰 카드 컨테이너 (차트·표용)."""
    return st.container(border=True, key=f"chartbox_{key}")
