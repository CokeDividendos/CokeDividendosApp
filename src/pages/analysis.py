# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import get_static_data, get_price_data
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all


def _get_user_email() -> str:
    # Intenta varias keys comunes
    candidates = ["user_email", "email", "username", "user", "auth_email", "logged_email"]
    for k in candidates:
        v = st.session_state.get(k)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


def page_analysis():
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

        user_email = _get_user_email()
        DAILY_LIMIT = 5

        if user_email:
            rem = remaining_searches(user_email, DAILY_LIMIT)
            st.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
        else:
            st.warning("No pude detectar el email del usuario en sesión.")
            with st.expander("Debug: session_state keys"):
                # no mostramos valores sensibles completos, solo tipo y (si es string) primeros chars
                for k, v in st.session_state.items():
                    if isinstance(v, str):
                        st.write(f"- {k}: str ({v[:3]}...)")
                    else:
                        st.write(f"- {k}: {type(v).__name__}")

    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")

    if not submitted:
        st.stop()

    if not ticker:
        st.warning("Ingresa un ticker.")
        st.stop()

    # Consume SOLO al presionar Buscar
    user_email = _get_user_email()
    DAILY_LIMIT = 5
    if user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            st.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            st.stop()
        with st.sidebar:
            st.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    try:
        static = get_static_data(ticker)
        price = get_price_data(ticker)

        prof = static.get("profile", {}) if isinstance(static, dict) else {}
        website = prof.get("website") or ""
        logo_urls = logo_candidates(website)
        if logo_urls:
            st.image(logo_urls[0], width=64)

        st.subheader(ticker)

        last_price = price.get("last_price")
        currency = price.get("currency") or ""
        pct = price.get("pct_change")
        net = price.get("net_change")
        vol = price.get("volume")
        asof = price.get("asof") or ""

        delta_txt = (
            f"{net:+.2f} ({pct:+.2f}%)"
            if isinstance(net, (int, float)) and isinstance(pct, (int, float))
            else None
        )

        st.metric(
            "Precio",
            f"{last_price:.2f} {currency}".strip() if isinstance(last_price, (int, float)) else "N/D",
            delta=delta_txt,
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Empresa", prof.get("name") or "N/D")
        with col2:
            st.metric("Exchange", price.get("exchange") or prof.get("exchange") or "N/D")
        with col3:
            st.metric("Asset Class", price.get("asset_class") or "N/D")

        if vol is not None:
            try:
                st.caption(f"Volumen: {int(vol):,}".replace(",", "."))
            except Exception:
                st.caption(f"Volumen: {vol}")
        if asof:
            st.caption(f"Fecha: {asof}")

        st.info("Base OK. Próximo: estados financieros históricos + dividendos + ratios.")

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
