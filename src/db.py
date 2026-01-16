# src/db.py
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac
from pathlib import Path
from typing import Any, Dict, Optional


# Repo root = .../src/.. (porque este archivo es src/db.py)
REPO_ROOT = Path(__file__).resolve().parents[1]
USERS_PATH = REPO_ROOT / "data" / "users.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


def ensure_users_file() -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not USERS_PATH.exists():
        USERS_PATH.write_text("{}", encoding="utf-8")


def load_users() -> Dict[str, Dict[str, Any]]:
    ensure_users_file()
    try:
        raw = USERS_PATH.read_text(encoding="utf-8").strip() or "{}"
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        # Normaliza llaves a email lower
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                out[_norm_email(k)] = v
        return out
    except Exception:
        return {}


def save_users(users: Dict[str, Dict[str, Any]]) -> None:
    """
    OJO: En Streamlit Cloud, escribir archivos NO garantiza persistencia entre deploys.
    Este método sirve para uso local. En producción, debes commitear data/users.json.
    """
    ensure_users_file()
    USERS_PATH.write_text(json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8")


def hash_password(password: str, *, salt_b64: Optional[str] = None, iterations: int = 200_000) -> Dict[str, str]:
    """
    PBKDF2-HMAC-SHA256 (stdlib, sin bcrypt).
    Retorna dict con salt/hash base64.
    """
    if salt_b64:
        salt = base64.b64decode(salt_b64.encode("utf-8"))
    else:
        salt = os.urandom(16)

    dk = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    return {
        "algo": "pbkdf2_sha256",
        "iterations": str(iterations),
        "salt_b64": base64.b64encode(salt).decode("utf-8"),
        "hash_b64": base64.b64encode(dk).decode("utf-8"),
    }


def verify_password(password: str, meta: Dict[str, Any]) -> bool:
    try:
        if meta.get("algo") != "pbkdf2_sha256":
            return False
        iterations = int(meta.get("iterations", "200000"))
        salt_b64 = str(meta.get("salt_b64", ""))
        expected = str(meta.get("hash_b64", ""))
        computed = hash_password(password, salt_b64=salt_b64, iterations=iterations)["hash_b64"]
        return computed == expected
    except Exception:
        return False


def upsert_user(email: str, password: str, role: str = "user") -> Dict[str, Any]:
    email_n = _norm_email(email)
    users = load_users()
    meta = hash_password(password)
    users[email_n] = {
        "role": role,
        "created_at": _now_iso(),
        **meta,
    }
    save_users(users)
    return users[email_n]


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    email_n = _norm_email(email)
    users = load_users()
    return users.get(email_n)


def has_any_user() -> bool:
    users = load_users()
    return len(users) > 0

# --- Compatibility / App bootstrap ---
def init_db() -> None:
    """
    Compatibilidad: algunas partes del proyecto llaman init_db().
    En este diseño, solo necesitamos asegurar que exista data/users.json.
    """
    ensure_users_file()

# --- SQLite (cache + soporte futuro) ---
import os
import sqlite3
from pathlib import Path

_DB_PATH = Path("data") / "app.sqlite3"

def get_conn() -> sqlite3.Connection:
    """
    Devuelve una conexión SQLite lista para usar.
    Crea data/app.sqlite3 y las tablas necesarias si no existen.
    """
    Path("data").mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Tabla de caché (para evitar rate-limits / too many requests)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            expires_at INTEGER
        )
    """)
    conn.commit()
    return conn

# --- Compatibility / App bootstrap ---
def init_db() -> None:
    """
    Compatibilidad: el router llama init_db() al iniciar.
    Aquí aseguramos que exista el storage de usuarios y el SQLite de caché.
    """
    ensure_users_file()   # tu JSON de usuarios
    _ = get_conn()        # crea el SQLite y tabla cache si faltan
