from __future__ import annotations

import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import pandas as pd
import requests
from web.backend.tls_env import configure_tls_ca_bundle
from web.backend.yfinance_client import search as yf_search

configure_tls_ca_bundle()

from parsel import Selector


@dataclass
class SearchResult:
    symbol: str
    name: str
    exchange: str | None = None
    type: str | None = None
    source: str | None = None


_KRX_CACHE: dict[str, Any] = {"ts": 0.0, "rows": []}
_KRX_TTL_SECONDS = 60 * 60 * 24
_CACHE_FILE = Path("web/backend/data/krx_symbols.csv")
_US_CACHE_FILE = Path("web/backend/data/us_symbols.csv")
_MIN_VALID_CACHE_ROWS = 800


def _normalize_korean_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("(주)", "").replace("주식회사", "")
    s = re.sub(r"\s+", "", s)
    return s


def _tokenize_query(s: str) -> list[str]:
    raw = (s or "").strip().lower()
    # Keep Korean/English/numbers and split on spaces and punctuation.
    parts = re.split(r"[^0-9a-z가-힣]+", raw)
    return [p for p in parts if p]


def _normalize_ascii_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^0-9a-z]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _load_us_rows() -> list[dict[str, str]]:
    # 1) user-provided local universe
    if _US_CACHE_FILE.exists():
        try:
            df = pd.read_csv(_US_CACHE_FILE)
            rows: list[dict[str, str]] = []
            for _, r in df.iterrows():
                symbol = str(r.get("symbol", "")).strip().upper()
                name = str(r.get("name", "")).strip()
                exchange = str(r.get("exchange", "US")).strip() or "US"
                if not symbol or not name:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "exchange": exchange,
                        "type": "EQUITY",
                        "name_norm": _normalize_ascii_name(name),
                    }
                )
            if rows:
                return rows
        except Exception:
            pass

    # 2) built-in offline seed (major US equities/ETFs)
    seed = [
        ("AAPL", "Apple Inc.", "NASDAQ"), ("MSFT", "Microsoft Corp.", "NASDAQ"),
        ("NVDA", "NVIDIA Corp.", "NASDAQ"), ("AMZN", "Amazon.com Inc.", "NASDAQ"),
        ("GOOGL", "Alphabet Inc. Class A", "NASDAQ"), ("GOOG", "Alphabet Inc. Class C", "NASDAQ"),
        ("META", "Meta Platforms Inc.", "NASDAQ"), ("TSLA", "Tesla Inc.", "NASDAQ"),
        ("BRK.B", "Berkshire Hathaway Inc. Class B", "NYSE"), ("JPM", "JPMorgan Chase & Co.", "NYSE"),
        ("V", "Visa Inc.", "NYSE"), ("MA", "Mastercard Inc.", "NYSE"),
        ("UNH", "UnitedHealth Group Inc.", "NYSE"), ("XOM", "Exxon Mobil Corp.", "NYSE"),
        ("JNJ", "Johnson & Johnson", "NYSE"), ("PG", "Procter & Gamble Co.", "NYSE"),
        ("HD", "Home Depot Inc.", "NYSE"), ("COST", "Costco Wholesale Corp.", "NASDAQ"),
        ("ABBV", "AbbVie Inc.", "NYSE"), ("AVGO", "Broadcom Inc.", "NASDAQ"),
        ("CRM", "Salesforce Inc.", "NYSE"), ("ADBE", "Adobe Inc.", "NASDAQ"),
        ("NFLX", "Netflix Inc.", "NASDAQ"), ("AMD", "Advanced Micro Devices Inc.", "NASDAQ"),
        ("INTC", "Intel Corp.", "NASDAQ"), ("ORCL", "Oracle Corp.", "NYSE"),
        ("QCOM", "QUALCOMM Inc.", "NASDAQ"), ("CSCO", "Cisco Systems Inc.", "NASDAQ"),
        ("KO", "Coca-Cola Co.", "NYSE"), ("PEP", "PepsiCo Inc.", "NASDAQ"),
        ("MCD", "McDonald's Corp.", "NYSE"), ("NKE", "Nike Inc.", "NYSE"),
        ("PFE", "Pfizer Inc.", "NYSE"), ("T", "AT&T Inc.", "NYSE"),
        ("BAC", "Bank of America Corp.", "NYSE"), ("WFC", "Wells Fargo & Co.", "NYSE"),
        ("DIS", "Walt Disney Co.", "NYSE"), ("UBER", "Uber Technologies Inc.", "NYSE"),
        ("PLTR", "Palantir Technologies Inc.", "NYSE"), ("SNOW", "Snowflake Inc.", "NYSE"),
        ("SOFI", "SoFi Technologies Inc.", "NASDAQ"), ("COIN", "Coinbase Global Inc.", "NASDAQ"),
        ("SPY", "SPDR S&P 500 ETF Trust", "NYSEARCA"), ("QQQ", "Invesco QQQ Trust", "NASDAQ"),
        ("IWM", "iShares Russell 2000 ETF", "NYSEARCA"), ("DIA", "SPDR Dow Jones Industrial Average ETF Trust", "NYSEARCA"),
        ("VTI", "Vanguard Total Stock Market ETF", "NYSEARCA"), ("VOO", "Vanguard S&P 500 ETF", "NYSEARCA"),
    ]
    return [
        {
            "symbol": s,
            "name": n,
            "exchange": ex,
            "type": "EQUITY" if "ETF" not in n else "ETF",
            "name_norm": _normalize_ascii_name(n),
        }
        for s, n, ex in seed
    ]


