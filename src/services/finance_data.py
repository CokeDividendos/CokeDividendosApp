# src/services/finance_data.py
from __future__ import annotations

from datetime import datetime
import pandas as pd

from src.services.cache_store import cache_get, cache_set
from src.services.yf_client import install_http_cache, yf_call, YFError


# Instala cache HTTP (1h) al importar el módulo
install_http_cache(expire_seconds=3600)


class FinanceDataError(RuntimeError):
    pass


def _cache_get_or_set(key: str, ttl: int, fn):
    hit = cache_get(key)
    if hit is not None:
        return hit
    try:
        val = fn()
    except Exception as e:
        raise FinanceDataError(str(e))
    cache_set(key, val, ttl_seconds=ttl)
    return val


def get_price_data(ticker: str) -> dict:
    t = ticker.strip().upper()
    key = f"yf:quote:{t}"
    ttl = 60 * 5  # 5 min

    def _load():
        import yfinance as yf
        tk = yf.Ticker(t)

        # fast_info suele ser más liviano que info
        fast = yf_call(lambda: getattr(tk, "fast_info", {}) or {})
        price = fast.get("last_price") or fast.get("lastPrice") or fast.get("last_price")
        currency = fast.get("currency")
        # cambios del día: a veces no vienen; se puede calcular desde history 2d
        hist = yf_call(lambda: tk.history(period="2d", interval="1d"))
        net = pct = vol = asof = None
        if hist is not None and len(hist) >= 1:
            last_close = float(hist["Close"].iloc[-1])
            asof = str(hist.index[-1].date())
            vol = int(hist["Volume"].iloc[-1]) if "Volume" in hist else None
            price = float(price) if price is not None else last_close
            if len(hist) >= 2:
                prev_close = float(hist["Close"].iloc[-2])
                net = last_close - prev_close
                pct = (net / prev_close) * 100 if prev_close else None

        return {
            "ticker": t,
            "company_name": None,
            "exchange": fast.get("exchange"),
            "asset_class": "STOCKS",
            "last_price": float(price) if price is not None else None,
            "net_change": float(net) if net is not None else None,
            "pct_change": float(pct) if pct is not None else None,
            "volume": vol,
            "currency": currency,
            "asof": asof,
            "raw": {"fast_info": fast},
        }

    return _cache_get_or_set(key, ttl, _load)


def get_profile_data(ticker: str) -> dict:
    t = ticker.strip().upper()
    key = f"yf:profile:{t}"
    ttl = 60 * 60 * 24 * 7  # 7 días

    def _load():
        import yfinance as yf
        tk = yf.Ticker(t)
        info = yf_call(lambda: tk.info or {})
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
            "raw": info,
        }

    return _cache_get_or_set(key, ttl, _load)


def get_financial_data(ticker: str) -> dict:
    """
    Snapshot de ratios/valorización (lo más cercano a tu 'financial-data').
    """
    t = ticker.strip().upper()
    key = f"yf:financial:{t}"
    ttl = 60 * 60 * 24  # 1 día

    def _load():
        import yfinance as yf
        tk = yf.Ticker(t)
        info = yf_call(lambda: tk.info or {})

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
            "raw": info,
        }

    return _cache_get_or_set(key, ttl, _load)


def get_history_daily(ticker: str, years: int = 5) -> pd.DataFrame:
    """
    Histórico diario para gráficos/rentabilidad/etc.
    """
    t = ticker.strip().upper()
    key = f"yf:hist:{t}:{years}y"
    ttl = 60 * 60 * 6  # 6h

    def _load():
        import yfinance as yf
        tk = yf.Ticker(t)
        period = f"{years}y"
        df = yf_call(lambda: tk.history(period=period, interval="1d", auto_adjust=True))
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        return df

    return _cache_get_or_set(key, ttl, _load)


def get_static_data(ticker: str) -> dict:
    """
    Agregador para tu UI.
    """
    q = get_price_data(ticker)
    prof = get_profile_data(ticker)
    fin = get_financial_data(ticker)

    return {
        "profile": {
            "name": q.get("company_name") or prof.get("raw", {}).get("shortName"),
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
