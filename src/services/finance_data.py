from __future__ import annotations

from src.services.rapidapi_client import rapidapi_get, RapidAPIError

def _modules(ticker: str, module: str) -> dict:
    # Endpoint de yahoo-finance15:
    # /api/v1/markets/stock/modules?ticker=AAPL&module=earnings
    return rapidapi_get(
        "/api/v1/markets/stock/modules",
        params={"ticker": ticker, "module": module},
    )

def get_static_data(ticker: str) -> dict:
    """
    Datos que NO cambian cada segundo:
    - nombre, sector, industria, resumen, website (para logo)
    - dividendos (si vienen), ratios, etc.
    """
    ticker = ticker.strip().upper()

    # Módulos típicos de Yahoo Finance
    # (si alguno no existe en esta API, la excepción te mostrará cuál falla)
    profile = _modules(ticker, "summaryProfile")
    summary = _modules(ticker, "summaryDetail")
    stats = _modules(ticker, "defaultKeyStatistics")

    return {
        "profile": profile,
        "summary": summary,
        "stats": stats,
    }

def get_price_data(ticker: str) -> dict:
    """
    Datos que cambian más seguido:
    - price / market price
    """
    ticker = ticker.strip().upper()
    price = _modules(ticker, "price")
    return {"price": price}

def get_earnings_data(ticker: str) -> dict:
    ticker = ticker.strip().upper()
    earnings = _modules(ticker, "earnings")
    return {"earnings": earnings}