def _search_us_local(query: str, max_results: int = 1000) -> list[SearchResult]:
    q = (query or "").strip()
    if not q:
        return []
    q_up = q.upper()
    qn = _normalize_ascii_name(q)
    rows = _load_us_rows()
    sym_starts, sym_contains, name_starts, name_contains = [], [], [], []
    for r in rows:
        sym = r["symbol"].upper()
        nm = r.get("name_norm", "")
        if sym.startswith(q_up):
            sym_starts.append(r)
        elif q_up in sym:
            sym_contains.append(r)
        elif nm.startswith(qn):
            name_starts.append(r)
        elif qn and qn in nm:
            name_contains.append(r)
    ranked = sym_starts + name_starts + sym_contains + name_contains
    out: list[SearchResult] = []
    seen: set[str] = set()
    for r in ranked:
        key = r["symbol"].upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            SearchResult(
                symbol=r["symbol"],
                name=r["name"],
                exchange=r.get("exchange"),
                type=r.get("type"),
                source="us_local",
            )
        )
        if len(out) >= max_results:
            break
    return out


def _load_krx_rows() -> list[dict[str, str]]:
    now = time.time()
    if _KRX_CACHE["rows"] and now - _KRX_CACHE["ts"] < _KRX_TTL_SECONDS:
        return _KRX_CACHE["rows"]

    # 0) Local cache first (works even when external network is blocked)
    cached_rows_any: list[dict[str, str]] = []
    if _CACHE_FILE.exists():
        try:
            cdf = pd.read_csv(_CACHE_FILE)
            cached_rows: list[dict[str, str]] = []
            for _, r in cdf.iterrows():
                name = str(r.get("name", "")).strip()
                symbol = str(r.get("symbol", "")).strip()
                if not name or not symbol:
                    continue
                exchange = str(r.get("exchange", "KRX")).strip()
                cached_rows.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "exchange": exchange,
                        "type": "EQUITY",
                        "name_norm": _normalize_korean_name(name),
                    }
                )
            cached_rows_any = cached_rows
            # Guardrail: prefer sufficiently large cache snapshots.
            if len(cached_rows) >= _MIN_VALID_CACHE_ROWS:
                _KRX_CACHE["rows"] = cached_rows
                _KRX_CACHE["ts"] = now
                return cached_rows
        except Exception:
            pass

    rows: list[dict[str, str]] = []

    # 1) KRX KIND corporate list (public download, no login)
    # Use POST + BytesIO parsing as it is generally more reliable than direct read_html(URL).
    try:
        url = "https://kind.krx.co.kr/corpgeneral/corpList.do"
        params = {"method": "download", "searchType": "13"}
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        res = requests.post(url, data=params, headers=headers, timeout=12)
        if res.status_code == 200 and res.content:
            df = pd.read_html(BytesIO(res.content), header=0)[0].copy()
            # Canonical KRX columns: 회사명, 종목코드, 업종, 주요제품, 상장일, 결산월
            if "종목코드" in df.columns:
                df["종목코드"] = df["종목코드"].astype(str).str.zfill(6)
            name_col = "회사명" if "회사명" in df.columns else df.columns[0]
            code_col = "종목코드" if "종목코드" in df.columns else df.columns[1]
            market_col = "시장구분" if "시장구분" in df.columns else None

            for _, row in df.iterrows():
                name = str(row.get(name_col, "")).strip()
                code = str(row.get(code_col, "")).strip()
                if not name or not code or code.lower() == "nan":
                    continue
                market = str(row.get(market_col, "")).strip() if market_col else ""
                # If market column is absent from downloaded table, default KOSPI suffix.
                suffix = ".KQ" if ("코스닥" in market or "KOSDAQ" in market.upper()) else ".KS"
                rows.append(
                    {
                        "symbol": f"{code}{suffix}",
                        "name": name,
                        "exchange": market or "KRX",
                        "type": "EQUITY",
                        "name_norm": _normalize_korean_name(name),
                    }
                )
    except Exception:
        rows = []

    # 2) Naver stock API fallback
    if not rows:
        try:
            rows = _load_naver_market_rows()
        except Exception:
            rows = []

    if rows:
        # de-duplicate by symbol
        uniq: dict[str, dict[str, str]] = {}
        for r in rows:
            uniq[r["symbol"].upper()] = r
        rows = list(uniq.values())
        if len(rows) < _MIN_VALID_CACHE_ROWS:
            # Keep in-memory for current request but avoid overwriting a better cache file.
            _KRX_CACHE["rows"] = rows
            _KRX_CACHE["ts"] = now
            return rows
        _KRX_CACHE["rows"] = rows
        _KRX_CACHE["ts"] = now
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [{"symbol": r["symbol"], "name": r["name"], "exchange": r.get("exchange", "KRX")} for r in rows]
            ).to_csv(_CACHE_FILE, index=False)
        except Exception:
            pass
        return rows

    # 3) Fallback to any cached rows (even if small) when live sources are unavailable.
    if cached_rows_any:
        _KRX_CACHE["rows"] = cached_rows_any
        _KRX_CACHE["ts"] = now
        return cached_rows_any
    return _KRX_CACHE["rows"]


