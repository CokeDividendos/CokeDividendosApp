# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import get_static_data, get_price_data
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all
from src.services.finance_data import get_history_daily, get_drawdown_daily, get_perf_metrics



def _get_user_email() -> str:
    candidates = ["user_email", "email", "username", "user", "auth_email", "logged_email"]
    for k in candidates:
        v = st.session_state.get(k)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


def _get_user_role() -> str:
    """
    Best-effort: intenta detectar rol desde session_state.
    Ajusta/añade keys si tu auth usa otra.
    """
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

    # Fallback: si tu auth no guarda role, pero sí guarda flags
    # (ajusta si aplica)
    if st.session_state.get("is_admin") is True:
        return True

    return False


def page_analysis():
    DAILY_LIMIT = 5

    colA, colB = st.columns([0.7, 0.3])
    with colA:
        st.title("📊 Análisis Financiero")
    with colB:
        if st.button("🧹 Limpiar caché", use_container_width=True, key="btn_clear_cache"):
            cache_clear_all()
            st.success("Caché limpiado.")
            st.rerun()

    user_email = _get_user_email()
    is_admin = _is_admin()

    with st.sidebar:
        logout_button()  # ojo: en auth.py debe tener key fija (key="logout_button")

        # UI de límites
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

    # --- FORM: solo consume al presionar Buscar ---
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

        st.info("Base OK. Próximo: histórico de precio + dividendos + ratios.")

        # -----------------------------
        # HISTÓRICO + DRAWDOWN + MÉTRICAS
        # -----------------------------
        years = 5

        perf = get_perf_metrics(ticker, years=years)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("CAGR (aprox)", f"{perf['cagr']*100:.2f}%" if isinstance(perf.get("cagr"), (int, float)) else "N/D")
        with c2:
            st.metric("Volatilidad anual", f"{perf['volatility']*100:.2f}%" if isinstance(perf.get("volatility"), (int, float)) else "N/D")
        with c3:
            st.metric("Max Drawdown", f"{perf['max_drawdown']*100:.2f}%" if isinstance(perf.get("max_drawdown"), (int, float)) else "N/D")

        with st.expander("📈 Precio histórico (5Y)", expanded=True):
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
                # Drawdown ya viene en proporción (0 a -1)
                st.line_chart(dd["Drawdown"])


        
    except Exception as e:
        st.error(f"Ocurrió un error: {e}")
