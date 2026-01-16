import json
import time
from typing import Any, Optional
from src.db import db

def cache_get(cache_key: str) -> Optional[dict[str, Any]]:
    now = int(time.time())
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT payload_json, expires_at FROM cache WHERE cache_key=?", (cache_key,))
        row = cur.fetchone()
        if not row:
            return None
        payload_json, expires_at = row
        if expires_at <= now:
            # expirado -> limpiar
            cur.execute("DELETE FROM cache WHERE cache_key=?", (cache_key,))
            conn.commit()
            return None
        return json.loads(payload_json)

def cache_set(cache_key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
    expires_at = int(time.time()) + int(ttl_seconds)
    payload_json = json.dumps(payload, ensure_ascii=False)
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO cache(cache_key, payload_json, expires_at)
        VALUES(?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            payload_json=excluded.payload_json,
            expires_at=excluded.expires_at
        """, (cache_key, payload_json, expires_at))
        conn.commit()

def cache_clear_prefix(prefix: str) -> None:
    with db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM cache WHERE cache_key LIKE ?", (f"{prefix}%",))
        conn.commit()

def cache_clear_all() -> None:
    with db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM cache;")
        conn.commit()
