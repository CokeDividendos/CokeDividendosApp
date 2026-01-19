
import streamlit as st

st.caption("BUILD: 2026-01-19-XYZ")

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

    ticker = st.text_input("Ticker", value="AAPL").strip().upper()
    if not ticker:
        st.stop()

    try:
        static = get_static_data(ticker)
        price = get_price_data(ticker)

        # --- Logo (best effort) ---
        prof = static.get("profile", {}) if isinstance(static, dict) else {}
        website = ""
        try:
            website = prof.get("website") or prof.get("assetProfile", {}).get("website") or ""
        except Exception:
            website = ""

        logo_urls = logo_candidates(website)
        if logo_urls:
            st.image(logo_urls[0], width=64)

        st.subheader(ticker)

        # --- Precio (del endpoint /api/v1/market/quotes) ---
        last_price = price.get("last_price")
        currency = price.get("currency") or ""
        pct = price.get("pct_change")
        net = price.get("net_change")
        vol = price.get("volume")
        asof = price.get("asof") or ""

        delta_txt = None
        if isinstance(net, (int, float)) and isinstance(pct, (int, float)):
            delta_txt = f"{net:+.2f} ({pct:+.2f}%)"

        st.metric(
            "Precio",
            f"{last_price:.2f} {currency}".strip() if isinstance(last_price, (int, float)) else "N/D",
            delta=delta_txt,
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Empresa", price.get("company_name") or "N/D")
        with col2:
            st.metric("Exchange", price.get("exchange") or "N/D")
        with col3:
            st.metric("Asset Class", price.get("asset_class") or "N/D")

        if vol is not None:
            st.caption(f"Volumen: {vol:,}".replace(",", "."))
        if asof:
            st.caption(f"Fecha: {asof}")

        st.info("Base OK. Aquí conectamos todos tus bloques de análisis (ratios, gráficos, valoración).")

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
