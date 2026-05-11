"""Shared yfinance client helpers.

Default behavior keeps TLS verification enabled.
Set INSECURE_YF=1 only for temporary local debugging behind intercepting proxies.
"""

from __future__ import annotations

import os
from typing import Any

import yfinance as yf


_cached_session: Any | None = None
_session_initialized = False


def _insecure_enabled() -> bool:
    return os.getenv("INSECURE_YF", "").strip().lower() in {"1", "true", "yes", "on"}


def get_yf_session() -> Any | None:
    """Return a curl_cffi session when insecure mode is enabled."""
    global _cached_session, _session_initialized

    if _session_initialized:
        return _cached_session

    _session_initialized = True
    if not _insecure_enabled():
        return None

    try:
        from curl_cffi import requests as curl_requests
    except Exception:
        return None

    session = curl_requests.Session()
    session.verify = False
    _cached_session = session
    return _cached_session


def ticker(symbol: str) -> Any:
    """Create a yfinance Ticker with optional shared insecure session."""
    session = get_yf_session()
    if session is None:
        return yf.Ticker(symbol)
    return yf.Ticker(symbol, session=session)


def download(*args: Any, **kwargs: Any) -> Any:
    """Proxy yfinance download with optional shared insecure session."""
    kwargs.setdefault("session", get_yf_session())
    return yf.download(*args, **kwargs)


def search(*args: Any, **kwargs: Any) -> Any:
    """Create yfinance Search with optional shared insecure session."""
    session = get_yf_session()
    if session is None:
        return yf.Search(*args, **kwargs)
    try:
        kwargs.setdefault("session", session)
        return yf.Search(*args, **kwargs)
    except TypeError:
        return yf.Search(*args, **kwargs)
