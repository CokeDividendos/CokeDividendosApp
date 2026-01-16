from dataclasses import dataclass
import streamlit as st

@dataclass(frozen=True)
class Settings:
    rapidapi_host: str
    rapidapi_key: str
    db_path: str = "cokeapp2.sqlite"
    cache_ttl_static_seconds: int = 60 * 60 * 24      # 24h
    cache_ttl_price_seconds: int = 60                 # 60s

def get_settings() -> Settings:
    # Streamlit secrets recomendado (Streamlit Cloud)
    # st.secrets["RAPIDAPI_KEY"], st.secrets["RAPIDAPI_HOST"]
    rapidapi_key = st.secrets.get("RAPIDAPI_KEY", "")
    rapidapi_host = st.secrets.get("RAPIDAPI_HOST", "yh-finance.p.rapidapi.com")

    if not rapidapi_key:
        raise RuntimeError("Falta RAPIDAPI_KEY en st.secrets")

    return Settings(
        rapidapi_host=rapidapi_host,
        rapidapi_key=rapidapi_key,
    )

