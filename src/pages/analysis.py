import streamlit as st
from src.services.finance_data import get_static_data, get_price_data
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all

def page_analysis():
    # Header + acciones
    colA, colB = st.columns([0.7, 0.3])
    with colA:
        st.title("📊 Análisis Financiero")
    with colB:
        if st.button("🧹 Limpiar caché", use_container_width=True):
            cache_clear_all()
            st.success("Caché limpiado.")
            st.rerun()

    with st.sidebar:
        logout_button()

    ticker = st.text_input("Ticker", value="AAPL")
    if not ticker:
        st.stop()

    try:
        static = get_static_data(ticker)
        price = get_price_data(ticker)

        # Perfil
        prof = static.get("profile", {})
        summary = static.get("summary", {})

        # intenta dominio/logo desde profile (depende endpoint)
        website = ""
        try:
            website = prof.get("website") or prof.get("assetProfile", {}).get("website") or ""
        except Exception:
            website = ""

        # Logo
        logo_urls = logo_candidates(website)
        if logo_urls:
            st.image(logo_urls[0], width=64)

        st.subheader(ticker.upper())

        # Precio (depende endpoint quotes)
        quote = (price.get("quote") or {}).get("quoteResponse", {}).get("result", [])
        last_price = None
        if quote and isinstance(quote, list):
            last_price = quote[0].get("regularMarketPrice")

        st.metric("Precio", f"{last_price}" if last_price is not None else "N/D")

        # Aquí es donde luego enchufamos tus bloques: ratios, gráficos, Weiss, etc.
        st.info("Base OK. Aquí conectamos todos tus bloques de análisis (ratios, gráficos, valoración).")

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

