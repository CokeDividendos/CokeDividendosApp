# src/services/finance_data.py
from __future__ import annotations

from datetime import datetime, date
from typing import Any, Callable

import pandas as pd
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
    # Pandas/numpy scalars
    try:
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.floating):
            return float(x)
        if isinstance(x, np.bool_):
            return bool(x)
    except Exception:
        pass
    # Object with items
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


def _to_iso_date(v: Any) -> str | None:
    """
    Convierte epoch (seg), epoch(ms), datetime/date o str -> 'YYYY-MM-DD'
    """
    if v is None:
        return None
    try:
        if isinstance(v, (datetime, date)):
            return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
        if isinstance(v, (int, float)):
            # yfinance suele traer epoch en segundos
            # si viene muy grande asumimos ms
            ts = float(v)
            if ts > 10_000_000_000:
                ts = ts / 1000.0
            return datetime.utcfromtimestamp(ts).date().isoformat()
        if isinstance(v, str):
            # ya viene formateado
            s = v.strip()
            if len(s) >= 10:
                return s[:10]
            return s
    except Exception:
        return None
    return None


def get_price_data(ticker: str) -> dict:
    """
    Devuelve datos de precio con TTL 5 minutos.
    (Robusto ante rate-limit: si fast_info dispara error, igual intenta con history)
    """
    t = ticker.strip().upper()
    key = f"yf:quote:{t}"
    ttl = 60 * 5

    def _load():
        import yfinance as yf
        tk = yf.Ticker(t)

        # 1) Intenta fast_info, pero sin “romper” si se rate-limitea
        price = None
        currency = None
        exchange = None

        try:
            fast = yf_call(lambda: getattr(tk, "fast_info", None))
            # fast_info puede ser dict o un objeto “lazy”. Evitamos fast.get directo.
            fast_dict = {}
            if isinstance(fast, dict):
                fast_dict = fast
            else:
                # best effort: algunos tipos soportan dict()
                try:
                    fast_dict = dict(fast)  # puede fallar si está rate-limited
                except Exception:
                    fast_dict = {}

            price = fast_dict.get("last_price") or fast_dict.get("last") or None
            currency = fast_dict.get("currency") or None
            exchange = fast_dict.get("exchange") or None
        except Exception:
            # si falla, seguimos con history abajo
            pass

        # 2) history (más confiable para precio y variación diaria)
        hist = None
        try:
            hist = yf_call(lambda: tk.history(period="2d", interval="1d", auto_adjust=True))
        except Exception:
            hist = None

        net = pct = vol = asof = None
        if hist is not None and isinstance(hist, pd.DataFrame) and not hist.empty and "Close" in hist:
            try:
                last_close = float(hist["Close"].iloc[-1])
                asof = str(hist.index[-1].date())
                if "Volume" in hist:
                    try:
                        vol = int(hist["Volume"].iloc[-1])
                    except Exception:
                        vol = None

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
            "last_price": float(price) if price is not None else None,
            "net_change": float(net) if net is not None else None,
            "pct_change": float(pct) if pct is not None else None,
            "volume": vol,
            "currency": currency,
            "asof": asof,
        }

    return _cache_get_or_set(key, ttl, _load)


def get_profile_data(ticker: str) -> dict:
    """
    Perfil robusto con fallback: TTL 30 días.
    """
    t = ticker.strip().upper()
    key = f"yf:profile:{t}"
    ttl = 60 * 60 * 24 * 30

    def _load():
        import yfinance as yf
        tk = yf.Ticker(t)

        info1 = yf_call(lambda: tk.info or {}) or {}
        info2 = {}
        try:
            if hasattr(tk, "get_info"):
                info2 = yf_call(lambda: tk.get_info() or {}) or {}
        except Exception:
            pass
        info3 = {}
        try:
            info3 = yf_call(lambda: getattr(tk, "basic_info", {}) or {}) or {}
        except Exception:
            pass
        info4 = {}
        try:
            info4 = yf_call(lambda: getattr(tk, "fast_info", {}) or {}) or {}
        except Exception:
            pass
        info5 = {}
        try:
            info5 = yf_call(lambda: getattr(tk, "history_metadata", {}) or {}) or {}
        except Exception:
            pass

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
            "raw": merged,
        }

    return _cache_get_or_set(key, ttl, _load)


