from typing import Any
from src.clients.rapidapi_yh import RapidYHClient
from src.services.cache_store import cache_get, cache_set
from src.config import get_settings

def _ck_static(ticker: str) -> str:
    return f"static:{ticker.upper()}"

def _ck_price(ticker: str) -> str:
    return f"price:{ticker.upper()}"

def get_static_data(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    settings = get_settings()
    ck = _ck_static(ticker)
    cached = cache_get(ck)
    if cached:
        return cached

    c = RapidYHClient()
    # Endpoints típicos de YH Finance RapidAPI
    profile = c.get("stock/v2/get-profile", {"symbol": ticker, "region": "US"})
    summary = c.get("stock/v2/get-summary", {"symbol": ticker, "region": "US"})
    payload = {"profile": profile, "summary": summary}

    cache_set(ck, payload, ttl_seconds=settings.cache_ttl_static_seconds)
    return payload

def get_price_data(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper().strip()
    settings = get_settings()
    ck = _ck_price(ticker)
    cached = cache_get(ck)
    if cached:
        return cached

    c = RapidYHClient()
    quote = c.get("market/v2/get-quotes", {"symbols": ticker, "region": "US"})
    payload = {"quote": quote}

    cache_set(ck, payload, ttl_seconds=settings.cache_ttl_price_seconds)
    return payload

