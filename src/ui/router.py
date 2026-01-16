import streamlit as st
from src.db import init_db
from src.auth import require_login
from src.pages.analysis import page_analysis

def run_app():
    init_db()
    require_login()

    # Sidebar navegación
    with st.sidebar:
        st.markdown(f"**Usuario:** {st.session_state.get('user_email','')}")
        st.divider()

        section = st.radio(
            "Secciones",
            ["Análisis"],
            index=0,
        )

    if section == "Análisis":
        page_analysis()