def _load_naver_market_rows() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    # Known public endpoint family used by Naver stock web client.
    # We page through major Korean markets.
    for market, suffix in [("KOSPI", ".KS"), ("KOSDAQ", ".KQ"), ("KONEX", ".KQ")]:
        page = 1
        empty_streak = 0
        while page <= 80:  # safeguard upper bound
            url = f"https://api.stock.naver.com/stock/exchange/{market}/marketValue?page={page}&pageSize=100"
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                break
            data = resp.json()
            items: list[dict[str, Any]] = []
            if isinstance(data, dict):
                # Most responses contain one list payload; find it flexibly.
                for v in data.values():
                    if isinstance(v, list):
                        items = [x for x in v if isinstance(x, dict)]
                        if items:
                            break
            elif isinstance(data, list):
                items = [x for x in data if isinstance(x, dict)]

            if not items:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                page += 1
                continue
            empty_streak = 0

            for it in items:
                code = str(
                    it.get("itemCode")
                    or it.get("symbolCode")
                    or it.get("code")
                    or ""
                ).strip()
                name = str(
                    it.get("stockName")
                    or it.get("itemName")
                    or it.get("name")
                    or ""
                ).strip()
                if not code or not name:
                    continue
                code = code.zfill(6)
                out.append(
                    {
                        "symbol": f"{code}{suffix}",
                        "name": name,
                        "exchange": market,
                        "type": "EQUITY",
                        "name_norm": _normalize_korean_name(name),
                    }
                )

            page += 1

    # de-duplicate by symbol
    uniq: dict[str, dict[str, str]] = {}
    for r in out:
        uniq[r["symbol"].upper()] = r
    return list(uniq.values())


