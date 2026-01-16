import sqlite3
from contextlib import contextmanager
from typing import Optional, Any
from src.config import get_settings

def _connect():
    settings = get_settings()
    return sqlite3.connect(settings.db_path, check_same_thread=False)

@contextmanager
def db():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()

def init_db() -> None:
    with db() as conn:
        cur = conn.cursor()

        # Usuarios
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)

        # Cache persistente (2 tipos: static y price)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        );
        """)
        conn.commit()

def get_user(email: str) -> Optional[dict[str, Any]]:
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT email, password_hash, is_active FROM users WHERE email = ?", (email.lower().strip(),))
        row = cur.fetchone()
        if not row:
            return None
        return {"email": row[0], "password_hash": row[1], "is_active": bool(row[2])}

def upsert_user(email: str, password_hash: str, is_active: bool = True) -> None:
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO users(email, password_hash, is_active)
        VALUES(?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            password_hash=excluded.password_hash,
            is_active=excluded.is_active
        """, (email.lower().strip(), password_hash, 1 if is_active else 0))
        conn.commit()

