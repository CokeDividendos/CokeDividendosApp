import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import get_static_data, get_price_data
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all

# Si ya no lo necesitas después, bórralo
st.caption("BUILD: 2026-01-19-XYZ")


def _get_user_email() -> str:
    """
    Intenta encontrar el email del usuario autenticado desde session_state.
    Ajusta aquí si tu auth usa otra clave.
    """
    for k in ("user_email", "email", "username", "user"):
        v = st.session_state.get(k)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


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

    # Sidebar
    with st.sidebar:
        logout_button()

        user_email = _get_user_email()
        DAILY_LIMIT = 5  # cambia a 3 si quieres

        if user_email:
            rem = remaining_searches(user_email, DAILY_LIMIT)
            st.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
        else:
            st.warning("No pude detectar el email del usuario en sesión. Revisa session_state keys.")

    # Formulario para no disparar requests al escribir
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")

    if not submitted:
        st.stop()

    if not ticker:
        st.warning("Ingresa un ticker.")
        st.stop()

    # Límite diario: consume SOLO al buscar
    user_email = _get_user_email()
    DAILY_LIMIT = 5
    if user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            st.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana cuando se reinicie el contador.")
            st.stop()
        # Refresca contador visible
        with st.sidebar:
            st.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    try:
        # Carga datos (con caché en backend)
        static = get_static_data(ticker)
        price = get_price_data(ticker)

        # --- Logo (best effort) ---
        prof = static.get("profile", {}) if isinstance(static, dict) else {}
        website = ""
        try:
            website = prof.get("website") or ""
        except Exception:
            website = ""

        logo_urls = logo_candidates(website)
        if logo_urls:
            st.image(logo_urls[0], width=64)

        st.subheader(ticker)

        # --- Precio ---
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
            st.metric("Empresa", price.get("company_name") or prof.get("name") or "N/D")
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

        # Aquí después enchufamos: stats, financials, dividends, valuation blocks
        st.info("Base OK. Próximo: integrar estadísticas, estados financieros, dividendos y ratios con caché trimestral.")

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
