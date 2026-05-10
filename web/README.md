# TradingAgents Web (FastAPI + React MUI)

## 포함 기능
- 기존 `TradingAgentsGraph` 재사용
- SQLite 영속화 (`web/tradingagents_web.db`)
- 실시간 스트리밍 (SSE): 에이전트 상태/메시지/툴 호출
- 기존 리포트 구조 유지 (`1_analysts`~`5_portfolio`, `complete_report.md`)
- MUI 기반 사이드바 설정 UI

## 백엔드 실행
```bash
uv run uvicorn web.backend.main:app --reload --host 0.0.0.0 --port 8005
```

## 프론트엔드 실행
```bash
cd web/frontend
npm install
npm run dev
```

## 주요 엔드포인트
- `POST /api/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/events`
- `GET /api/runs/{run_id}/events?event_types=message,tool_call` (필터)
- `GET /api/runs/{run_id}/events/stream?event_types=...` (SSE + 필터)
- `POST /api/runs/{run_id}/cancel` (실행 취소 요청)
- `GET /api/runs/{run_id}/report/{path}`
- `GET /api/tickers/search?q=...`

## 비고
- 실행 상태/이벤트는 SQLite에 저장되어 서버 재시작 후에도 조회 가능
- 실행 상세에는 진행률(`progress`)과 취소 요청 상태(`cancel_requested`)가 포함
- 리포트 파일은 기존처럼 `reports/` 디렉토리에 저장
