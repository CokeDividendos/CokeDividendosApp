# src/services/finance_data.py
from __future__ import annotations

from src.services.rapidapi_client import rapidapi_cached_get


def get_modules(ticker: str, module: str) -> dict:
    """
    Endpoint típico visto en el panel: GET /v1/stock/modules
    Params: symbol (o ticker), module
    """
    t = ticker.strip().upper()

    # TTL por tipo (ajústalo)
    ttl = 24 * 3600
    if module in ("price", "quote", "quotes", "history"):
        ttl = 15 * 60  # 15 min
    if module in ("financialData", "incomeStatementHistory", "balanceSheetHistory", "cashflowStatementHistory"):
        ttl = 7 * 24 * 3600  # 7 días
    if module in ("summaryProfile", "defaultKeyStatistics"):
        ttl = 30 * 24 * 3600  # 30 días

    cache_key = f"yh:modules:{t}:{module}"
    return rapidapi_cached_get(
        cache_key=cache_key,
        path="/v1/stock/modules",
        params={"symbol": t, "module": module},
        ttl_seconds=ttl,
    )


def get_static_data(ticker: str) -> dict:
    t = ticker.strip().upper()
    profile = get_modules(t, "summaryProfile")
    stats = get_modules(t, "defaultKeyStatistics")
    summary = get_modules(t, "summaryDetail")
    financial = get_modules(t, "financialData")

    return {
        "profile": profile,
        "stats": stats,
        "summary": summary,
        "financial": financial,
    }


def get_price_data(ticker: str) -> dict:
    t = ticker.strip().upper()
    price_raw = get_modules(t, "price")

    # Lo dejamos defensivo (depende del shape exacto de tu API)
    last_price = None
    currency = None

    try:
        # adapta según response real
        # por ejemplo: price_raw["quoteSummary"]["result"][0]["price"]["regularMarketPrice"]["raw"]
        pass
    except Exception:
        pass

    return {"last_price": last_price, "currency": currency, "raw": price_raw}
