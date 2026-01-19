# src/services/finance_data.py
from __future__ import annotations

import re
from src.services.rapidapi_client import rapidapi_cached_get, RapidAPIError


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
        ttl_seconds=10 * 60,   # 10 min
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
# FINANCIAL DATA (fundamentals snapshot)
# -----------------------------
def _financial_data(ticker: str) -> dict:
    """
    Endpoint que en tu RapidAPI da 200 OK:
    GET /v1/stock/financial-data?ticker=AAPL
    """
    t = ticker.strip().upper()
    cache_key = f"yh:financial-data:{t}"

    return rapidapi_cached_get(
        cache_key=cache_key,
        path="/v1/stock/financial-data",
        params={"ticker": t},
        ttl_seconds=14 * 24 * 3600,  # 14 días
        error_ttl_seconds=60,
    )


def get_financial_data(ticker: str) -> dict:
    raw = _financial_data(ticker)
    body = (raw or {}).get("body") or {}

    # Helper para sacar {raw, fmt, longFmt} -> raw
    def raw_val(x):
        if isinstance(x, dict):
            return x.get("raw")
        return x

    return {
        "financial_currency": body.get("financialCurrency"),
        "current_price": raw_val(body.get("currentPrice")),
        "target_mean_price": raw_val(body.get("targetMeanPrice")),
        "recommendation_key": body.get("recommendationKey"),
        "analyst_opinions": raw_val(body.get("numberOfAnalystOpinions")),
        "total_cash": raw_val(body.get("totalCash")),
        "total_debt": raw_val(body.get("totalDebt")),
        "ebitda": raw_val(body.get("ebitda")),
        "total_revenue": raw_val(body.get("totalRevenue")),
        "gross_profits": raw_val(body.get("grossProfits")),
        "free_cashflow": raw_val(body.get("freeCashflow")),
        "operating_cashflow": raw_val(body.get("operatingCashflow")),
        "quick_ratio": raw_val(body.get("quickRatio")),
        "current_ratio": raw_val(body.get("currentRatio")),
        "debt_to_equity": raw_val(body.get("debtToEquity")),
        "roe": raw_val(body.get("returnOnEquity")),
        "roa": raw_val(body.get("returnOnAssets")),
        "earnings_growth": raw_val(body.get("earningsGrowth")),
        "revenue_growth": raw_val(body.get("revenueGrowth")),
        "gross_margins": raw_val(body.get("grossMargins")),
        "ebitda_margins": raw_val(body.get("ebitdaMargins")),
        "operating_margins": raw_val(body.get("operatingMargins")),
        "profit_margins": raw_val(body.get("profitMargins")),
        "raw": raw,
    }


# -----------------------------
# STATIC DATA AGGREGATOR
# -----------------------------
def get_static_data(ticker: str) -> dict:
    """
    Agregador para la UI.
    Por ahora: mínimos + financial-data.
    Después añadimos profile/statistics/estados/dividendos.
    """
    q = get_price_data(ticker)
    fin = get_financial_data(ticker)

    return {
        "profile": {
            "name": q.get("company_name"),
            "exchange": q.get("exchange"),
            "ticker": q.get("ticker"),
        },
        "summary": {},
        "stats": {},
        "financial": fin,
    }
