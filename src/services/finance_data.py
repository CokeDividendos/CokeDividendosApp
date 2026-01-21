from __future__ import annotations

from datetime import datetime, date
from typing import Any, Callable

import numpy as np

from src.services.cache_store import cache_get, cache_set
from src.services.yf_client import install_http_cache, yf_call


class FinanceDataError(RuntimeError):
    pass


# Activa cache HTTP para yfinance
install_http_cache(expire_seconds=3600)


def _json_safe(x: Any) -> Any:
    """Convierte objetos a tipos JSON serializables."""
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

    # numpy scalars
    try:
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.floating):
            return float(x)
        if isinstance(x, np.bool_):
            return bool(x)
    except Exception:
        pass

    # dict-like
    try:
        if hasattr(x, "items"):
            return {str(k): _json_safe(v) for k, v in dict(x).items()}
    except Exception:
        pass

    return str(x)


def _cache_get_or_set(key: str, ttl: int, fn: Callable[[], Any]):
    hit = cache_get(key)
    if hit is not None:
        return hit
    val = fn()
    val = _json_safe(val)
    cache_set(key, val, ttl_seconds=ttl)
    return val


# -----------------------------
# PRICE (TTL 5 min)
# -----------------------------
def get_price_data(ticker: str) -> dict:
    t = ticker.strip().upper()
    key = f"yf:quote:{t}"
    ttl = 60 * 5

    def _load():
        import yfinance as yf

        tk = yf.Ticker(t)

        fast = {}
        try:
            fast = yf_call(lambda: getattr(tk, "fast_info", {}) or {}) or {}
        except Exception:
            fast = {}
        fast = _json_safe(fast) if isinstance(fast, (dict, list, tuple, set)) else {}

        price = fast.get("last_price") or fast.get("lastPrice") or fast.get("last")
        currency = fast.get("currency")
        exchange = fast.get("exchange")

        hist = None
        try:
            hist = yf_call(lambda: tk.history(period="2d", interval="1d", auto_adjust=True))
        except Exception:
            hist = None

        net = pct = vol = asof = None
        if hist is not None and getattr(hist, "empty", True) is False:
            try:
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
                    prev = float(hist["Close"].iloc[-2])
                    net = last_close - prev
                    pct = (net / prev) * 100 if prev else None
            except Exception:
                pass

        return {
            "ticker": t,
            "company_name": None,
            "exchange": exchange,
            "asset_class": "STOCKS",
            "last_price": float(price) if isinstance(price, (int, float)) else (float(price) if price is not None else None),
            "net_change": float(net) if isinstance(net, (int, float)) else None,
            "pct_change": float(pct) if isinstance(pct, (int, float)) else None,
            "volume": int(vol) if isinstance(vol, (int, float)) else None,
            "currency": currency,
            "asof": asof,
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

        # ✅ Siempre inicializados (evita NameError sí o sí)
        info1 = {}
        info2 = {}
        info3 = {}
        info4 = {}
        info5 = {}

        try:
            info1 = yf_call(lambda: tk.info or {}) or {}
        except Exception:
            info1 = {}

        try:
            if hasattr(tk, "get_info"):
                info2 = yf_call(lambda: tk.get_info() or {}) or {}
        except Exception:
            info2 = {}

        try:
            info3 = yf_call(lambda: getattr(tk, "basic_info", {}) or {}) or {}
        except Exception:
            info3 = {}

        try:
            info4 = yf_call(lambda: getattr(tk, "fast_info", {}) or {}) or {}
        except Exception:
            info4 = {}

        try:
            info5 = yf_call(lambda: getattr(tk, "history_metadata", {}) or {}) or {}
        except Exception:
            info5 = {}

        def merge(dicts):
            result = {}
            for d in dicts:
                if not isinstance(d, dict):
                    continue
                for k, v in d.items():
                    if k not in result or result[k] is None:
                        result[k] = v
            return result

        merged = merge([info1, info2, info3, info5, info4])
        merged = _json_safe(merged)
        if not isinstance(merged, dict):
            merged = {}

        short = merged.get("shortName") or merged.get("longName")

        return {
            "website": merged.get("website"),
            "industry": merged.get("industry"),
            "sector": merged.get("sector"),
            "longBusinessSummary": merged.get("longBusinessSummary"),
            "fullTimeEmployees": merged.get("fullTimeEmployees"),
            "country": merged.get("country"),
            "city": merged.get("city"),
            "address1": merged.get("address1"),
            "phone": merged.get("phone"),
            "shortName": short,
            "logo_url": merged.get("logo_url") or merged.get("logoUrl") or None,
            "raw": merged,
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
        info = {}
        try:
            info = yf_call(lambda: tk.info or {}) or {}
        except Exception:
            info = {}
        info = _json_safe(info)
        if not isinstance(info, dict):
            info = {}

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
# KEY STATS (TTL 30 días)
# -----------------------------
def get_key_stats(ticker: str) -> dict:
    t = ticker.strip().upper()
    key = f"yf:keystats:{t}"
    ttl = 60 * 60 * 24 * 30

    def _load():
        prof = get_profile_data(t) or {}
        raw = prof.get("raw") if isinstance(prof, dict) else {}
        if not isinstance(raw, dict):
            raw = {}

        beta = raw.get("beta")
        pe = raw.get("trailingPE") or raw.get("peTrailingTwelveMonths")
        eps = raw.get("epsTrailingTwelveMonths") or raw.get("trailingEps")
        target = raw.get("targetMeanPrice") or raw.get("targetMedianPrice") or raw.get("targetHighPrice")

        if target is None:
            fin = get_financial_data(t) or {}
            if isinstance(fin, dict):
                target = fin.get("target_mean_price")

        return {
            "beta": beta,
            "pe_ttm": pe,
            "eps_ttm": eps,
            "target_1y": target,
        }

    return _cache_get_or_set(key, ttl, _load)
