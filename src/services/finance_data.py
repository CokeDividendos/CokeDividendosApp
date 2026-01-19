# src/services/finance_data.py
from __future__ import annotations

import re
from src.services.rapidapi_client import rapidapi_cached_get, RapidAPIError


# -----------------------------
# Helpers de parseo
# -----------------------------
def _to_float_money(s: str | None) -> float | None:
    if s is None:
        return None
    if not isinstance(s, str):
        try:
            return float(s)
        except Exception:
            return None

    cleaned = s.strip()
    cleaned = cleaned.replace("$", "").replace("€", "").replace("£", "")
    cleaned = cleaned.replace(",", "")
    cleaned = re.sub(r"[^0-9\.\-]", "", cleaned)

    try:
        return float(cleaned)
    except Exception:
        return None


def _to_float_percent(s: str | None) -> float | None:
    if s is None:
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
    if s is None:
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


def _raw_val(x):
    """Saca {raw, fmt, longFmt} -> raw si viene en dict."""
    if isinstance(x, dict):
        return x.get("raw")
    return x


# -----------------------------
# QUOTE (real-time-ish)
# -----------------------------
def _quote(ticker: str, asset_type: str = "STOCKS") -> dict:
    """
    Endpoint comprobado por tu cURL:
    /api/v1/markets/quote?ticker=AAPL&type=STOCKS
    """
    t = ticker.strip().upper()
    cache_key = f"yh:quote:{asset_type}:{t}"

    return rapidapi_cached_get(
        cache_key=cache_key,
        path="/api/v1/markets/quote",
        params={"ticker": t, "type": asset_type},
        ttl_seconds=10 * 60,     # 10 min
        error_ttl_seconds=45,
    )


def get_price_data(ticker: str, asset_type: str = "STOCKS") -> dict:
    raw = _quote(ticker, asset_type=asset_type)
    body = (raw or {}).get("body") or {}
    primary = body.get("primaryData") or {}

    last = _to_float_money(primary.get("lastSalePrice"))
    net_change = _to_float_money(primary.get("netChange"))
    pct_change = _to_float_percent(primary.get("percentageChange"))
    volume = _to_int(primary.get("volume"))
    currency = primary.get("currency")
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


# -----------------------------
# FINANCIAL DATA
# -----------------------------
def _financial_data(ticker: str) -> dict:
    """
    Endpoint que TU RapidAPI muestra 200 OK:
    GET /v1/stock/financial-data?ticker=AAPL
    """
    t = ticker.strip().upper()
    cache_key = f"yh:financial-data:{t}"

    # Guardarraíl: si alguien cambia a "modules", lo queremos ver de inmediato.
    path = "/v1/stock/financial-data"
    if "modules" in path:
        raise RapidAPIError("BUG: finance_data.py está llamando a /modules, y no debe.")

    return rapidapi_cached_get(
        cache_key=cache_key,
        path=path,
        params={"ticker": t},
        ttl_seconds=14 * 24 * 3600,  # 14 días
        error_ttl_seconds=60,
    )


def get_financial_data(ticker: str) -> dict:
    raw = _financial_data(ticker)
    body = (raw or {}).get("body") or {}

    return {
        "financial_currency": body.get("financialCurrency"),
        "current_price": _raw_val(body.get("currentPrice")),
        "target_high_price": _raw_val(body.get("targetHighPrice")),
        "target_low_price": _raw_val(body.get("targetLowPrice")),
        "target_mean_price": _raw_val(body.get("targetMeanPrice")),
        "target_median_price": _raw_val(body.get("targetMedianPrice")),
        "recommendation_key": body.get("recommendationKey"),
        "recommendation_mean": _raw_val(body.get("recommendationMean")),
        "analyst_opinions": _raw_val(body.get("numberOfAnalystOpinions")),
        "total_cash": _raw_val(body.get("totalCash")),
        "total_debt": _raw_val(body.get("totalDebt")),
        "ebitda": _raw_val(body.get("ebitda")),
        "total_revenue": _raw_val(body.get("totalRevenue")),
        "gross_profits": _raw_val(body.get("grossProfits")),
        "free_cashflow": _raw_val(body.get("freeCashflow")),
        "operating_cashflow": _raw_val(body.get("operatingCashflow")),
        "quick_ratio": _raw_val(body.get("quickRatio")),
        "current_ratio": _raw_val(body.get("currentRatio")),
        "debt_to_equity": _raw_val(body.get("debtToEquity")),
        "roe": _raw_val(body.get("returnOnEquity")),
        "roa": _raw_val(body.get("returnOnAssets")),
        "earnings_growth": _raw_val(body.get("earningsGrowth")),
        "revenue_growth": _raw_val(body.get("revenueGrowth")),
        "gross_margins": _raw_val(body.get("grossMargins")),
        "ebitda_margins": _raw_val(body.get("ebitdaMargins")),
        "operating_margins": _raw_val(body.get("operatingMargins")),
        "profit_margins": _raw_val(body.get("profitMargins")),
        "raw": raw,
    }


# -----------------------------
# PROFILE (asset-profile)
# -----------------------------
def _profile(ticker: str) -> dict:
    """
    Endpoint: GET /v1/stock/profile?ticker=AAPL
    """
    t = ticker.strip().upper()
    cache_key = f"yh:profile:{t}"

    return rapidapi_cached_get(
        cache_key=cache_key,
        path="/v1/stock/profile",
        params={"ticker": t},
        ttl_seconds=30 * 24 * 3600,  # 30 días
        error_ttl_seconds=60,
    )


def get_profile_data(ticker: str) -> dict:
    raw = _profile(ticker)
    body = (raw or {}).get("body") or {}

    return {
        "website": body.get("website"),
        "industry": body.get("industryDisp") or body.get("industry"),
        "sector": body.get("sectorDisp") or body.get("sector"),
        "employees": body.get("fullTimeEmployees"),
        "summary": body.get("longBusinessSummary"),
        "country": body.get("country"),
        "city": body.get("city"),
        "address": body.get("address1"),
        "phone": body.get("phone"),
        "raw": raw,
    }


# -----------------------------
# STATIC DATA AGGREGATOR
# -----------------------------
def get_static_data(ticker: str) -> dict:
    q = get_price_data(ticker)
    fin = get_financial_data(ticker)
    prof = get_profile_data(ticker)

    return {
        "profile": {
            "name": q.get("company_name"),
            "exchange": q.get("exchange"),
            "ticker": q.get("ticker"),
            "website": prof.get("website"),
            "sector": prof.get("sector"),
            "industry": prof.get("industry"),
        },
        "summary": {
            "business_summary": prof.get("summary"),
            "employees": prof.get("employees"),
        },
        "stats": {},
        "financial": fin,
    }
