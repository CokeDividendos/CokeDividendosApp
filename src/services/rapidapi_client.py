# src/services/rapidapi_client.py
from __future__ import annotations

import requests
import streamlit as st

from src.services.cache_store import cache_get, cache_set

class RapidAPIError(RuntimeError):
    pass


def _secret(name: str, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


RAPIDAPI_KEY = _secret("RAPIDAPI_KEY")
RAPIDAPI_HOST = _secret("RAPIDAPI_HOST", "yahoo-finance15.p.rapidapi.com")
RAPIDAPI_BASE_URL = _secret("RAPIDAPI_BASE_URL", "https://yahoo-finance15.p.rapidapi.com")

# OJO: por defecto VACÍO. Si quieres prefijar, lo seteas en secrets.
RAPIDAPI_API_PREFIX = _secret("RAPIDAPI_API_PREFIX", "").strip()


def rapidapi_get(path: str, params: dict | None = None, timeout: int = 25) -> dict:
    if not RAPIDAPI_KEY:
        raise RapidAPIError("Falta RAPIDAPI_KEY en st.secrets.")

    if not path.startswith("/"):
        path = "/" + path

    prefix = RAPIDAPI_API_PREFIX
    if prefix and not prefix.startswith("/"):
        prefix = "/" + prefix

    url = RAPIDAPI_BASE_URL.rstrip("/") + prefix + path

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        # ayuda a evitar bloqueos “raros”
        "User-Agent": "CokeDividendosApp/1.0",
        "Accept": "application/json",
    }

    r = requests.get(url, headers=headers, params=params or {}, timeout=timeout)

    if r.status_code >= 400:
        snippet = (r.text or "")[:300]
        raise RapidAPIError(f"HTTP {r.status_code}. Respuesta (primeros 300 chars): {snippet}")

    try:
        return r.json()
    except ValueError:
        ct = r.headers.get("content-type", "")
        snippet = (r.text or "")[:300]
        raise RapidAPIError(f"La respuesta NO es JSON (content-type: {ct}). Primeros 300 chars: {snippet}")


def rapidapi_cached_get(
    cache_key: str,
    path: str,
    params: dict | None = None,
    ttl_seconds: int = 3600,
) -> dict:
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    data = rapidapi_get(path, params=params)
    cache_set(cache_key, data, ttl_seconds=ttl_seconds)
    return data
