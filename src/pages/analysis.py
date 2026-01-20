# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import get_price_data, get_profile_data, get_key_stats
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all


def _get_user_email() -> str:
    for key in ["auth_email", "user_email", "email", "username", "user", "logged_email"]:
        v = st.session_state.get(key)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


def _get_user_role() -> str:
    for key in ["auth_role", "role", "user_role", "auth_role", "logged_role"]:
        v = st.session_state.get(key)
        if isinstance(v, str) and v:
            return v.strip().lower()
    return ""


def _is_admin() -> bool:
    return _get_user_role() == "admin" or st.session_state.get("is_admin") is True


def _fmt_price(x, currency: str) -> str:
    if not isinstance(x, (int, float)):
        return "N/D"
    # 1.234,56 estilo ES
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} {currency}".strip()


def _fmt_delta(net, pct) -> str | None:
    if isinstance(net, (int, float)) and isinstance(pct, (int, float)):
        return f"{net:+.2f} ({pct:+.2f}%)"
    return None


def _fmt_kpi(x, suffix: str = "", decimals: int = 2) -> str:
    return f"{x:.{decimals}f}{suffix}" if isinstance(x, (int, float)) else "N/D"


def page_analysis():
    DAILY_LIMIT = 3
    user_email = _get_user_email()
    is_admin = _is_admin()

    # -----------------------------
    # SIDEBAR (una sola vez)
    # -----------------------------
    with st.sidebar:
        logout_button()  # ya tiene key="logout_button" en auth.py
        if is_admin:
            if st.button("🧹 Limpiar caché", key="clear_cache_btn", use_container_width=True):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()

        limit_box = st.empty()
        if is_admin:
            limit_box.success("👑 Admin: sin límite diario (alimenta el caché global).")
        else:
            if user_email:
                rem = remaining_searches(user_email, DAILY_LIMIT)
                limit_box.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
            else:
                limit_box.warning("No se detectó el correo del usuario.")

    # -----------------------------
    # CSS: FIJAR ANCHO Y CENTRAR (clave)
    # -----------------------------
    st.markdown(
        """
        <style>
          /* Fija el ancho del contenido principal (evita expansión horizontal) */
          section.main > div.block-container {
            max-width: 920px;
            padding-left: 18px;
            padding-right: 18px;
            margin: 0 auto;
          }

          /* Un poco más compacto el input/botón */
          div[data-testid="stForm"] { margin-bottom: 0.25rem; }

          /* “Cards” sin borde (look moderno) */
          .cd-card {
            padding: 16px 18px;
            border-radius: 14px;
            background: rgba(255,255,255,0.75);
          }
          @media (prefers-color-scheme: dark) {
            .cd-card { background: rgba(30,30,30,0.55); }
          }

          /* Ajuste opcional para que el título no se “desparrame” */
          .cd-title { margin-top: 0.25rem; margin-bottom: 0.75rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------
    # NIVEL 1: TÍTULO (centrado por ancho fijo global)
    # -----------------------------
    st.markdown('<div class="cd-title">', unsafe_allow_html=True)
    st.markdown("## 📊 Análisis Financiero")
    st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------
    # NIVEL 2: BUSCADOR (en card sin borde)
    # -----------------------------
    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")
    st.markdown("</div>", unsafe_allow_html=True)

    if not submitted:
        return

    if not ticker:
        st.warning("Ingresa un ticker.")
        return

    # Limitar búsquedas (solo no-admin)
    if not is_admin and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            limit_box.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            return
        limit_box.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    # -----------------------------
    # DATA
    # -----------------------------
    price = get_price_data(ticker) or {}
    profile = get_profile_data(ticker) or {}
    raw = profile.get("raw") if isinstance(profile, dict) else {}
    stats = get_key_stats(ticker) or {}

    company_name = raw.get("longName") or raw.get("shortName") or profile.get("shortName") or ticker

    last_price = price.get("last_price")
    currency = price.get("currency") or ""
    delta_txt = _fmt_delta(price.get("net_change"), price.get("pct_change"))

    # Logo (evitar el “0”: solo URL válida)
    website = (profile.get("website") or raw.get("website") or "") if isinstance(profile, dict) else ""
    logos = logo_candidates(website) if website else []
    logo_url = next((u for u in logos if isinstance(u, str) and u.startswith(("http://", "https://"))), "")

    # -----------------------------
    # NIVEL 3: NOMBRE + PRECIO (misma línea) dentro de card
    # -----------------------------
    st.markdown('<div class="cd-card" style="margin-top: 12px;">', unsafe_allow_html=True)

    c_logo, c_name, c_price = st.columns([0.12, 0.58, 0.30], gap="small", vertical_alignment="center")

    with c_logo:
        if logo_url:
            st.image(logo_url, width=52)

    with c_name:
        st.markdown(f"### {company_name}")
        st.caption(ticker)

    with c_price:
        st.markdown(f"### {_fmt_price(last_price, currency)}")
        if delta_txt:
            st.caption(delta_txt)

    st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------
    # NIVEL 4: KPIs (4 columnas) dentro de card
    # -----------------------------
    st.markdown('<div class="cd-card" style="margin-top: 12px;">', unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4, gap="small")
    with k1:
        st.caption("Beta")
        st.markdown(f"### {_fmt_kpi(stats.get('beta'))}")
    with k2:
        st.caption("PER (TTM)")
        pe = stats.get("pe_ttm")
        pe_txt = _fmt_kpi(pe) + ("x" if isinstance(pe, (int, float)) else "")
        st.markdown(f"### {pe_txt}")
    with k3:
        st.caption("EPS (TTM)")
        st.markdown(f"### {_fmt_kpi(stats.get('eps_ttm'))}")
    with k4:
        st.caption("Target 1Y (est.)")
        st.markdown(f"### {_fmt_kpi(stats.get('target_1y'))}")

    st.markdown("</div>", unsafe_allow_html=True)
