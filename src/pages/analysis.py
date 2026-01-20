# src/pages/analysis.py
import streamlit as st

from src.services.usage_limits import remaining_searches, consume_search
from src.services.finance_data import get_price_data, get_profile_data, get_key_stats
from src.services.logos import logo_candidates
from src.auth import logout_button
from src.services.cache_store import cache_clear_all


def _get_user_email() -> str:
    for key in ["user_email", "email", "username", "user", "auth_email", "logged_email"]:
        v = st.session_state.get(key)
        if isinstance(v, str) and "@" in v:
            return v.strip().lower()
    return ""


def _get_user_role() -> str:
    for key in ["role", "user_role", "auth_role", "logged_role"]:
        v = st.session_state.get(key)
        if isinstance(v, str) and v:
            return v.strip().lower()
    return ""


def _is_admin() -> bool:
    # User is admin if role=admin or a separate flag is set
    return _get_user_role() == "admin" or st.session_state.get("is_admin") is True


def _fmt_price(x, currency: str) -> str:
    return f"{x:,.2f} {currency}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(x, (int, float)) else "N/D"


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

    # Sidebar: logout and cache clear button (only admin)
    with st.sidebar:
        logout_button()  # logout_button has key="logout_button"
        if is_admin:
            # Clear cache only for admin
            if st.button("🧹 Limpiar caché", use_container_width=True):
                cache_clear_all()
                st.success("Caché limpiado.")
                st.rerun()
        # Show remaining searches or admin message
        if is_admin:
            st.success("👑 Admin: sin límite diario (las búsquedas igual alimentan el caché global).")
        else:
            if user_email:
                rem = remaining_searches(user_email, DAILY_LIMIT)
                st.info(f"🔎 Búsquedas restantes hoy: {rem}/{DAILY_LIMIT}")
            else:
                st.warning("No se detectó el correo del usuario.")

    # CSS: wrap main content in a fixed-width container
    st.markdown(
        """
        <style>
          /* Main container fixed width and centered */
          .analysis-wrapper {
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
            padding-left: 12px;
            padding-right: 12px;
          }
          /* Card-like section for form and KPIs */
          .analysis-card {
            padding: 16px 18px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.8);
            margin-top: 16px;
          }
          @media (prefers-color-scheme: dark) {
            .analysis-card {
              background: rgba(30, 30, 30, 0.7);
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Main wrapper div start
    st.markdown('<div class="analysis-wrapper">', unsafe_allow_html=True)

    # Title
    st.markdown("## 📊 Análisis Financiero")

    # Search form in a card (prevents expansion)
    st.markdown('<div class="analysis-card">', unsafe_allow_html=True)
    with st.form("search_form", clear_on_submit=False):
        ticker = st.text_input("Ticker", value="AAPL").strip().upper()
        submitted = st.form_submit_button("🔎 Buscar")
    st.markdown("</div>", unsafe_allow_html=True)

    # If form not submitted yet, stop here
    if not submitted:
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if not ticker:
        st.warning("Ingresa un ticker.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Limit searches for non-admins
    if not is_admin and user_email:
        ok, rem_after = consume_search(user_email, DAILY_LIMIT, cost=1)
        if not ok:
            st.error("🚫 Búsquedas diarias alcanzadas. Vuelve mañana.")
            st.markdown("</div>", unsafe_allow_html=True)
            return
        # Update remaining search count in sidebar
        st.sidebar.info(f"🔎 Búsquedas restantes hoy: {rem_after}/{DAILY_LIMIT}")

    # Fetch data
    price = get_price_data(ticker) or {}
    profile = get_profile_data(ticker) or {}
    raw = profile.get("raw") if isinstance(profile, dict) else {}
    stats = get_key_stats(ticker) or {}

    # Determine company name
    company_name = (
        raw.get("longName")
        or raw.get("shortName")
        or profile.get("shortName")
        or ticker
    )

    # Price and variation
    last_price = price.get("last_price")
    currency = price.get("currency") or ""
    delta_txt = _fmt_delta(price.get("net_change"), price.get("pct_change"))

    # Get logo (best effort)
    website = (profile.get("website") or raw.get("website") or "")
    logos = logo_candidates(website) if website else []
    logo_url = next((u for u in logos if isinstance(u, str) and u.startswith(("http://", "https://"))), "")

    # -----------------------------
    # Card: Name & Price row
    # -----------------------------
    st.markdown('<div class="analysis-card">', unsafe_allow_html=True)

    # Row with logo, name and price + delta
    cols = st.columns([0.13, 0.60, 0.27], gap="small")
    with cols[0]:
        if logo_url:
            st.image(logo_url, width=50)
    with cols[1]:
        st.markdown(f"### {company_name}")
        st.caption(ticker)
    with cols[2]:
        st.markdown(f"### {_fmt_price(last_price, currency)}")
        if delta_txt:
            st.caption(delta_txt)

    st.markdown("</div>", unsafe_allow_html=True)

    # -----------------------------
    # Card: KPIs grid (Beta, PER TTM, EPS TTM, Target 1Y)
    # -----------------------------
    st.markdown('<div class="analysis-card">', unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4, gap="small")
    with k1:
        st.caption("Beta")
        st.markdown(f"### {_fmt_kpi(stats.get('beta'))}")
    with k2:
        st.caption("PER TTM")
        pe = stats.get("pe_ttm")
        # Append "x" only if there is a valid PE
        st.markdown(f"### {_fmt_kpi(pe)}" + ("x" if isinstance(pe, (int, float)) else ""))
    with k3:
        st.caption("EPS TTM")
        st.markdown(f"### {_fmt_kpi(stats.get('eps_ttm'))}")
    with k4:
        st.caption("Target 1Y (est.)")
        st.markdown(f"### {_fmt_kpi(stats.get('target_1y'))}")

    st.markdown("</div>", unsafe_allow_html=True)

    # Close main wrapper
    st.markdown("</div>", unsafe_allow_html=True)
