from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .db import DB
from .run_manager import RUN_MANAGER
from .schemas import (
    ModelCreateRequest,
    ModelDefaultsRequest,
    ModelOptionsResponse,
    ModelUpdateRequest,
    ProviderCreateRequest,
    ProviderRenameRequest,
    RunDetail,
    RunEvent,
    RunRequest,
    RunSummary,
    SavedTickersRequest,
    TickerSearchItem,
    TickerSearchResponse,
)
from .ticker_search import search_tickers as unified_search_tickers

app = FastAPI(title="TradingAgents Web API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/options", response_model=ModelOptionsResponse)
def options() -> ModelOptionsResponse:
    catalog = DB.get_model_catalog()
    normalized: dict[str, dict[str, list[dict[str, str]]]] = {}
    for provider in catalog["providers"]:
        modes = catalog["models"].get(provider, {})
        normalized[provider] = {
            "quick": [{"label": m["label"], "value": m["value"]} for m in modes.get("quick", [])],
            "deep": [{"label": m["label"], "value": m["value"]} for m in modes.get("deep", [])],
        }
    return ModelOptionsResponse(
        providers=catalog["providers"],
        models=normalized,
        defaults=catalog.get("defaults"),
    )


@app.get("/api/admin/model-catalog")
def get_model_catalog() -> dict[str, Any]:
    return DB.get_model_catalog()


@app.post("/api/admin/providers")
def create_provider(req: ProviderCreateRequest) -> dict[str, Any]:
    DB.create_provider(req.name)
    return {"ok": True}


@app.put("/api/admin/providers/{provider_name}")
def rename_provider(provider_name: str, req: ProviderRenameRequest) -> dict[str, Any]:
    ok = DB.rename_provider(provider_name, req.new_name.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="provider not found")
    return {"ok": True}


@app.delete("/api/admin/providers/{provider_name}")
def delete_provider(provider_name: str) -> dict[str, Any]:
    ok = DB.delete_provider(provider_name)
    if not ok:
        raise HTTPException(status_code=404, detail="provider not found")
    return {"ok": True}


@app.post("/api/admin/models")
def create_model(req: ModelCreateRequest) -> dict[str, Any]:
    model_id = DB.create_model(req.provider.strip(), req.mode, req.label.strip(), req.value.strip())
    return {"ok": True, "id": model_id}


@app.put("/api/admin/models/{model_id}")
def update_model(model_id: int, req: ModelUpdateRequest) -> dict[str, Any]:
    ok = DB.update_model(model_id, req.mode, req.label.strip(), req.value.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="model not found")
    return {"ok": True}


@app.delete("/api/admin/models/{model_id}")
def delete_model(model_id: int) -> dict[str, Any]:
    ok = DB.delete_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="model not found")
    return {"ok": True}


@app.post("/api/admin/model-defaults")
def save_model_defaults(req: ModelDefaultsRequest) -> dict[str, Any]:
    DB.set_model_defaults(req.provider.strip(), req.quick_model.strip(), req.deep_model.strip())
    return {"ok": True}


@app.get("/api/saved-tickers", response_model=list[TickerSearchItem])
def list_saved_tickers() -> list[TickerSearchItem]:
    return [TickerSearchItem(**r) for r in DB.list_saved_tickers()]


@app.post("/api/saved-tickers")
def save_tickers(req: SavedTickersRequest) -> dict[str, Any]:
    count = DB.save_tickers([i.model_dump() for i in req.items])
    return {"ok": True, "saved": count}


@app.delete("/api/saved-tickers/{symbol}")
def delete_saved_ticker(symbol: str) -> dict[str, Any]:
    ok = DB.delete_saved_ticker(symbol)
    if not ok:
        raise HTTPException(status_code=404, detail="saved ticker not found")
    return {"ok": True}


@app.get("/api/tickers/search", response_model=TickerSearchResponse)
def search_tickers(
    q: str = Query(..., min_length=1),
    market: str = Query("ALL", description="KR | US | ALL"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    max_results: int = Query(5000, ge=1, le=20000),
) -> TickerSearchResponse:
    query = q.strip()
    try:
        rows = unified_search_tickers(query, max_results=max_results, market=market)
    except Exception:
        rows = []
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    paged = rows[start:end]
    return TickerSearchResponse(
        items=[TickerSearchItem(**r) for r in paged],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.post("/api/runs", response_model=RunSummary)
def create_run(req: RunRequest) -> RunSummary:
    rec = RUN_MANAGER.create_run(req)
    return RunSummary(**rec)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    return [RunSummary(**r) for r in RUN_MANAGER.list_runs()]


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    rec = RUN_MANAGER.get_run(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="run not found")
    return RunDetail(**rec)


@app.get("/api/runs/{run_id}/events", response_model=list[RunEvent])
def get_events(
    run_id: str,
    after_id: int = 0,
    event_types: str | None = Query(None, description="Comma-separated event types"),
) -> list[RunEvent]:
    rec = RUN_MANAGER.get_run(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="run not found")
    types = [t.strip() for t in event_types.split(",")] if event_types else None
    return [RunEvent(**e) for e in RUN_MANAGER.list_events(run_id, after_id=after_id, event_types=types)]


@app.post("/api/runs/{run_id}/cancel", response_model=RunDetail)
def cancel_run(run_id: str) -> RunDetail:
    rec = RUN_MANAGER.request_cancel(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="run not found")
    return RunDetail(**rec)


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str) -> dict[str, Any]:
    ok, reason = RUN_MANAGER.delete_run(run_id)
    if not ok:
        if reason == "run not found":
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=409, detail=reason)
    return {"ok": True, "run_id": run_id}


@app.get("/api/runs/{run_id}/events/stream")
async def stream_events(
    run_id: str,
    after_id: int = 0,
    event_types: str | None = Query(None, description="Comma-separated event types"),
) -> StreamingResponse:
    rec = RUN_MANAGER.get_run(run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="run not found")

    async def gen():
        last_id = after_id
        types = [t.strip() for t in event_types.split(",")] if event_types else None
        while True:
            events = RUN_MANAGER.list_events(run_id, after_id=last_id, event_types=types)
            if events:
                for ev in events:
                    last_id = ev["id"]
                    yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                state = RUN_MANAGER.get_run(run_id)
                if state and state["status"] in {"completed", "failed"}:
                    break
            else:
                state = RUN_MANAGER.get_run(run_id)
                if state and state["status"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/runs/{run_id}/report/{report_path:path}")
def get_report_file(run_id: str, report_path: str) -> dict[str, Any]:
    rec = RUN_MANAGER.get_run(run_id)
    if not rec or rec["status"] != "completed" or not rec.get("report_dir"):
        raise HTTPException(status_code=404, detail="report not ready")

    root = Path(rec["report_dir"]).resolve()
    target = (root / report_path).resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=400, detail="invalid report path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="report file not found")
    return {"path": report_path, "content": target.read_text(encoding="utf-8")}
