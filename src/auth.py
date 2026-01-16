import streamlit as st
import bcrypt
from src.db import get_user

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def login_form() -> None:
    st.markdown("## 🔒 Iniciar sesión")
    email = st.text_input("Correo", placeholder="tu@email.com")
    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar", use_container_width=True):
        u = get_user(email)
        if not u or not u["is_active"]:
            st.error("Usuario no autorizado.")
            return
        if not verify_password(password, u["password_hash"]):
            st.error("Contraseña incorrecta.")
            return

        st.session_state["user_email"] = u["email"]
        st.success("Acceso concedido.")
        st.rerun()

def require_login() -> None:
    if "user_email" not in st.session_state:
        login_form()
        st.stop()

def logout_button() -> None:
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.pop("user_email", None)
        st.rerun()

