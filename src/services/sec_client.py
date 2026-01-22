# src/services/sec_client.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests

# Rate limit suave (SEC sugiere ~10 req/s máx). Usamos 4-5 req/s.
_MIN_INTERVAL_SEC = 0.25
_last_call_ts = 0.0


class SecClientError(RuntimeError):
    pass


def _user_agent() -> str:
    """
    SEC requiere User-Agent identificable.
    Puedes setear SEC_USER_AGENT en secrets/env.
    """
    return os.getenv(
        "SEC_USER_AGENT",
        "CokeDividendosApp/1.0 (contacto@cokedividendos.com)",
    )


def _throttle():
    global _last_call_ts
    now = time.time()
    wait = _MIN_INTERVAL_SEC - (now - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.time()


def get_json(url: str, timeout: int = 20) -> Dict[str, Any]:
    """
    GET JSON robusto + rate limit + headers SEC.
    """
    _throttle()
    headers = {
        "User-Agent": _user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code >= 400:
            raise SecClientError(f"SEC {r.status_code}: {url}")
        return r.json()
    except Exception as e:
        raise SecClientError(f"SEC request failed: {e}") from e
