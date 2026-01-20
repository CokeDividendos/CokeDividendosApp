# src/pages/analysis.py
import streamlit as st

from src.auth import logout_button
from src.services.cache_store import cache_clear_all
from src.services.logos import logo_candidates
from src.services.usage_limits import remaining_searches, consume_search

from src.services.finance_data import (
    get_static_data,
    get_price_data,
    get_profile_data,          # <-- para nombre + beta/PE/EPS/target
    get_history_daily,
    get_drawdown_daily,
    get_perf_metrics,
    get_dividends_series,
    get_dividends_by_year,
    get_dividend_metrics,
)


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


def _fmt_num(x, decimals=2, suffix=""):
    if isinstance(x, (int, float)) and x is not None:
        return f"{x:.{decimals}f}{suffix}"
    return "N/D"


def _fmt_pct(x, decimals=2):
    if isinstance(x, (int, float)) and x is not None:
        return f"{x*100:.{decimals}f}%"
    return "N/D"


def page_analysis():
    # ==========================
    # CONFIG
    # ==========================
    DAILY_LIMIT = 3
    years = 5

    user_email = _get_user_email()
    is_admin = _is_admin()

    # ==========================
    # SIDEBAR
    # ==========================
    with st.sidebar:
        logout_button()  # ojo: en auth.py debe tener key fija (key="logout_button")

        # Un SOLO placeholder para que no se duplique el contador
        rem_box = st.empty()

        if is_admin:
            rem_box.success("👑 Admin: sin límite diario (las búsquedas igual alimentan el caché global).")
        else:
            if user_email:
                rem = remaining_searches(user_email, DAILY_LIMIT)
                rem_box.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
            else:
                rem_box.warning("No pude detectar el email del usuario en sesión.")

    # ==========================
    # HEADER (con botón cache sólo para Admin)
    # ==========================
    colA, colB = st.columns([0.75, 0.25])
    with colA:
        st.title("📊 Análisis Financiero")

    with colB:
        if is_admin:
            if st.button("🧹 Limpiar caché", use_container_width=True, key="btn_clear_cache"):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()

    # ==========================
    # CSS / Layout: centra input + bloque resumen
    # ==========================
    st.markdown(
        """
        <style>
          /* “tarjeta” central para que no se estire con pantallas grandes */
          .cd-center {
            max-width: 760px;
            margin-left: auto;
            margin-right: auto;
          }
          /* separador suave */
          .cd-divider {
            margin: 18px 0 6px 0;
            height: 1px;
            background: rgba(0,0,0,0.08);
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Contenedor centrado (input + summary)
    st.markdown('<div class="cd-center">', unsafe_allow_html=True)

    # --- FORM: solo consume al presionar Buscar ---
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")

    if not submitted:
        st.markdown("</div>", unsafe_allow_html=True)  # cierra cd-center
        st.stop()

    if not ticker:
        st.warning("Ingresa un ticker.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # Consume SOLO si NO es admin
    if (not is_admin) and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            with st.sidebar:
                # Actualiza el mismo “box”, sin duplicar
                st.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()

        # Actualiza el contador (mismo placeholder) sin duplicar
        with st.sidebar:
            # recreamos el box dentro del sidebar actual para mantener el comportamiento
            # (Streamlit no permite referenciar el rem_box creado antes desde otro scope fácilmente sin session)
            st.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    try:
        # ==========================
        # DATA FETCH
        # ==========================
        static = get_static_data(ticker)
        price = get_price_data(ticker)

        # Perfil “raw” (yfinance info) para nombre + beta/per/eps/target
        prof_full = get_profile_data(ticker) or {}
        raw = prof_full.get("raw", {}) if isinstance(prof_full, dict) else {}

        prof = static.get("profile", {}) if isinstance(static, dict) else {}

        # --- Logo (best-effort)
        website = (prof.get("website") or prof_full.get("website") or raw.get("website") or "") if isinstance(prof_full, dict) else (prof.get("website") or "")
        logo_urls = logo_candidates(website)
        if logo_urls:
            st.image(logo_urls[0], width=64)

        # --- Nombre empresa (fallbacks)
        company_name = (
            prof.get("name")
            or prof_full.get("shortName")
            or raw.get("shortName")
            or raw.get("longName")
            or "N/D"
        )

        st.subheader(ticker)

        # ==========================
        # PRECIO + VARIACIÓN (centrado)
        # ==========================
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

        # ==========================
        # BLOQUE RESUMEN (centrado) - Empresa + Beta/PE/EPS/Target
        # ==========================
        st.markdown('<div class="cd-divider"></div>', unsafe_allow_html=True)

        # Empresa (nombre) en una línea, bien simple
        st.caption("Empresa")
        st.markdown(f"**{company_name}**")

        # Métricas extra desde yfinance info (raw)
        beta = raw.get("beta")
        pe_ttm = raw.get("trailingPE")
        eps_ttm = raw.get("epsTrailingTwelveMonths") or raw.get("trailingEps")
        target_1y = raw.get("targetMeanPrice") or raw.get("targetHighPrice")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Beta", _fmt_num(beta, 2))
        with c2:
            # PER es “x”
            st.metric("PER (TTM)", (_fmt_num(pe_ttm, 2) + "x") if isinstance(pe_ttm, (int, float)) else "N/D")
        with c3:
            st.metric("EPS (TTM)", _fmt_num(eps_ttm, 2))
        with c4:
            st.metric("Target 1Y (est.)", _fmt_num(target_1y, 2))

        # También mantengo Exchange/Asset class pero sin “estirar” con 3 columnas enormes
        c5, c6, c7 = st.columns(3)
        with c5:
            st.metric("Exchange", price.get("exchange") or prof.get("exchange") or "N/D")
        with c6:
            st.metric("Asset Class", price.get("asset_class") or "N/D")
        with c7:
            st.metric("Ticker", ticker)

        if vol is not None:
            try:
                st.caption(f"Volumen: {int(vol):,}".replace(",", "."))
            except Exception:
                st.caption(f"Volumen: {vol}")
        if asof:
            st.caption(f"Fecha: {asof}")

        st.info("Base OK. Próximo: layout tipo Qualtrim (gráficos expandibles por métrica).")

        # Cierra el contenedor centrado
        st.markdown("</div>", unsafe_allow_html=True)

        # ==========================
        # BLOQUES EXPANDIBLES (pueden usar full width)
        # ==========================

        perf = get_perf_metrics(ticker, years=years)
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("CAGR (aprox)", f"{perf['cagr']*100:.2f}%" if isinstance(perf.get("cagr"), (int, float)) else "N/D")
        with k2:
            st.metric("Volatilidad anual", f"{perf['volatility']*100:.2f}%" if isinstance(perf.get("volatility"), (int, float)) else "N/D")
        with k3:
            st.metric("Max Drawdown", f"{perf['max_drawdown']*100:.2f}%" if isinstance(perf.get("max_drawdown"), (int, float)) else "N/D")

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
            dm = get_dividend_metrics(ticker, years=years)

            d1, d2, d3 = st.columns(3)
            with d1:
                st.metric("Dividendo TTM", f"{dm['ttm_dividend']:.2f}" if isinstance(dm.get("ttm_dividend"), (int, float)) else "N/D")
            with d2:
                st.metric("Yield TTM", f"{dm['ttm_yield']*100:.2f}%" if isinstance(dm.get("ttm_yield"), (int, float)) else "N/D")
            with d3:
                st.metric("CAGR Div (aprox)", f"{dm['div_cagr']*100:.2f}%" if isinstance(dm.get("div_cagr"), (int, float)) else "N/D")

            divs = get_dividends_series(ticker, years=years)
            if divs is None or divs.empty:
                st.warning("Sin dividendos disponibles para este ticker.")
            else:
                st.line_chart(divs["Dividend"])

            annual = get_dividends_by_year(ticker, years=years)
            if annual is not None and not annual.empty:
                st.bar_chart(annual.set_index("Year")["Dividends"])

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
