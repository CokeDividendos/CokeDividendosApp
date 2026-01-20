# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import (
    get_static_data,
    get_price_data,
    get_profile_data,
    get_history_daily,
    get_drawdown_daily,
    get_perf_metrics,
    get_dividends_series,
    get_dividends_by_year,
    get_dividend_metrics,
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
    role = _get_user_role()
    if role == "admin":
        return True
    if st.session_state.get("is_admin") is True:
        return True
    return False


def _fmt_num(x, nd="N/D", fmt="{:.2f}"):
    return fmt.format(x) if isinstance(x, (int, float)) else nd


def page_analysis():
    DAILY_LIMIT = 3
    user_email = _get_user_email()
    is_admin = _is_admin()

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
    # LAYOUT CENTRADO (Opción A)
    # -----------------------------
    pad_l, center, pad_r = st.columns([1, 2, 1])

    with center:
        # FORM centrado (no se expande a todo el ancho de la pantalla)
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
        static = get_static_data(ticker)
        price = get_price_data(ticker)
        prof_full = get_profile_data(ticker)  # para nombre robusto
        prof_raw = prof_full.get("raw") if isinstance(prof_full, dict) else {}

        # Logo (best effort)
        website = (prof_full.get("website") if isinstance(prof_full, dict) else None) or prof_raw.get("website") or ""
        logo = logo_candidates(website)
        if logo:
            st.image(logo[0], width=56)

        # Nombre con prioridad: static["profile"]["name"]
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
            else None
        )

        # -----------------------------
        # NOMBRE + PRECIO EN LA MISMA LÍNEA
        # -----------------------------
        row_l, row_r = st.columns([0.62, 0.38], vertical_alignment="bottom")

        with row_l:
            # Nombre grande, ticker pequeño debajo
            st.markdown(f"## {company_name}")
            st.caption(ticker)

        with row_r:
            # Precio + delta (en el mismo renglón visual de la sección superior)
            if isinstance(last_price, (int, float)):
                st.markdown(f"## {_fmt_num(last_price)} {currency}".strip())
            else:
                st.markdown("## N/D")

            if delta_txt:
                # estilo simple (sin meter st.metric que tiende a “romper” la alineación)
                st.caption(delta_txt)

        st.divider()

        # Nada más por ahora, como pediste (sin tocar KPIs/expander/etc)
