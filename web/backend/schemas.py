from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


AnalystKey = Literal["market", "social", "news", "fundamentals"]


class TickerSearchItem(BaseModel):
    symbol: str
    name: str
    exchange: Optional[str] = None
    type: Optional[str] = None


class TickerSearchResponse(BaseModel):
    items: List[TickerSearchItem]
    total: int
    page: int
    page_size: int


class RunRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    analysis_date: date
    analysts: List[AnalystKey] = Field(default_factory=lambda: ["market", "social", "news", "fundamentals"])
    research_depth: int = Field(default=1, ge=1, le=5)
    llm_provider: str = Field(default="openai")
    shallow_thinker: str = Field(default="gpt-5.4-mini")
    deep_thinker: str = Field(default="gpt-5.4")
    backend_url: Optional[str] = None
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    anthropic_effort: Optional[str] = None
    output_language: str = Field(default="English")
    checkpoint: bool = False

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, v: str) -> str:
        s = (v or "").strip().upper()
        if s.startswith("$"):
            s = s[1:]
        return s


class RunSummary(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    ticker: str
    analysis_date: str
    created_at: str
    progress: int = 0
    cancel_requested: bool = False


class RunDetail(RunSummary):
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error: Optional[str] = None
    report_dir: Optional[str] = None
    report_files: List[str] = Field(default_factory=list)
    final_state: Optional[Dict[str, Any]] = None


class RunEvent(BaseModel):
    id: int
    run_id: str
    ts: str
    event_type: str
    payload: Dict[str, Any]


class ModelOptionsResponse(BaseModel):
    providers: List[str]
    models: Dict[str, Dict[str, List[Dict[str, str]]]]
    defaults: Optional[Dict[str, str]] = None


class ProviderCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)


class ProviderRenameRequest(BaseModel):
    new_name: str = Field(..., min_length=1)


class ModelCreateRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    mode: Literal["quick", "deep"]
    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class ModelUpdateRequest(BaseModel):
    mode: Literal["quick", "deep"]
    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)


class ModelDefaultsRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    quick_model: str = Field(..., min_length=1)
    deep_model: str = Field(..., min_length=1)


class SavedTickersRequest(BaseModel):
    items: List[TickerSearchItem] = Field(default_factory=list)
