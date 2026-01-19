# src/services/finance_data.py
from __future__ import annotations

import re
from datetime import datetime

from src.services.rapidapi_client import rapidapi_cached_get, RapidAPIError


def _to_float_money(s: str | None) -> float | None:
    """
    Convierte strings tipo "$255.53" o "255.53" a float.
    Retorna None si no parsea.
    """
    if not s:
        return None
    if not isinstance(s, str):
        try:
            return float(s)
        except Exception:
            return None

    cleaned = s.strip()
    # quita símbolos de moneda y separadores
    cleaned = cleaned.replace("$", "").replace("€", "").replace("£", "")
    cleaned = cleaned.replace(",", "")  # "72,142,773"
    cleaned = cleaned.strip()

    # deja solo números, punto y signo
    cleaned = re.sub(r"[^0-9\.\-]", "", cleaned)

    try:
        return float(cleaned)
    except Exception:
        return None


def _to_float_percent(s: str | None) -> float | None:
    """Convierte '-1.04%' a -1.04"""
    if not s:
        return None
    if not isinstance(s, str):
        try:
            return float(s)
        except Exception:
            return None
    cleaned = s.strip().replace("%", "").replace(",", "")
    cleaned = re.sub(r"[^0-9\.\-]", "", cleaned)
    try:
        return float(cleaned)
    except Exception:
        return None


def _to_int(s: str | None) -> int | None:
    if not s:
        return None
    if not isinstance(s, str):
        try:
            return int(s)
        except Exception:
            return None
    cleaned = s.strip().replace(",", "")
    cleaned = re.sub(r"[^0-9\-]", "", cleaned)
    try:
        return int(cleaned)
    except Exception:
        return None


def _quotes_realtime(ticker: str, asset_type: str = "STOCKS") -> dict:
    """
    Endpoint según tu cURL:
    https://yahoo-finance15.p.rapidapi.com/api/v1/markets/quote?ticker=AAPL&type=STOCKS
    """
    t = ticker.strip().upper()
    cache_key = f"yh:quote:{asset_type}:{t}"

    return rapidapi_cached_get(
        cache_key=cache_key,
        path="/api/v1/markets/quote",
        params={"ticker": t, "type": asset_type},
        ttl_seconds=10 * 60,
    )



def get_price_data(ticker: str, asset_type: str = "STOCKS") -> dict:
    raw = _quotes_realtime(ticker, asset_type=asset_type)

    body = (raw or {}).get("body") or {}
    primary = body.get("primaryData") or {}

    last = _to_float_money(primary.get("lastSalePrice"))
    net_change = _to_float_money(primary.get("netChange"))
    pct_change = _to_float_percent(primary.get("percentageChange"))
    volume = _to_int(primary.get("volume"))
    currency = primary.get("currency")  # en tu ejemplo viene null

    asof = primary.get("lastTradeTimestamp") or None

    return {
        "ticker": body.get("symbol") or ticker.strip().upper(),
        "company_name": body.get("companyName"),
        "exchange": body.get("exchange"),
        "asset_class": body.get("assetClass"),
        "last_price": last,
        "net_change": net_change,
        "pct_change": pct_change,
        "volume": volume,
        "currency": currency,
        "asof": asof,
        "raw": raw,
    }


# --- Stubs (para que no se caiga tu UI mientras conectamos fundamentals) ---
def get_static_data(ticker: str) -> dict:
    """
    De momento devolvemos mínimos desde el mismo quote.
    Luego conectamos endpoints: /v1/stock/profile, /v1/stock/statistics,
    /v1/stock/financial-data, /v1/stock/sec-filings, etc.
    """
    q = get_price_data(ticker)
    return {
        "profile": {
            "name": q.get("company_name"),
            "exchange": q.get("exchange"),
        },
        "summary": {},
        "stats": {},
        "financial": {},
    }
