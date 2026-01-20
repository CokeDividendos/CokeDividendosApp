# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import (
    get_static_data,
    get_price_data,
    get_profile_data,
    get_key_stats,          # NUEVA función para KPIs
    get_history_daily,
    get_drawdown_daily,
    get_perf_metrics,
    get_dividends_series,
    get_dividends_by_year,
    get_dividend_metrics,
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

def page_analysis():
    DAILY_LIMIT = 3  # Límite de búsquedas/día
    user_email = _get_user_email()
    is_admin = _is_admin()

    # --- Sidebar ---
    with st.sidebar:
        logout_button()
        # Placeholder único para no duplicar contador
        limit_box = st.empty()
        if is_admin:
            limit_box.success("👑 Admin: sin límite diario.")
        else:
            if user_email:
                rem = remaining_searches(user_email, DAILY_LIMIT)
                limit_box.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
            else:
                limit_box.warning("No se detectó email del usuario.")

    # --- Header ---
    colA, colB = st.columns([0.75, 0.25])
    with colA:
        st.title("📊 Análisis Financiero")
    with colB:
        if is_admin:
            if st.button("🧹 Limpiar caché", key="clear_cache_btn"):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()

    # --- Layout centrado para input y tarjetas ---
    st.markdown("<div style='max-width: 800px; margin: auto'>", unsafe_allow_html=True)

    # Form de búsqueda
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")

    if not submitted or not ticker:
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Control de límite
    if not is_admin and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            limit_box.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            st.markdown("</div>", unsafe_allow_html=True)
            return
        limit_box.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    # --- Fetch data ---
    static = get_static_data(ticker)
    price = get_price_data(ticker)
    prof_full = get_profile_data(ticker)
    key_stats = get_key_stats(ticker)  # KPIs principales

    prof_raw = prof_full.get("raw") if isinstance(prof_full, dict) else {}
    website = prof_full.get("website") or prof_raw.get("website")
    logo = logo_candidates(website or "")

    # Nombre de la empresa
    profile = static.get("profile", {}) or {}
    company_name = profile.get("name") or prof_full.get("shortName") or prof_raw.get("shortName") or "N/D"

    # Precio y variación
    last_price = price.get("last_price")
    currency = price.get("currency") or ""
    pct = price.get("pct_change")
    net = price.get("net_change")
    delta_txt = f"{net:+.2f} ({pct:+.2f}%)" if isinstance(net, (int, float)) and isinstance(pct, (int, float)) else None

    # --- Tarjeta principal: precio + KPIs ---
    if logo:
        st.image(logo[0], width=60)
    st.subheader(company_name)

    st.metric("Precio", f"{last_price:.2f} {currency}" if isinstance(last_price, (int, float)) else "N/D", delta=delta_txt)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Beta", f"{key_stats['beta']:.2f}" if isinstance(key_stats.get("beta"), (int, float)) else "N/D")
    with c2:
        st.metric("PER TTM", f"{key_stats['pe_ttm']:.2f}" if isinstance(key_stats.get("pe_ttm"), (int, float)) else "N/D")
    with c3:
        st.metric("EPS TTM", f"{key_stats['eps_ttm']:.2f}" if isinstance(key_stats.get("eps_ttm"), (int, float)) else "N/D")
    with c4:
        st.metric("Target 1Y", f"{key_stats['target_1y']:.2f}" if isinstance(key_stats.get("target_1y"), (int, float)) else "N/D")

    # --- Expander bloques (histórico, drawdown, dividendos) ---
    years = 5
    perf = get_perf_metrics(ticker, years=years)
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("CAGR (aprox)", f"{perf.get('cagr') * 100:.2f}%" if isinstance(perf.get("cagr"), (int, float)) else "N/D")
    with k2:
        st.metric("Volatilidad anual", f"{perf.get('volatility') * 100:.2f}%" if isinstance(perf.get("volatility"), (int, float)) else "N/D")
    with k3:
        st.metric("Max Drawdown", f"{perf.get('max_drawdown') * 100:.2f}%" if isinstance(perf.get("max_drawdown"), (int, float)) else "N/D")

    with st.expander("📈 Precio histórico (5Y)"):
        hist = get_history_daily(ticker, years=years)
        if hist is None or hist.empty:
            st.warning("Sin datos históricos.")
        else:
            st.line_chart(hist["Close"])

    with st.expander("📉 Drawdown (5Y)"):
        dd = get_drawdown_daily(ticker, years=years)
        if dd is None or dd.empty or "Drawdown" not in dd.columns:
            st.warning("Sin datos de drawdown.")
        else:
            st.line_chart(dd["Drawdown"])

    with st.expander("💸 Dividendos (5Y)"):
        div_metrics = get_dividend_metrics(ticker, years=years)
        st.metric("Dividendo TTM", f"{div_metrics.get('ttm_dividend'):.2f}" if isinstance(div_metrics.get("ttm_dividend"), (int, float)) else "N/D")
        st.metric("Yield TTM", f"{div_metrics.get('ttm_yield') * 100:.2f}%" if isinstance(div_metrics.get("ttm_yield"), (int, float)) else "N/D")
        st.metric("CAGR Div (aprox)", f"{div_metrics.get('div_cagr') * 100:.2f}%" if isinstance(div_metrics.get("div_cagr"), (int, float)) else "N/D")

        divs = get_dividends_series(ticker, years=years)
        if divs is None or divs.empty:
            st.warning("Sin dividendos disponibles para este ticker.")
        else:
            st.line_chart(divs["Dividend"])

        annual = get_dividends_by_year(ticker, years=years)
        if annual is not None and not annual.empty:
            st.bar_chart(annual.set_index("Year")["Dividends"])

    st.markdown("</div>", unsafe_allow_html=True)
