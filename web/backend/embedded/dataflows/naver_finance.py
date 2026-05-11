from __future__ import annotations

from datetime import datetime
from io import StringIO
from typing import Optional
import os

import pandas as pd
import requests
import urllib3


_NAVER_DAY_URL = "https://finance.naver.com/item/sise_day.naver"
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def is_kr_symbol(symbol: str) -> bool:
    s = (symbol or "").strip().upper()
    return s.endswith(".KS") or s.endswith(".KQ")


def to_naver_code(symbol: str) -> str:
    s = (symbol or "").strip().upper()
    if "." in s:
        s = s.split(".")[0]
    return s.zfill(6)


def fetch_ohlcv_naver(
    symbol: str,
    start_date: str,
    end_date: str,
    max_pages: int = 200,
) -> pd.DataFrame:
    """Fetch daily OHLCV from Naver Finance for KR symbols.

    Args:
        symbol: ticker like "005930.KS" or "005930"
        start_date: inclusive YYYY-MM-DD
        end_date: inclusive YYYY-MM-DD
    """
    code = to_naver_code(symbol)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    frames: list[pd.DataFrame] = []
    session = requests.Session()
    session.headers.update(_DEFAULT_HEADERS)
    insecure = os.getenv("INSECURE_YF", "").strip().lower() in {"1", "true", "yes", "on"}
    verify = False if insecure else True
    if insecure:
        # Local/dev override: when certificate verification is intentionally
        # disabled, suppress repetitive TLS warnings in logs.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    for page in range(1, max_pages + 1):
        resp = session.get(
            _NAVER_DAY_URL,
            params={"code": code, "page": page},
            timeout=10,
            verify=verify,
        )
        resp.raise_for_status()
        # Naver serves EUC-KR pages; decode explicitly and parse via StringIO.
        # Passing raw literal HTML directly to read_html is deprecated and can
        # be misinterpreted as a filename by downstream parsers.
        resp.encoding = "euc-kr"
        html = resp.text
        tables = pd.read_html(StringIO(html))
        if not tables:
            break
        df = tables[0]
        if "날짜" not in df.columns:
            break

        df = df.dropna()
        if df.empty:
            break

        df = df.rename(
            columns={
                "날짜": "Date",
                "시가": "Open",
                "고가": "High",
                "저가": "Low",
                "종가": "Close",
                "거래량": "Volume",
            }
        )
        # Keep only expected columns when available.
        cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        df = df[cols]
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["Date", "Close"])

        if df.empty:
            continue

        frames.append(df)

        oldest: Optional[pd.Timestamp] = df["Date"].min() if not df.empty else None
        if oldest is not None and oldest <= pd.Timestamp(start_dt):
            break

    if not frames:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    out = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["Date"], keep="first")
    out = out.sort_values("Date")
    out = out[(out["Date"] >= pd.Timestamp(start_dt)) & (out["Date"] <= pd.Timestamp(end_dt))]
    out = out.reset_index(drop=True)
    return out
