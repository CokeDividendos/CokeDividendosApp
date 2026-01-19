import os
from typing import Any, Dict, Optional

import requests
import streamlit as st


class RapidAPIError(RuntimeError):
    pass


def _secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Lee secretos de:
    1) st.secrets (Streamlit Cloud)
    2) variables de entorno (local / CI)
    """
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            val = st.secrets.get(name)
            return str(val) if val is not None else default
    except Exception:
        pass

    val = os.getenv(name)
    return val if val else default


RAPIDAPI_KEY = _secret("RAPIDAPI_KEY")
RAPIDAPI_HOST = _secret("RAPIDAPI_HOST", "yahoo-finance15.p.rapidapi.com")
RAPIDAPI_BASE_URL = _secret("RAPIDAPI_BASE_URL", "https://yahoo-finance15.p.rapidapi.com")


def _validate_config() -> None:
    missing = []
    if not RAPIDAPI_KEY:
        missing.append("RAPIDAPI_KEY")
    if not RAPIDAPI_HOST:
        missing.append("RAPIDAPI_HOST")
    if not RAPIDAPI_BASE_URL:
        missing.append("RAPIDAPI_BASE_URL")

    if missing:
        raise RapidAPIError(
            "Faltan secrets requeridos en st.secrets / env: " + ", ".join(missing)
        )

    # Normalizamos base URL
    if "://" not in RAPIDAPI_BASE_URL:
        raise RapidAPIError("RAPIDAPI_BASE_URL debe incluir https:// (ej: https://yahoo-finance15.p.rapidapi.com)")


def rapidapi_get(path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 25) -> Dict[str, Any]:
    """
    Llama a RapidAPI. `path` debe comenzar con '/'.
    Ej: /api/v1/markets/stock/modules
    """
    _validate_config()

    if not path.startswith("/"):
        path = "/" + path

    url = RAPIDAPI_BASE_URL.rstrip("/") + path

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
    }

    r = requests.get(url, params=params or {}, headers=headers, timeout=timeout)

    # Errores comunes con mensajes útiles
    if r.status_code == 401:
        raise RapidAPIError("401 Unauthorized: API key inválida o sin permisos.")
    if r.status_code == 403:
        raise RapidAPIError(
            "403 Forbidden. Causas típicas:\n"
            "1) No estás suscrito a esta API en RapidAPI (Subscribe).\n"
            "2) Estás usando un endpoint que tu plan no permite.\n"
            "3) El host no coincide con el producto (RAPIDAPI_HOST)."
        )
    if r.status_code == 429:
        raise RapidAPIError("429 Too Many Requests: superaste el límite del plan (rate limit).")

    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        # Incluye cuerpo si viene en JSON/texto
        body = None
        try:
            body = r.json()
        except Exception:
            body = r.text[:500]
        raise RapidAPIError(f"HTTP {r.status_code} Error: {body}") from e

    return r.json()
