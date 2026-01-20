# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import get_price_data, get_profile_data, get_key_stats
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all


def _get_user_email() -> str:
    keys = ["user_email", "email", "username", "user", "auth_email", "logged_email"]
    for k in keys:
        v = st.session_state.get(k)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


def _get_user_role() -> str:
    keys = ["role", "user_role", "auth_role", "logged_role"]
    for k in keys:
        v = st.session_state.get(k)
        if isinstance(v, str) and v:
            return v.strip().lower()
    return ""


def _is_admin() -> bool:
    role = _get_user_role()
    if role == "admin":
        return True
    if st.session_state.get("is_admin") is True:
        return True
    return False


def _fmt_price(x, currency: str) -> str:
    if isinstance(x, (int, float)):
        return f"{x:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".").strip()
    return "N/D"


def _fmt_delta(net, pct) -> str | None:
    if isinstance(net, (int, float)) and isinstance(pct, (int, float)):
        sign_net = f"{net:+.2f}"
        sign_pct = f"{pct:+.2f}%"
        return f"{sign_net} ({sign_pct})"
    return None


def page_analysis():
    DAILY_LIMIT = 3
    user_email = _get_user_email()
    is_admin = _is_admin()

    # -----------------------------
    # SIDEBAR (1 sola vez)
    # -----------------------------
    with st.sidebar:
        logout_button()
        limit_box = st.empty()

        if is_admin:
            limit_box.success("👑 Admin: sin límite diario (alimenta el caché global).")
        else:
            if user_email:
                rem = remaining_searches(user_email, DAILY_LIMIT)
                limit_box.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
            else:
                limit_box.warning("No se detectó email del usuario.")

    # -----------------------------
    # HEADER (cache solo admin)
    # -----------------------------
    head_l, head_r = st.columns([0.75, 0.25])
    with head_l:
        st.title("📊 Análisis Financiero")
    with head_r:
        if is_admin:
            if st.button("🧹 Limpiar caché", key="clear_cache_btn", use_container_width=True):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()

    # -----------------------------
    # CSS: centra y limita ancho del form y del bloque principal
    # (sin cambiar todo el layout global)
    # -----------------------------
    st.markdown(
        """
        <style>
          /* centra el form y lo limita (evita que se estire infinito) */
          div[data-testid="stForm"] {
            max-width: 720px;
            margin: 0 auto;
          }

          /* centra el bloque principal que viene justo después del form */
          .cd-main {
            max-width: 720px;
            margin: 0 auto;
          }

          /* pequeño ajuste para que el logo no deje “basura” visual */
          .cd-logo img {
            display: block;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------
    # FORM (centrado)
    # -----------------------------
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")

    if not submitted:
        return

    if not ticker:
        st.warning("Ingresa un ticker.")
        return

    # Consume SOLO si NO es admin
    if (not is_admin) and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            limit_box.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            return
        limit_box.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    # -----------------------------
    # DATA
    # -----------------------------
    price = get_price_data(ticker)
    prof_full = get_profile_data(ticker) or {}
    prof_raw = prof_full.get("raw") if isinstance(prof_full, dict) else {}
    stats = get_key_stats(ticker) or {}

    company_name = (
        (prof_raw.get("longName") if isinstance(prof_raw, dict) else None)
        or (prof_raw.get("shortName") if isinstance(prof_raw, dict) else None)
        or (prof_full.get("shortName") if isinstance(prof_full, dict) else None)
        or ticker
    )

    last_price = price.get("last_price")
    currency = price.get("currency") or ""
    delta_txt = _fmt_delta(price.get("net_change"), price.get("pct_change"))

    # Logo (best effort): filtra URLs válidas para evitar el “0”
    website = (prof_full.get("website") if isinstance(prof_full, dict) else "") or (prof_raw.get("website") if isinstance(prof_raw, dict) else "") or ""
    logo_urls = [u for u in (logo_candidates(website) or []) if isinstance(u, str) and u.startswith(("http://", "https://"))]

    # -----------------------------
    # BLOQUE PRINCIPAL CENTRADO
    # Nombre + Precio en misma línea
    # -----------------------------
    st.markdown('<div class="cd-main">', unsafe_allow_html=True)

    top = st.columns([0.12, 0.58, 0.30], vertical_alignment="bottom")

    with top[0]:
        if logo_urls:
            st.markdown('<div class="cd-logo">', unsafe_allow_html=True)
            st.image(logo_urls[0], width=52)
            st.markdown("</div>", unsafe_allow_html=True)

    with top[1]:
        st.markdown(f"### {company_name}")
        st.caption(ticker)

    with top[2]:
        st.markdown(f"### {_fmt_price(last_price, currency)}")
        if delta_txt:
            st.caption(delta_txt)

    st.markdown("</div>", unsafe_allow_html=True)

    # (Nada más en este paso, como pediste: luego centramos KPIs + tarjetas)
