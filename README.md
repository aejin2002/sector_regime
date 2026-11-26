# 🍋 Regime Compass

파스텔 노랑 Streamlit 대시보드. 상단 메뉴 4개 페이지:

| 페이지 | 내용 |
|---|---|
| 🧭 크로스에셋 | 둔화 신호 5개 · 신용 전이(HY/BB/CCC) · 핵심 계기판 |
| 🇺🇸 미국 섹터 | 섹터 RRG(정규화) · 키움식 판정 · 일별 스냅샷 |
| 🇰🇷 한국 업종 | KRX 업종 RRG(동일가중/KOSPI 벤치마크) · 히트맵 |
| 🧩 레짐 전략 | SAA Regime Tilt: 성장×인플레 레짐 · 위기 오버레이 · 간단 F&G 신호 |

## 로컬 실행

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # 값 채우기
streamlit run regime_compass.py
```

## Streamlit Community Cloud 배포

1. https://share.streamlit.io → **Create app** → 이 저장소, 브랜치 `main`, Main file `regime_compass.py`
2. **Advanced settings → Secrets** 에 `.streamlit/secrets.toml.example` 형식으로 키 입력
3. Deploy

## 파일

- `regime_compass.py` — 진입점 · 크로스에셋 페이지 · 내비게이션
- `compass_ui.py` — 공통 테마/CSS/카드/차트 스타일
- `compass_common.py` — RRG 계산 공통
- `sector_us.py`, `sector_kr.py` — 섹터 페이지
- `regime_strategy.py` — 레짐 전략 페이지 UI
- `saa_strategy.py` — [SAA_REGIME_TILT](https://github.com/aejin2002/SAA_REGIME_TILT) 의 `strategy.py` (계산 엔진)
- `data/vkospi_daily.csv` — VKOSPI 캐시 (KRX API 로 자동 증분 갱신)
- `snapshots/` — 미국 섹터 일별 스냅샷 (PIT 이력)

과거 데이터·신호이며 투자 조언이 아닙니다.
