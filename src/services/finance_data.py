# src/services/finance_data.py
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict

import pandas as pd

from src.services.cache_store import cache_get, cache_set
from src.services.yf_client import install_http_cache, yf_call


class FinanceDataError(RuntimeError):
    pass


# Cache HTTP para yfinance (reduce rate-limits)
install_http_cache(expire_seconds=3600)


# -----------------------------
# JSON SAFE HELPERS
# -----------------------------
def _json_safe(x: Any) -> Any:
    """Convierte objetos a tipos JSON serializables (dict/list/str/int/float/bool/None)."""
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, (datetime, date)):
        return x.isoformat()
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_json_safe(v) for v in x]
    # pandas / numpy
    try:
        import numpy as np
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, (np.bool_,)):
            return bool(x)
    except Exception:
        pass

    # yfinance FastInfo u otros objetos "dict-like"
    try:
        if hasattr(x, "items"):
            return {str(k): _json_safe(v) for k, v in dict(x).items()}
    except Exception:
        pass

    # fallback: string
    return str(x)


def _cache_get_or_set(key: str, ttl: int, fn):
    hit = cache_get(key)
    if hit is not None:
        return hit
    val = fn()
    val = _json_safe(val)
    cache_set(key, val, ttl_seconds=ttl)
    return val


# -----------------------------
# PRICE
# -----------------------------
def get_price_data(ticker: str) -> dict:
    """Precio y métricas diarias (TTL 5 min)."""
    t = ticker.strip().upper()
    key = f"yf:quote:{t}"
    ttl = 60 * 5

    def _load():
        import yfinance as yf

        tk = yf.Ticker(t)

        # fast_info a veces es FastInfo (no JSON)
        fast = yf_call(lambda: getattr(tk, "fast_info", {}) or {})
        # hacemos dict plano
        fast_dict = _json_safe(fast)

        price = fast_dict.get("last_price") or fast_dict.get("lastPrice") or fast_dict.get("last")
        currency = fast_dict.get("currency")
        exchange = fast_dict.get("exchange")

        hist = yf_call(lambda: tk.history(period="2d", interval="1d", auto_adjust=True))
        net = pct = vol = asof = None

        if hist is not None and not hist.empty:
            last_close = float(hist["Close"].iloc[-1])
            asof = str(hist.index[-1].date())
            vol = int(hist["Volume"].iloc[-1]) if "Volume" in hist else None

            if price is None:
                price = last_close
            else:
                try:
                    price = float(price)
                except Exception:
                    price = last_close

            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                net = last_close - prev_close
                pct = (net / prev_close) * 100 if prev_close else None

        return {
            "ticker": t,
            "company_name": None,  # lo llenamos desde profile/info
            "exchange": exchange,
            "asset_class": "STOCKS",
            "last_price": float(price) if price is not None else None,
            "net_change": float(net) if net is not None else None,
            "pct_change": float(pct) if pct is not None else None,
            "volume": vol,
            "currency": currency,
            "asof": asof,
            # NO guardamos objetos raw; solo dict plano
            "debug": {"fast_info": fast_dict},
        }

    return _cache_get_or_set(key, ttl, _load)


# -----------------------------
# PROFILE (TTL 30 días)
# -----------------------------
def get_profile_data(ticker: str) -> dict:
    t = ticker.strip().upper()
    key = f"yf:profile:{t}"
    ttl = 60 * 60 * 24 * 30

    def _load():
        import yfinance as yf

        tk = yf.Ticker(t)
        info = yf_call(lambda: tk.info or {})
        info = _json_safe(info)

        return {
            "website": info.get("website"),
            "industry": info.get("industry"),
            "sector": info.get("sector"),
            "longBusinessSummary": info.get("longBusinessSummary"),
            "fullTimeEmployees": info.get("fullTimeEmployees"),
            "country": info.get("country"),
            "city": info.get("city"),
            "address1": info.get("address1"),
            "phone": info.get("phone"),
            "shortName": info.get("shortName"),
            "raw": info,  # aquí sí, porque ya lo dejamos JSON-safe
        }

    return _cache_get_or_set(key, ttl, _load)


# -----------------------------
# FINANCIAL SNAPSHOT (TTL 90 días)
# -----------------------------
def get_financial_data(ticker: str) -> dict:
    t = ticker.strip().upper()
    key = f"yf:financial:{t}"
    ttl = 60 * 60 * 24 * 90

    def _load():
        import yfinance as yf

        tk = yf.Ticker(t)
        info = yf_call(lambda: tk.info or {})
        info = _json_safe(info)

        return {
            "financial_currency": info.get("financialCurrency") or info.get("currency"),
            "current_price": info.get("currentPrice"),
            "target_mean_price": info.get("targetMeanPrice"),
            "recommendation_key": info.get("recommendationKey"),
            "analyst_opinions": info.get("numberOfAnalystOpinions"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "ebitda": info.get("ebitda"),
            "total_revenue": info.get("totalRevenue"),
            "gross_profits": info.get("grossProfits"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            "quick_ratio": info.get("quickRatio"),
            "current_ratio": info.get("currentRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "earnings_growth": info.get("earningsGrowth"),
            "revenue_growth": info.get("revenueGrowth"),
            "gross_margins": info.get("grossMargins"),
            "ebitda_margins": info.get("ebitdaMargins"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
        }

    return _cache_get_or_set(key, ttl, _load)


# -----------------------------
# HISTORY (TTL 6h)
# -----------------------------
def get_history_daily(ticker: str, years: int = 5) -> pd.DataFrame:
    t = ticker.strip().upper()
    key = f"yf:hist:{t}:{years}y"
    ttl = 60 * 60 * 6

    def _load():
        import yfinance as yf

        tk = yf.Ticker(t)
        period = f"{years}y"
        df = yf_call(lambda: tk.history(period=period, interval="1d", auto_adjust=True))
        if df is None or df.empty:
            return []
        df = df.reset_index()
        # DataFrame no es JSON → guardamos como lista de dicts
        return df.to_dict(orient="records")

    records = _cache_get_or_set(key, ttl, _load)
    if isinstance(records, list):
        return pd.DataFrame(records)
    return pd.DataFrame()


# -----------------------------
# AGGREGATOR
# -----------------------------
def get_static_data(ticker: str) -> dict:
    q = get_price_data(ticker)
    prof = get_profile_data(ticker)
    fin = get_financial_data(ticker)

    return {
        "profile": {
            "name": q.get("company_name") or prof.get("shortName") or prof.get("raw", {}).get("shortName"),
            "exchange": q.get("exchange"),
            "ticker": q.get("ticker"),
            "website": prof.get("website"),
            "sector": prof.get("sector"),
            "industry": prof.get("industry"),
        },
        "summary": {},
        "stats": {},
        "financial": fin,
    }
