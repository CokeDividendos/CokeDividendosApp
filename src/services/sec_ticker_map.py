# src/services/sec_ticker_map.py
from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.cache_store import cache_get, cache_set
from src.services.sec_client import get_json

# Fuente oficial SEC:
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_CACHE_KEY = "sec:ticker_map:v1"
_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 días


def _normalize_ticker(t: str) -> str:
    return (t or "").strip().upper().replace(".", "-")  # BRK.B -> BRK-B


def _pad_cik(cik: Any) -> Optional[str]:
    try:
        n = int(cik)
        return f"{n:010d}"
    except Exception:
        return None


def get_ticker_map(force_refresh: bool = False) -> Dict[str, str]:
    """
    Retorna dict {TICKER: CIK10}
    """
    if not force_refresh:
        hit = cache_get(_CACHE_KEY)
        if isinstance(hit, dict) and hit:
            return hit

    data = get_json(_TICKER_MAP_URL)
    # Estructura típica: {"0": {"cik_str": 320193, "ticker": "AAPL", ...}, "1": {...}}
    out: Dict[str, str] = {}
    if isinstance(data, dict):
        for _, row in data.items():
            if not isinstance(row, dict):
                continue
            ticker = _normalize_ticker(row.get("ticker"))
            cik10 = _pad_cik(row.get("cik_str"))
            if ticker and cik10:
                out[ticker] = cik10

    cache_set(_CACHE_KEY, out, ttl_seconds=_TTL_SECONDS)
    return out


def ticker_to_cik10(ticker: str) -> Optional[str]:
    t = _normalize_ticker(ticker)
    mp = get_ticker_map(force_refresh=False)
    cik = mp.get(t)
    if cik:
        return cik

    # Fallback: refresh 1 vez
    mp = get_ticker_map(force_refresh=True)
    return mp.get(t)