def get_financial_data(ticker: str) -> dict:
    """
    Snapshot financiero: TTL 90 días.
    """
    t = ticker.strip().upper()
    key = f"yf:financial:{t}"
    ttl = 60 * 60 * 24 * 90

    def _load():
        import yfinance as yf
        tk = yf.Ticker(t)
        info = yf_call(lambda: tk.info or {}) or {}
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


def get_key_stats(ticker: str) -> dict:
    """
    Devuelve Beta, PER TTM, EPS TTM y Target 1Y (con fallback).
    TTL 30 días.
    """
    t = ticker.strip().upper()
    key = f"yf:keystats:{t}"
    ttl = 60 * 60 * 24 * 30

    def _load():
        prof = get_profile_data(t)
        raw = prof.get("raw") if isinstance(prof, dict) else {}

        beta = raw.get("beta")
        pe = raw.get("trailingPE") or raw.get("peTrailingTwelveMonths")
        eps = raw.get("epsTrailingTwelveMonths") or raw.get("trailingEps")
        target = raw.get("targetMeanPrice") or raw.get("targetMedianPrice") or raw.get("targetHighPrice")

        if target is None:
            fin = get_financial_data(t)
            target = fin.get("target_mean_price")

        return {
            "beta": beta,
            "pe_ttm": pe,
            "eps_ttm": eps,
            "target_1y": target,
        }

    return _cache_get_or_set(key, ttl, _load)


# ✅ NUEVO: KPIs de Dividendos (TTL 24h)
def get_dividend_kpis(ticker: str) -> dict:
    """
    KPIs para cards de dividendos (6):
    - Dividend Yield (%): anual / precio (si posible)
    - Forward Div. Yield (%): (dividendRate / precio) o dividendYield*100
    - Dividendo Anual $: dividendRate o trailingAnnualDividendRate
    - PayOut Ratio (%): (anual / EPS TTM)*100 o payoutRatio*100
    - Ex-Date fecha: exDividendDate (YYYY-MM-DD)
    - Próximo Dividendo $: lastDividendValue (fallback)
    TTL: 24h (varía poco)
    """
    t = ticker.strip().upper()
    key = f"yf:divkpis:{t}"
    ttl = 60 * 60 * 24  # 24h

    def _load():
        prof = get_profile_data(t) or {}
        raw = prof.get("raw") if isinstance(prof, dict) else {}
        price = get_price_data(t) or {}
        stats = get_key_stats(t) or {}

        last_price = price.get("last_price")
        eps_ttm = stats.get("eps_ttm")

        # anual ($)
        annual = (
            raw.get("dividendRate")
            or raw.get("trailingAnnualDividendRate")
            or None
        )
        try:
            annual = float(annual) if annual is not None else None
        except Exception:
            annual = None

        # “próximo dividendo $” -> mejor esfuerzo sin meter llamadas extra:
        # lastDividendValue suele venir (monto del último pago)
        nxt = raw.get("lastDividendValue")
        try:
            nxt = float(nxt) if nxt is not None else None
        except Exception:
            nxt = None

        # Dividend yield (%): anual/precio
        div_yield = None
        if isinstance(last_price, (int, float)) and last_price and isinstance(annual, (int, float)):
            div_yield = (annual / float(last_price)) * 100.0

        # Forward yield (%):
        # - si existe dividendYield (decimal), úsalo
        # - sino calcula con annual/precio si annual existe
        fwd_yield = None
        dy_raw = raw.get("dividendYield")
        if isinstance(dy_raw, (int, float)):
            # suele venir como decimal (0.02 => 2%)
            fwd_yield = float(dy_raw) * 100.0
        elif div_yield is not None:
            fwd_yield = div_yield

        # Payout ratio (%):
        pr_raw = raw.get("payoutRatio")
        payout = None
        if isinstance(pr_raw, (int, float)):
            payout = float(pr_raw) * 100.0
        else:
            if isinstance(annual, (int, float)) and isinstance(eps_ttm, (int, float)) and eps_ttm:
                try:
                    payout = (float(annual) / float(eps_ttm)) * 100.0
                except Exception:
                    payout = None

        # Ex-date
        exd = _to_iso_date(raw.get("exDividendDate"))

        return {
            "dividend_yield": div_yield,
            "forward_div_yield": fwd_yield,
            "annual_dividend": annual,
            "payout_ratio": payout,
            "ex_div_date": exd,
            "next_dividend": nxt,
        }

    return _cache_get_or_set(key, ttl, _load)
