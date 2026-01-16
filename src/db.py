# src/db.py
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st

DB_PATH = Path(st.secrets.get("DB_PATH", "/tmp/cokedividendosapp.sqlite"))


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # Usuarios
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    # Caché key-value
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kv_cache (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            ttl_seconds INTEGER
        )
        """
    )

    conn.commit()
    conn.close()


def get_user_by_email(email: str) -> Optional[Tuple[str, str, int]]:
    email = (email or "").strip().lower()
    if not email:
        return None

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT email, password_hash, is_active FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None
    return (row["email"], row["password_hash"], int(row["is_active"]))


def upsert_user(email: str, password_hash: str, is_active: int = 1) -> None:
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Email vacío")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users(email, password_hash, is_active)
        VALUES (?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            password_hash=excluded.password_hash,
            is_active=excluded.is_active
        """,
        (email, password_hash, int(is_active)),
    )
    conn.commit()
    conn.close()
