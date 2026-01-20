# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import get_price_data, get_profile_data, get_key_stats
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all


def _get_user_email() -> str:
    keys = ["user_email", "email", "username", "user", "auth_email", "logged_email", "auth_email"]
    for k in keys:
        v = st.session_state.get(k)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


def _get_user_role() -> str:
    keys = ["role", "user_role", "auth_role", "logged_role", "auth_role"]
    for k in keys:
        v = st.session_state.get(k)
        if isinstance(v, str) and v:
            return v.strip().lower()
    return ""


def _is_admin() -> bool:
    return _get_user_role() == "admin" or st.session_state.get("is_admin") is True


def _fmt_price(x, currency: str) -> str:
    if isinstance(x, (int, float)):
        # formato tipo 250.48 USD (puedes cambiar a formato CL si quieres)
        return f"{x:.2f} {currency}".strip()
    return "N/D"


def _fmt_delta(net, pct) -> str | None:
    if isinstance(net, (int, float)) and isinstance(pct, (int, float)):
        return f"{net:+.2f} ({pct:+.2f}%)"
    return None


def _fmt_kpi(x, suffix: str = "") -> str:
    if isinstance(x, (int, float)):
        return f"{x:.2f}{suffix}"
    return "N/D"


def page_analysis():
    DAILY_LIMIT = 3
    user_email = _get_user_email()
    is_admin = _is_admin()

    # -----------------------------
    # CSS: Contenedor centrado para TODO el contenido principal
    # -----------------------------
    st.markdown(
        """
        <style>
          .cd-wrap {
            max-width: 820px;
            margin: 0 auto;
          }
          /* reduce el "aire" arriba */
          .cd-title { margin-top: 0.25rem; margin-bottom: 0.75rem; }

          /* el form dentro del contenedor */
          .cd-form > div[data-testid="stForm"] {
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 14px;
            padding: 14px 14px 6px 14px;
            background: rgba(255,255,255,0.0);
          }

          /* “cards” sin borde (look moderno), pero con separación */
          .cd-card {
            padding: 12px 2px;
            margin-top: 12px;
          }

          /* evita que imágenes dejen basura visual */
          .cd-logo img { display: block; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------
    # SIDEBAR (1 sola vez)
    # -----------------------------
    with st.sidebar:
        logout_button()  # ya tiene key fijo en auth.py ✅
        limit_box = st.empty()

        # Botón de caché SOLO admin y acá (no arriba en el header)
        if is_admin:
            if st.button("🧹 Limpiar caché", key="clear_cache_btn", use_container_width=True):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()

        if is_admin:
            limit_box.success("👑 Admin: sin límite diario (alimenta el caché global).")
        else:
            if user_email:
                rem = remaining_searches(user_email, DAILY_LIMIT)
                limit_box.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
            else:
                limit_box.warning("No se detectó email del usuario.")

    # -----------------------------
    # CONTENIDO PRINCIPAL CENTRADO
    # -----------------------------
    st.markdown('<div class="cd-wrap">', unsafe_allow_html=True)

    # Título centrado y SIN expandirse (queda dentro del contenedor)
    st.markdown('<div class="cd-title">', unsafe_allow_html=True)
    st.markdown("## 📊 Análisis Financiero")
    st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------
    # FORM centrado (en “rectángulo”)
    # -----------------------------
    st.markdown('<div class="cd-form">', unsafe_allow_html=True)
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")
    st.markdown("</div>", unsafe_allow_html=True)

    if not submitted:
        st.markdown("</div>", unsafe_allow_html=True)  # cd-wrap
        return

    if not ticker:
        st.warning("Ingresa un ticker.")
        st.markdown("</div>", unsafe_allow_html=True)  # cd-wrap
        return

    # Consume SOLO si NO es admin
    if (not is_admin) and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            limit_box.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            st.markdown("</div>", unsafe_allow_html=True)  # cd-wrap
            return
        limit_box.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    # -----------------------------
    # DATA
    # -----------------------------
    price = get_price_data(ticker) or {}
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

    # Logo (best effort) — filtra URLs válidas para evitar que aparezca “0”
    website = ""
    if isinstance(prof_full, dict):
        website = prof_full.get("website") or ""
    if not website and isinstance(prof_raw, dict):
        website = prof_raw.get("website") or ""

    logo_urls = [
        u for u in (logo_candidates(website) or [])
        if isinstance(u, str) and u.startswith(("http://", "https://"))
    ]

    # -----------------------------
    # CARD: Logo + Nombre + Precio (misma línea) dentro del contenedor
    # -----------------------------
    st.markdown('<div class="cd-card">', unsafe_allow_html=True)

    row = st.columns([0.12, 0.55, 0.33], vertical_alignment="bottom")

    with row[0]:
        if logo_urls:
            st.markdown('<div class="cd-logo">', unsafe_allow_html=True)
            st.image(logo_urls[0], width=54)
            st.markdown("</div>", unsafe_allow_html=True)

    with row[1]:
        st.markdown(f"### {company_name}")
        st.caption(ticker)

    with row[2]:
        st.markdown(f"### {_fmt_price(last_price, currency)}")
        if delta_txt:
            st.caption(delta_txt)

    st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------
    # CARD: KPIs (centrados, grilla moderna SIN bordes)
    # -----------------------------
    st.markdown('<div class="cd-card">', unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.caption("Beta")
        st.markdown(f"### {_fmt_kpi(stats.get('beta'))}")
    with k2:
        st.caption("PER (TTM)")
        # PE suele ser “x”
        pe = stats.get("pe_ttm")
        st.markdown(f"### {_fmt_kpi(pe)}" + ("x" if isinstance(pe, (int, float)) else ""))
    with k3:
        st.caption("EPS (TTM)")
        st.markdown(f"### {_fmt_kpi(stats.get('eps_ttm'))}")
    with k4:
        st.caption("Target 1Y (est.)")
        st.markdown(f"### {_fmt_kpi(stats.get('target_1y'))}")

    st.markdown("</div>", unsafe_allow_html=True)

    # Cerramos wrapper principal
    st.markdown("</div>", unsafe_allow_html=True)
