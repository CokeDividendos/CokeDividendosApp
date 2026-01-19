# src/services/rapidapi_client.py
from __future__ import annotations

import random
import time
from typing import Any

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
RAPIDAPI_API_PREFIX = (_secret("RAPIDAPI_API_PREFIX", "") or "").strip()


def _build_url(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path

    prefix = RAPIDAPI_API_PREFIX
    if prefix and not prefix.startswith("/"):
        prefix = "/" + prefix

    return RAPIDAPI_BASE_URL.rstrip("/") + prefix + path


def rapidapi_get(path: str, params: dict | None = None, timeout: int = 25) -> dict:
    """
    GET robusto con:
    - retries + exponential backoff para 429 y 5xx
    - errores con snippet del body
    - validación de JSON
    """
    if not RAPIDAPI_KEY:
        raise RapidAPIError("Falta RAPIDAPI_KEY en st.secrets.")

    url = _build_url(path)

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "User-Agent": "CokeDividendosApp/1.0",
        "Accept": "application/json",
    }

    max_attempts = 4
    last_status = None
    last_text = ""

    for attempt in range(1, max_attempts + 1):
        r = requests.get(url, headers=headers, params=params or {}, timeout=timeout)
        last_status = r.status_code
        last_text = r.text or ""

        # 429 / 5xx -> retry con backoff
        if r.status_code in (429, 500, 502, 503, 504):
            if attempt == max_attempts:
                break
            sleep_s = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
            continue

        # cualquier otro status rompe el loop
        break

    # Errores HTTP (incluye 4xx)
    if last_status is None:
        raise RapidAPIError("No hubo respuesta del servidor.")
    if last_status >= 400:
        snippet = last_text[:300]
        raise RapidAPIError(f"HTTP {last_status}. Respuesta (primeros 300 chars): {snippet}")

    # JSON parse
    try:
        return r.json()
    except ValueError:
        ct = r.headers.get("content-type", "")
        snippet = last_text[:300]
        raise RapidAPIError(
            f"La respuesta NO es JSON (content-type: {ct}). Primeros 300 chars: {snippet}"
        )


def rapidapi_cached_get(
    cache_key: str,
    path: str,
    params: dict | None = None,
    ttl_seconds: int = 3600,
    error_ttl_seconds: int = 45,
) -> dict:
    """
    Wrapper con:
    - caché normal por cache_key
    - circuit breaker: si falló hace poco, no spamea RapidAPI por error_ttl_seconds
    """
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    err_key = cache_key + ":err"
    recent_err = cache_get(err_key)
    if recent_err:
        # evita martillar el endpoint cuando está caído / rate-limited
        raise RapidAPIError(str(recent_err))

    try:
        data = rapidapi_get(path, params=params)
        cache_set(cache_key, data, ttl_seconds=ttl_seconds)
        return data
    except RapidAPIError as e:
        cache_set(err_key, str(e), ttl_seconds=error_ttl_seconds)
        raise
