import requests
import streamlit as st


class RapidAPIError(RuntimeError):
    pass


def _secret(name: str, default=None):
    try:
        # st.secrets es dict-like
        return st.secrets.get(name, default)
    except Exception:
        return default


RAPIDAPI_KEY = _secret("RAPIDAPI_KEY")
RAPIDAPI_HOST = _secret("RAPIDAPI_HOST", "yahoo-finance15.p.rapidapi.com")
RAPIDAPI_BASE_URL = _secret("RAPIDAPI_BASE_URL", "https://yahoo-finance15.p.rapidapi.com")
RAPIDAPI_API_PREFIX = _secret("RAPIDAPI_API_PREFIX", "/api/v1")


def rapidapi_get(path: str, params: dict | None = None, timeout: int = 25) -> dict:
    if not RAPIDAPI_KEY:
        raise RapidAPIError("Falta RAPIDAPI_KEY en st.secrets (Streamlit Cloud → Settings → Secrets).")

    if not path.startswith("/"):
        path = "/" + path

    # Si te pasan /markets/... o /stock/..., le anteponemos /api/v1 automáticamente
    if RAPIDAPI_API_PREFIX and (
        path.startswith("/markets") or path.startswith("/stock")
    ):
        path = RAPIDAPI_API_PREFIX.rstrip("/") + path

    url = RAPIDAPI_BASE_URL.rstrip("/") + path

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }

    r = requests.get(url, params=params or {}, headers=headers, timeout=timeout)

    # Errores HTTP con contexto útil
    if r.status_code == 403:
        raise RapidAPIError(
            "403 Forbidden: normalmente significa que NO estás suscrito al API en RapidAPI, "
            "o el plan gratuito no permite este endpoint."
        )
    if r.status_code == 429:
        raise RapidAPIError("429 Too Many Requests: llegaste al límite del plan.")
    if r.status_code >= 400:
        snippet = (r.text or "")[:300]
        raise RapidAPIError(f"HTTP {r.status_code}. Respuesta (primeros 300 chars): {snippet}")

    # Validación JSON (tu error actual)
    try:
        return r.json()
    except ValueError:
        ct = r.headers.get("content-type", "")
        snippet = (r.text or "")[:300]
        raise RapidAPIError(
            f"La respuesta NO es JSON (content-type: {ct}). "
            f"Primeros 300 chars: {snippet}"
        )
