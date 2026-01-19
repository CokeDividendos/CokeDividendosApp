# src/services/finance_data.py
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Dict, Callable

import pandas as pd
import math


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


def _cache_get_or_set(key: str, ttl: int, fn: Callable[[], Any]):
    hit = cache_get(key)
    if hit is not None:
        return hit
    val = fn()
    val = _json_safe(val)
    cache_set(key, val, ttl_seconds=ttl)
    return val


def _df_from_cached_records(records: Any) -> pd.DataFrame:
    if isinstance(records, list):
        return pd.DataFrame(records)
    return pd.DataFrame()


def _ensure_dt_index(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columna Date -> datetime y la deja como índice para graficar."""
    if df is None or df.empty:
        return pd.DataFrame()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"]).set_index("Date")
    elif df.index.name is None or str(df.index.dtype) != "datetime64[ns]":
        try:
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df.dropna()
        except Exception:
            pass
    return df


# -----------------------------
# PRICE (TTL 5 min)
# -----------------------------
def get_price_data(ticker: str) -> dict:
    """Precio y métricas diarias (TTL 5 min)."""
    t = ticker.strip().upper()
    key = f"yf:quote:{t}"
    ttl = 60 * 5

    def _load():
        import yfinance as yf

        tk = yf.Ticker(t)

        fast = yf_call(lambda: getattr(tk, "fast_info", {}) or {})
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
            "company_name": None,  # se llena desde profile/info
            "exchange": exchange,
            "asset_class": "STOCKS",
            "last_price": float(price) if price is not None else None,
            "net_change": float(net) if net is not None else None,
            "pct_change": float(pct) if pct is not None else None,
            "volume": vol,
            "currency": currency,
            "asof": asof,
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
            "raw": info,
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
        # guardamos como lista de dicts (JSON)
        return df.to_dict(orient="records")

    records = _cache_get_or_set(key, ttl, _load)
    df = _df_from_cached_records(records)
    df = _ensure_dt_index(df)
    return df


# -----------------------------
# DRAWDOWN (derivado del history, TTL 6h)
# -----------------------------
def get_drawdown_daily(ticker: str, years: int = 5) -> pd.DataFrame:
    t = ticker.strip().upper()
    key = f"yf:dd:{t}:{years}y"
    ttl = 60 * 60 * 6

    def _load():
        df = get_history_daily(t, years=years)
        if df is None or df.empty or "Close" not in df.columns:
            return []
        s = df["Close"].astype(float)
        peak = s.cummax()
        dd = (s / peak) - 1.0  # en proporción
        out = pd.DataFrame(
            {
                "Date": s.index,
                "Close": s.values,
                "Peak": peak.values,
                "Drawdown": dd.values,
            }
        )
        return out.to_dict(orient="records")

    records = _cache_get_or_set(key, ttl, _load)
    df = _df_from_cached_records(records)
    df = _ensure_dt_index(df.rename(columns={"Date": "Date"}))
    return df


# -----------------------------
# PERFORMANCE METRICS (TTL 6h)
# -----------------------------
def get_perf_metrics(ticker: str, years: int = 5) -> dict:
    t = ticker.strip().upper()
    key = f"yf:perf:{t}:{years}y"
    ttl = 60 * 60 * 6

    def _load():
        df = get_history_daily(t, years=years)
        if df is None or df.empty or "Close" not in df.columns:
            return {
                "years": years,
                "cagr": None,
                "volatility": None,
                "max_drawdown": None,
                "start": None,
                "end": None,
            }

        closes = df["Close"].astype(float)
        start_price = float(closes.iloc[0])
        end_price = float(closes.iloc[-1])
        start_date = closes.index[0].date().isoformat()
        end_date = closes.index[-1].date().isoformat()

        # CAGR (aprox por días)
        n_days = (closes.index[-1] - closes.index[0]).days
        years_span = n_days / 365.25 if n_days and n_days > 0 else None
        cagr = None
        if years_span and start_price > 0:
            cagr = (end_price / start_price) ** (1.0 / years_span) - 1.0

        # Vol anualizada (returns diarios)
        rets = closes.pct_change().dropna()
        vol = None
        if not rets.empty:
            vol = float(rets.std() * (252 ** 0.5))

        # Max drawdown
        peak = closes.cummax()
        dd = (closes / peak) - 1.0
        max_dd = float(dd.min()) if not dd.empty else None

        return {
            "years": years,
            "cagr": float(cagr) if cagr is not None else None,
            "volatility": float(vol) if vol is not None else None,
            "max_drawdown": float(max_dd) if max_dd is not None else None,
            "start": start_date,
            "end": end_date,
        }

    return _cache_get_or_set(key, ttl, _load)


# -----------------------------
# AGGREGATOR
# -----------------------------
def (ticker: str) -> dict:
    q = get_price_data(ticker)
    prof = get_profile_data(ticker)
    fin = get_financial_data(ticker)

    return {
        "profile": {
            "name": q.get("company_name")
            or prof.get("shortName")
            or (prof.get("raw", {}) or {}).get("shortName"),
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

# -----------------------------
# DIVIDENDS (TTL 90 días)
# -----------------------------
def get_dividends_series(ticker: str, years: int = 5) -> pd.DataFrame:
    """
    Retorna DataFrame con índice datetime y columna 'Dividend' (valores).
    Cache 90 días.
    """
    t = ticker.strip().upper()
    key = f"yf:divs:{t}:{years}y"
    ttl = 60 * 60 * 24 * 90

    def _load():
        import yfinance as yf

        tk = yf.Ticker(t)
        s = yf_call(lambda: tk.dividends)  # pandas Series
        if s is None or len(s) == 0:
            return []
        s = s.copy()
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s.dropna()
        if s.empty:
            return []
        # filtra últimos N años aprox
        cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=int(years * 365.25))
        s = s[s.index >= cutoff]
        df = pd.DataFrame({"Date": s.index, "Dividend": s.values})
        return df.to_dict(orient="records")

    records = _cache_get_or_set(key, ttl, _load)
    df = _df_from_cached_records(records)
    if df.empty:
        return pd.DataFrame()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
    return df


def get_dividends_by_year(ticker: str, years: int = 5) -> pd.DataFrame:
    """
    Suma anual de dividendos.
    """
    df = get_dividends_series(ticker, years=years)
    if df is None or df.empty:
        return pd.DataFrame()
    annual = df["Dividend"].resample("Y").sum()
    out = pd.DataFrame({"Year": annual.index.year, "Dividends": annual.values})
    out = out.sort_values("Year")
    return out


def get_dividend_metrics(ticker: str, years: int = 5) -> dict:
    """
    - Yield TTM (últimos 12 meses / precio)
    - CAGR de dividendos (aprox) usando suma anual
    """
    t = ticker.strip().upper()
    key = f"yf:divmetrics:{t}:{years}y"
    ttl = 60 * 60 * 24 * 90

    def _load():
        price = get_price_data(t)
        last_price = price.get("last_price")

        divs = get_dividends_series(t, years=years)
        if divs is None or divs.empty:
            return {
                "ttm_dividend": None,
                "ttm_yield": None,
                "div_cagr": None,
            }

        # TTM dividend
        cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(days=365)
        ttm = divs[divs.index >= cutoff]["Dividend"].sum()
        ttm = float(ttm) if ttm is not None else None

        # Yield TTM
        yld = None
        if isinstance(last_price, (int, float)) and last_price and ttm is not None:
            yld = ttm / float(last_price)

        # CAGR dividend (aprox) usando anual (primer año vs último año)
        annual = get_dividends_by_year(t, years=years)
        div_cagr = None
        if annual is not None and not annual.empty and len(annual) >= 2:
            first = float(annual["Dividends"].iloc[0])
            last = float(annual["Dividends"].iloc[-1])
            n = (annual["Year"].iloc[-1] - annual["Year"].iloc[0])
            if n > 0 and first > 0 and last > 0:
                div_cagr = (last / first) ** (1.0 / n) - 1.0

        return {
            "ttm_dividend": float(ttm) if ttm is not None else None,
            "ttm_yield": float(yld) if yld is not None else None,
            "div_cagr": float(div_cagr) if div_cagr is not None else None,
        }

    return _cache_get_or_set(key, ttl, _load)
