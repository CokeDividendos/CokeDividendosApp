# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import (
    get_static_data,
    get_price_data,
    get_profile_data,
    get_key_stats,
)
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
    if _get_user_role() == "admin":
        return True
    return st.session_state.get("is_admin") is True


def _fmt_num(x, nd="N/D", fmt="{:.2f}"):
    return fmt.format(x) if isinstance(x, (int, float)) else nd


def _first_valid_logo_url(urls) -> str:
    if not urls:
        return ""
    for u in urls:
        if isinstance(u, str):
            us = u.strip()
            if us.startswith("http://") or us.startswith("https://"):
                return us
    return ""


def page_analysis():
    # -----------------------------
    # CONFIG
    # -----------------------------
    DAILY_LIMIT = 3
    user_email = _get_user_email()
    is_admin = _is_admin()

    # -----------------------------
    # CSS: contenedor centrado + cards con ancho fijo
    # -----------------------------
    st.markdown(
        """
        <style>
          /* Ancho fijo para los bloques principales */
          .cd-wrap { max-width: 760px; margin: 0 auto; }
          .cd-card {
            border: 1px solid rgba(49,51,63,.15);
            border-radius: 14px;
            padding: 18px 18px;
            margin: 14px auto;
            background: rgba(255,255,255,.75);
          }
          /* Ajustes dark-mode amigables */
          @media (prefers-color-scheme: dark) {
            .cd-card { background: rgba(28,28,28,.55); border-color: rgba(255,255,255,.12); }
          }
          /* Precio alineado a la derecha */
          .cd-right { text-align: right; }
          .cd-muted { opacity: .75; font-size: .9rem; }
          .cd-delta { font-size: .9rem; opacity: .85; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------
    # SIDEBAR (una sola vez)
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
    # HEADER (botón cache solo admin)
    # -----------------------------
    head_l, head_r = st.columns([0.75, 0.25])
    with head_l:
        st.title("📊 Análisis Financiero")
    with head_r:
        if is_admin:
            if st.button("🧹 Limpiar caché", key="clear_cache_btn"):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()

    # -----------------------------
    # CONTENIDO CENTRADO (wrap)
    # -----------------------------
    st.markdown('<div class="cd-wrap">', unsafe_allow_html=True)

    # --------- CARD: BUSCADOR (centrado y NO expansivo) ----------
    st.markdown('<div class="cd-card">', unsafe_allow_html=True)
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")
    st.markdown("</div>", unsafe_allow_html=True)

    if not submitted:
        st.markdown("</div>", unsafe_allow_html=True)  # close wrap
        return

    if not ticker:
        st.warning("Ingresa un ticker.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Consume SOLO si NO es admin
    if (not is_admin) and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            limit_box.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            st.markdown("</div>", unsafe_allow_html=True)
            return
        limit_box.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    # -----------------------------
    # DATA
    # -----------------------------
    static = get_static_data(ticker)
    price = get_price_data(ticker)
    prof_full = get_profile_data(ticker)
    prof_raw = prof_full.get("raw") if isinstance(prof_full, dict) else {}

    profile = static.get("profile", {}) if isinstance(static, dict) else {}
    company_name = (
        (profile.get("name") if isinstance(profile, dict) else None)
        or (prof_raw.get("longName") if isinstance(prof_raw, dict) else None)
        or (prof_raw.get("shortName") if isinstance(prof_raw, dict) else None)
        or (prof_full.get("shortName") if isinstance(prof_full, dict) else None)
        or "N/D"
    )

    last_price = price.get("last_price")
    currency = price.get("currency") or ""
    pct = price.get("pct_change")
    net = price.get("net_change")

    delta_txt = (
        f"{net:+.2f} ({pct:+.2f}%)"
        if isinstance(net, (int, float)) and isinstance(pct, (int, float))
        else ""
    )

    # Logo best-effort (evita “0” / valores no url)
    website = (prof_full.get("website") if isinstance(prof_full, dict) else None) or (prof_raw.get("website") if isinstance(prof_raw, dict) else "") or ""
    logo_url = _first_valid_logo_url(logo_candidates(website))

    # KPIs (si tu finance_data.py ya tiene get_key_stats, perfecto; si no, quedará N/D)
    try:
        ks = get_key_stats(ticker) or {}
    except Exception:
        ks = {}

    beta = ks.get("beta")
    pe_ttm = ks.get("pe_ttm")
    eps_ttm = ks.get("eps_ttm")
    target_1y = ks.get("target_1y")

    # --------- CARD: HEADER (logo + nombre + precio en misma línea) ----------
    st.markdown('<div class="cd-card">', unsafe_allow_html=True)

    c_logo, c_name, c_price = st.columns([0.14, 0.56, 0.30], vertical_alignment="center")

    with c_logo:
        if logo_url:
            st.image(logo_url, width=44)

    with c_name:
        st.markdown(f"### {company_name}")
        st.markdown(f'<div class="cd-muted">{ticker}</div>', unsafe_allow_html=True)

    with c_price:
        if isinstance(last_price, (int, float)):
            st.markdown(f'<div class="cd-right"><h3 style="margin:0">{_fmt_num(last_price)} {currency}</h3></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cd-right"><h3 style="margin:0">N/D</h3></div>', unsafe_allow_html=True)

        if delta_txt:
            st.markdown(f'<div class="cd-right cd-delta">{delta_txt}</div>', unsafe_allow_html=True)

    st.divider()

    # --------- KPIs centrados y contenidos dentro de la misma card ----------
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Beta", _fmt_num(beta, fmt="{:.2f}"))
    with k2:
        st.metric("PER (TTM)", _fmt_num(pe_ttm, fmt="{:.2f}x"))
    with k3:
        st.metric("EPS (TTM)", _fmt_num(eps_ttm, fmt="{:.2f}"))
    with k4:
        st.metric("Target 1Y (est.)", _fmt_num(target_1y, fmt="{:.2f}"))

    st.markdown("</div>", unsafe_allow_html=True)  # close header card
    st.markdown("</div>", unsafe_allow_html=True)  # close wrap
