# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import (
    get_static_data,
    get_price_data,
    get_financial_data,
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
    candidates = ["user_email", "email", "username", "user", "auth_email", "logged_email"]
    for k in candidates:
        v = st.session_state.get(k)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


def _get_user_role() -> str:
    candidates = ["role", "user_role", "auth_role", "logged_role"]
    for k in candidates:
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


def _fmt_float(x, nd="N/D", dec=2):
    if isinstance(x, (int, float)):
        try:
            return f"{float(x):.{dec}f}"
        except Exception:
            return nd
    return nd


def _fmt_pct(x, nd="N/D", dec=2):
    if isinstance(x, (int, float)):
        try:
            return f"{float(x) * 100:.{dec}f}%"
        except Exception:
            return nd
    return nd


def page_analysis():
    # ✅ Ajuste: usuarios 3 búsquedas/día
    DAILY_LIMIT = 3

    user_email = _get_user_email()
    is_admin = _is_admin()

    # Header
    colA, colB = st.columns([0.75, 0.25])
    with colA:
        st.title("📊 Análisis Financiero")
    with colB:
        # ✅ Ajuste: botón de caché SOLO admin
        if is_admin:
            if st.button("🧹 Limpiar caché", use_container_width=True, key="btn_clear_cache"):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()

    # Sidebar
    with st.sidebar:
        logout_button()

        if is_admin:
            st.success("👑 Admin: sin límite diario (las búsquedas igual alimentan el caché global).")
        else:
            if user_email:
                rem = remaining_searches(user_email, DAILY_LIMIT)
                st.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
            else:
                st.warning("No pude detectar el email del usuario en sesión.")
                with st.expander("Debug: session_state keys"):
                    for k, v in st.session_state.items():
                        if isinstance(v, str):
                            st.write(f"- {k}: str ({v[:3]}...)")
                        else:
                            st.write(f"- {k}: {type(v).__name__}")

    # ✅ Ajuste: input centrado (no full width)
    left, center, right = st.columns([1, 2, 1])
    with center:
        with st.form("search_form", clear_on_submit=False):
            ticker = st.text_input("Ticker", value="AAPL").strip().upper()
            submitted = st.form_submit_button("🔎 Buscar")

    if not submitted:
        st.stop()

    if not ticker:
        st.warning("Ingresa un ticker.")
        st.stop()

    # Consume SOLO si NO es admin
    if (not is_admin) and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            st.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            st.stop()
        with st.sidebar:
            st.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    try:
        static = get_static_data(ticker)
        price = get_price_data(ticker)
        fin = get_financial_data(ticker)  # ✅ para beta/per/eps/target

        prof = static.get("profile", {}) if isinstance(static, dict) else {}
        website = prof.get("website") or ""
        logo_urls = logo_candidates(website)

        # ✅ Ajuste: bloque principal centrado y no expansible
        l2, c2, r2 = st.columns([1, 2, 1])
        with c2:
            if logo_urls:
                st.image(logo_urls[0], width=64)

            # Nombre + ticker (centrado)
            company_name = prof.get("name") or prof.get("ticker") or ticker
            st.subheader(f"{company_name} ({ticker})" if company_name != ticker else ticker)

            # Precio + variación
            last_price = price.get("last_price")
            currency = price.get("currency") or ""
            pct = price.get("pct_change")
            net = price.get("net_change")

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

            # ✅ Ajuste: métricas extra centradas
            beta = fin.get("beta")
            pe_ttm = fin.get("pe_ttm")
            eps_ttm = fin.get("eps_ttm")
            target_1y = fin.get("target_1y")

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Beta", _fmt_float(beta, dec=2))
            with m2:
                st.metric("PER (TTM)", _fmt_float(pe_ttm, dec=2))
            with m3:
                st.metric("EPS (TTM)", _fmt_float(eps_ttm, dec=2))
            with m4:
                # target suele ser precio, no %
                if isinstance(target_1y, (int, float)):
                    st.metric("Target 1Y (est.)", f"{float(target_1y):.2f} {currency}".strip())
                else:
                    st.metric("Target 1Y (est.)", "N/D")

        # -----------------------------
        # Resto (por ahora lo dejamos igual, después lo “qualtrimizamos”)
        # -----------------------------
        st.divider()
        st.info("Base OK. Próximo: layout tipo Qualtrim (gráficos expandibles por métrica).")

        years = 5
        perf = get_perf_metrics(ticker, years=years)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(
                "CAGR (aprox)",
                f"{perf['cagr']*100:.2f}%" if isinstance(perf.get("cagr"), (int, float)) else "N/D",
            )
        with c2:
            st.metric(
                "Volatilidad anual",
                f"{perf['volatility']*100:.2f}%" if isinstance(perf.get("volatility"), (int, float)) else "N/D",
            )
        with c3:
            st.metric(
                "Max Drawdown",
                f"{perf['max_drawdown']*100:.2f}%" if isinstance(perf.get("max_drawdown"), (int, float)) else "N/D",
            )

        with st.expander("📈 Precio histórico (5Y)", expanded=False):
            h = get_history_daily(ticker, years=years)
            if h is None or h.empty:
                st.warning("Sin datos históricos.")
            else:
                st.line_chart(h["Close"])

        with st.expander("📉 Drawdown (5Y)", expanded=False):
            dd = get_drawdown_daily(ticker, years=years)
            if dd is None or dd.empty or "Drawdown" not in dd.columns:
                st.warning("Sin datos de drawdown.")
            else:
                st.line_chart(dd["Drawdown"])

        with st.expander("💸 Dividendos (5Y)", expanded=False):
            dm = get_dividend_metrics(ticker, years=5)

            d1, d2, d3 = st.columns(3)
            with d1:
                st.metric(
                    "Dividendo TTM",
                    _fmt_float(dm.get("ttm_dividend"), dec=2),
                )
            with d2:
                y = dm.get("ttm_yield")
                st.metric("Yield TTM", f"{y*100:.2f}%" if isinstance(y, (int, float)) else "N/D")
            with d3:
                c = dm.get("div_cagr")
                st.metric("CAGR Div (aprox)", f"{c*100:.2f}%" if isinstance(c, (int, float)) else "N/D")

            divs = get_dividends_series(ticker, years=5)
            if divs is None or divs.empty:
                st.warning("Sin dividendos disponibles para este ticker.")
            else:
                st.line_chart(divs["Dividend"])

            annual = get_dividends_by_year(ticker, years=5)
            if annual is not None and not annual.empty:
                st.bar_chart(annual.set_index("Year")["Dividends"])

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