def _search_naver_html(query: str, max_results: int = 200) -> list[SearchResult]:
    """Search ticker list from Naver Finance search page (no login)."""
    q = quote_plus(query)
    url = f"https://finance.naver.com/search/searchList.naver?query={q}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=8)
    if resp.status_code != 200 or not resp.text:
        return []

    sel = Selector(text=resp.text)
    out: list[SearchResult] = []
    seen: set[str] = set()

    # Pattern from Naver Finance item links.
    for a in sel.css("a[href*='/item/main.naver?code=']"):
        href = a.attrib.get("href", "")
        m = re.search(r"code=(\d{6})", href)
        if not m:
            continue
        code = m.group(1)
        name = (a.xpath("normalize-space(string())").get() or "").strip()
        if not name:
            continue
        symbol = f"{code}.KS"
        if symbol in seen:
            continue
        seen.add(symbol)
        out.append(
            SearchResult(
                symbol=symbol,
                name=name,
                exchange="KRX",
                type="EQUITY",
                source="naver_html",
            )
        )
        if len(out) >= max_results:
            break
    return out


def _search_naver_autocomplete(query: str, max_results: int = 200) -> list[SearchResult]:
    """Search via Naver stock autocomplete endpoints (best-effort)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    urls = [
        f"https://ac.stock.naver.com/ac?query={quote_plus(query)}&q={quote_plus(query)}&r_format=json",
        f"https://m.stock.naver.com/api/search?query={quote_plus(query)}",
    ]

    out: list[SearchResult] = []
    seen: set[str] = set()

    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            continue

        # Generic recursive extraction: find dicts containing code/name-ish fields.
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                code = (
                    cur.get("itemCode")
                    or cur.get("stockCode")
                    or cur.get("code")
                    or cur.get("symbol")
                    or ""
                )
                name = (
                    cur.get("itemName")
                    or cur.get("stockName")
                    or cur.get("name")
                    or cur.get("nm")
                    or ""
                )
                code_s = str(code).strip()
                name_s = str(name).strip()
                m = re.search(r"(\d{6})", code_s)
                if m and name_s:
                    base = m.group(1)
                    symbol = f"{base}.KS"
                    if symbol not in seen:
                        seen.add(symbol)
                        out.append(
                            SearchResult(
                                symbol=symbol,
                                name=name_s,
                                exchange="KRX",
                                type="EQUITY",
                                source="naver_ac",
                            )
                        )
                        if len(out) >= max_results:
                            return out
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)
    return out


def _search_krx(query: str, max_results: int = 1000) -> list[SearchResult]:
    qn = _normalize_korean_name(query)
    q_tokens = _tokenize_query(query)
    if len(qn) < 1:
        return []

    rows = _load_krx_rows()
    starts: list[dict[str, str]] = []
    contains: list[dict[str, str]] = []
    symbol_starts: list[dict[str, str]] = []
    symbol_contains: list[dict[str, str]] = []
    for r in rows:
        nm = r.get("name_norm", "")
        sym = r.get("symbol", "").upper()
        if not nm:
            continue
        sym_up = sym.upper()
        token_match = all(tok in nm for tok in [_normalize_korean_name(t) for t in q_tokens]) if q_tokens else False
        if sym_up.startswith(query.upper()):
            symbol_starts.append(r)
        elif query.upper() in sym_up:
            symbol_contains.append(r)
        elif nm.startswith(qn):
            starts.append(r)
        elif qn in nm or token_match:
            contains.append(r)

    ranked = symbol_starts + starts + symbol_contains + contains
    out: list[SearchResult] = []
    for r in ranked[:max_results]:
        out.append(
            SearchResult(
                symbol=r["symbol"],
                name=r["name"],
                exchange=r.get("exchange"),
                type=r.get("type"),
                source="krx",
            )
        )
    return out


def _search_yfinance(query: str, max_results: int = 1000) -> list[SearchResult]:
    try:
        search = yf_search(query=query, max_results=max_results)
    except Exception:
        return []

    quotes = getattr(search, "quotes", None) or []
    out: list[SearchResult] = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol:
            continue
        out.append(
            SearchResult(
                symbol=symbol,
                name=q.get("shortname") or q.get("longname") or symbol,
                exchange=q.get("exchange"),
                type=q.get("quoteType"),
                source="yfinance",
            )
        )
    return out


def _search_yahoo_http(query: str, max_results: int = 200) -> list[SearchResult]:
    """Yahoo Finance public search endpoint (works well for US tickers/companies)."""
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    params = {
        "q": query,
        "quotesCount": max_results,
        "newsCount": 0,
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    quotes = data.get("quotes", []) if isinstance(data, dict) else []
    out: list[SearchResult] = []
    for q in quotes:
        if not isinstance(q, dict):
            continue
        symbol = str(q.get("symbol", "")).strip()
        if not symbol:
            continue
        qtype = str(q.get("quoteType", "")).upper()
        if qtype and qtype not in {"EQUITY", "ETF"}:
            continue
        out.append(
            SearchResult(
                symbol=symbol,
                name=str(q.get("shortname") or q.get("longname") or symbol).strip(),
                exchange=str(q.get("exchange") or q.get("exchDisp") or "").strip() or None,
                type=qtype or None,
                source="yahoo_http",
            )
        )
        if len(out) >= max_results:
            break
    return out


def search_tickers(
    query: str,
    max_results: int = 1000,
    market: str = "ALL",
) -> list[dict[str, str | None]]:
    query = (query or "").strip()
    if not query:
        return []

    market_norm = (market or "ALL").strip().upper()
    use_kr = market_norm in {"ALL", "KR", "KOREA", "DOMESTIC"}
    use_us = market_norm in {"ALL", "US", "USA", "AMERICA"}

    naver_html: list[SearchResult] = []
    naver_ac: list[SearchResult] = []
    krx: list[SearchResult] = []
    yf_rows: list[SearchResult] = []
    yahoo_rows: list[SearchResult] = []

    if use_kr:
        try:
            naver_html = _search_naver_html(query, max_results=max_results)
        except Exception:
            naver_html = []
        try:
            naver_ac = _search_naver_autocomplete(query, max_results=max_results)
        except Exception:
            naver_ac = []
        try:
            krx = _search_krx(query, max_results=max_results)
        except Exception:
            krx = []

    if use_us:
        try:
            yf_rows = _search_yfinance(query, max_results=max_results)
        except Exception:
            yf_rows = []
        try:
            yahoo_rows = _search_yahoo_http(query, max_results=min(max_results, 300))
        except Exception:
            yahoo_rows = []
        try:
            us_local_rows = _search_us_local(query, max_results=max_results)
        except Exception:
            us_local_rows = []
    else:
        us_local_rows = []

    merged: list[SearchResult] = []
    seen: set[str] = set()

    for item in naver_html + naver_ac + krx + yahoo_rows + yf_rows + us_local_rows:
        key = item.symbol.upper()
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= max_results:
            break

    return [
        {
            "symbol": r.symbol,
            "name": r.name,
            "exchange": r.exchange,
            "type": r.type,
        }
        for r in merged
    ]
