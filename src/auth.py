# src/auth.py
from __future__ import annotations

import streamlit as st
from typing import Optional, Dict, Any

from .db import (
    count_users,
    create_user,
    get_user_by_email,
    verify_password,
    init_db,
)

SESSION_KEY = "auth_user"  # dict con email/is_admin/is_active


def _set_user_session(user: Dict[str, Any]) -> None:
    st.session_state[SESSION_KEY] = {
        "email": user["email"],
        "is_admin": bool(user.get("is_admin", 0)),
        "is_active": bool(user.get("is_active", 1)),
    }


def current_user() -> Optional[Dict[str, Any]]:
    return st.session_state.get(SESSION_KEY)


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)
    # rerun para que se muestre el login
    st.rerun()


def require_login() -> bool:
    """
    Retorna True si el usuario está autenticado.
    Si NO hay usuarios en la DB, muestra pantalla de creación del primer admin.
    """
    init_db()

    user = current_user()
    if user and user.get("is_active", False):
        return True

    # 1) Bootstrap: si no hay usuarios aún, crear admin
    if count_users() == 0:
        st.markdown("## 🛠️ Configuración inicial")
        st.info("No hay usuarios creados. Crea el **primer administrador** para habilitar el acceso.")
        with st.form("create_admin", clear_on_submit=False):
            email = st.text_input("Correo (admin)", value="cokedividendos@gmail.com")
            password = st.text_input("Contraseña (admin)", type="password")
            password2 = st.text_input("Repite la contraseña", type="password")
            submitted = st.form_submit_button("Crear administrador")
        if submitted:
            if not email.strip():
                st.error("El correo es obligatorio.")
                return False
            if not password:
                st.error("La contraseña es obligatoria.")
                return False
            if password != password2:
                st.error("Las contraseñas no coinciden.")
                return False

            # crear admin
            create_user(email=email.strip(), password=password, is_admin=True, is_active=True)
            user_db = get_user_by_email(email.strip())
            _set_user_session(user_db)
            st.success("Administrador creado. Entrando…")
            st.rerun()

        return False

    # 2) Login normal
    st.markdown("## 🔐 Iniciar sesión")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Correo", value="tucorreo@gmail.com")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        u = get_user_by_email(email.strip())
        if not u:
            st.error("Correo o contraseña incorrectos.")
            return False
        if not bool(u.get("is_active", 1)):
            st.error("Tu cuenta está desactivada.")
            return False

        ok = verify_password(password, u["salt_b64"], u["hash_b64"])
        if not ok:
            st.error("Correo o contraseña incorrectos.")
            return False

        _set_user_session(u)
        st.success("Acceso correcto.")
        st.rerun()

    return False
