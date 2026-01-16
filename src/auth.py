# src/auth.py
import streamlit as st
import os
import base64
import hashlib
import hmac

from src.db import get_user_by_email


# --- Password hashing (PBKDF2) ---
# Formato: pbkdf2_sha256$<iteraciones>$<salt_b64>$<hash_b64>

_DEFAULT_ITERATIONS = 210_000  # estándar razonable para PBKDF2 en 2025 (sin volverse lento)


def hash_password(password: str, iterations: int = _DEFAULT_ITERATIONS) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    dk_b64 = base64.b64encode(dk).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${salt_b64}${dk_b64}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iter_s, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False

        iterations = int(iter_s)
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(dk_b64.encode("utf-8"))

        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# --- Auth flow ---
def require_login() -> None:
    """
    Protege la app: si no hay sesión iniciada, muestra el login y detiene el render.
    """
    if st.session_state.get("user_email"):
        return

    st.markdown(
        "<h2 style='text-align:center;'>🔒 Iniciar sesión</h2>",
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        email = st.text_input("Correo", placeholder="tucorreo@gmail.com").strip().lower()
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        row = get_user_by_email(email)
        if not row:
            st.error("Usuario no autorizado.")
            st.stop()

        # row: (email, password_hash, is_active)
        if row[2] != 1:
            st.error("Usuario desactivado.")
            st.stop()

        if not verify_password(password, row[1]):
            st.error("Contraseña incorrecta.")
            st.stop()

        st.session_state["user_email"] = email
        st.success("✅ Sesión iniciada")
        st.rerun()

    st.stop()


def logout_button() -> None:
    if st.button("🚪 Cerrar sesión", key="logout_btn"):
        st.session_state.pop("user_email", None)
        st.rerun()

