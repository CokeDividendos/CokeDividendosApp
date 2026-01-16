import requests
import streamlit as st

def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

RAPIDAPI_KEY = _secret("d9cadaced3mshe1b00a8e7bb2c9bp1639e5jsnf84e9fe23364")
RAPIDAPI_HOST = _secret("RAPIDAPI_HOST", "yahoo-finance15.p.rapidapi.com")
RAPIDAPI_BASE_URL = _secret("RAPIDAPI_BASE_URL", f"https://yahoo-finance15.p.rapidapi.com/api/v1/markets/stock/modules?ticker=AAPL&module=earnings")

class RapidAPIError(RuntimeError):
    pass

def rapidapi_get(path: str, params: dict | None = None, timeout: int = 25) -> dict:
    if not RAPIDAPI_KEY:
        raise RapidAPIError("Falta RAPIDAPI_KEY en st.secrets")

    url = RAPIDAPI_BASE_URL.rstrip("/") + path
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }

    r = requests.get(url, params=params or {}, headers=headers, timeout=timeout)

    # Mensajes más útiles que un simple traceback
    if r.status_code == 403:
        raise RapidAPIError(
            "403 Forbidden. Causas típicas:\n"
            "1) No estás suscrito a la API en RapidAPI (Subscribe to test).\n"
            "2) RAPIDAPI_HOST no coincide con el endpoint.\n"
            "3) Tu plan/free no permite ese endpoint.\n"
        )

    r.raise_for_status()
    data = r.json()
    if data is None:
        raise RapidAPIError("Respuesta vacía (JSON None).")
    return data
