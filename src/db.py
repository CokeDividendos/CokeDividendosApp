# src/db.py
from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# -----------------------------
# DB location
# -----------------------------
def _default_db_path() -> Path:
    # project root = .../src/.. (parent of src)
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "app.sqlite3"

DB_PATH = Path(os.environ.get("COKEAPP_DB_PATH", str(_default_db_path())))

# -----------------------------
# Password hashing (stdlib only)
# -----------------------------
_PBKDF2_ITERS = 210_000
_SALT_BYTES = 16

def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("utf-8"))

def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
    if salt is None:
        salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS)
    return _b64e(salt), _b64e(dk)

def verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    salt = _b64d(salt_b64)
    _, dk_b64 = hash_password(password, salt=salt)
    # constant-time compare
    return hashlib.compare_digest(dk_b64, hash_b64)

# -----------------------------
# DB helpers
# -----------------------------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                salt_b64 TEXT NOT NULL,
                hash_b64 TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

def count_users() -> int:
    init_db()
    conn = get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        return int(row["c"]) if row else 0
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    init_db()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE lower(email)=lower(?) LIMIT 1", (email.strip(),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def create_user(email: str, password: str, *, is_admin: bool = False, is_active: bool = True) -> None:
    init_db()
    salt_b64, hash_b64 = hash_password(password)
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO users (email, salt_b64, hash_b64, is_admin, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email.strip(), salt_b64, hash_b64, 1 if is_admin else 0, 1 if is_active else 0),
        )
        conn.commit()
    finally:
        conn.close()

def set_user_active(email: str, is_active: bool) -> None:
    init_db()
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users SET is_active=? WHERE lower(email)=lower(?)",
            (1 if is_active else 0, email.strip()),
        )
        conn.commit()
    finally:
        conn.close()
