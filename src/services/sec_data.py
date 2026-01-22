# src/services/sec_data.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.services.cache_store import cache_get, cache_set
from src.services.sec_client import get_json
from src.services.sec_ticker_map import ticker_to_cik10


# ---------- Helpers ----------
def _pick_units(concept: dict) -> Optional[List[dict]]:
    """
    Devuelve la lista de facts para la unidad más típica (USD) si existe.
    """
    if not isinstance(concept, dict):
        return None
    units = concept.get("units")
    if not isinstance(units, dict):
        return None
    # Prefer USD
    for k in ("USD", "usd"):
        if k in units and isinstance(units[k], list):
            return units[k]
    # Fallback: primera unidad disponible
    for _, arr in units.items():
        if isinstance(arr, list):
            return arr
    return None


def _annual_facts(arr: List[dict]) -> List[dict]:
    """
    Filtra facts que correspondan a anual (10-K/20-F/40-F) y fp=FY cuando exista.
    """
    out = []
    for it in arr:
        if not isinstance(it, dict):
            continue
        form = str(it.get("form") or "")
        fp = str(it.get("fp") or "")
        # Consideramos 10-K y variantes, y reportes anuales extranjeros
        is_annual_form = form.startswith("10-K") or form in ("20-F", "40-F")
        if not is_annual_form:
            continue
        # Muchas veces fp = FY. Si no viene, igual lo aceptamos si hay end date.
        if fp and fp != "FY":
            continue
        if not it.get("end"):
            continue
        out.append(it)
    return out


def _latest_by_year(arr: List[dict]) -> Dict[int, dict]:
    """
    De un listado anual, toma el último fact por año (según 'filed' y luego según aparición).
    """
    best: Dict[int, dict] = {}
    for it in arr:
        end = str(it.get("end") or "")
        if len(end) < 4:
            continue
        try:
            y = int(end[:4])
        except Exception:
            continue
        filed = str(it.get("filed") or "")
        prev = best.get(y)
        if prev is None:
            best[y] = it
        else:
            # si filed es mayor, reemplaza
            prev_filed = str(prev.get("filed") or "")
            if filed and (not prev_filed or filed > prev_filed):
                best[y] = it
    return best


def _series_from_companyfacts(facts: dict, tag: str) -> List[dict]:
    """
    Retorna lista de registros anuales ordenados: [{"year":YYYY,"end":"YYYY-MM-DD","value":float}]
    """
    if not isinstance(facts, dict):
        return []
    usgaap = facts.get("facts", {}).get("us-gaap", {})
    concept = usgaap.get(tag)
    if not isinstance(concept, dict):
        return []
    arr = _pick_units(concept)
    if not arr:
        return []

    annual = _annual_facts(arr)
    best = _latest_by_year(annual)

    rows: List[dict] = []
    for y in sorted(best.keys()):
        it = best[y]
        v = it.get("val")
        try:
            v = float(v)
        except Exception:
            v = None
        rows.append({"year": y, "end": str(it.get("end")), "value": v})
    return rows


# ---------- Public API ----------
def get_companyfacts_by_ticker(ticker: str, ttl_seconds: int = 60 * 60 * 24) -> dict:
    """
    Descarga companyfacts y cachea. TTL recomendado 24h.
    """
    cik10 = ticker_to_cik10(ticker)
    if not cik10:
        return {}

    key = f"sec:companyfacts:{cik10}"
    hit = cache_get(key)
    if isinstance(hit, dict) and hit:
        return hit

    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
    data = get_json(url)
    cache_set(key, data, ttl_seconds=ttl_seconds)
    return data


def get_fundamentals_minimal(ticker: str) -> dict:
    """
    Devuelve un set mínimo de series y últimos valores para gráficos/ratios.

    Series anuales:
      - Assets, Liabilities, StockholdersEquity
      - Revenues, GrossProfit (si existe), NetIncomeLoss
      - Operating Cash Flow, CapEx, Free Cash Flow (OCF + CapEx si CapEx es negativo)
      - Cash & Equivalents (si existe)
      - Debt (best effort)
    """
    facts = get_companyfacts_by_ticker(ticker)
    if not facts:
        return {}

    # Tags US-GAAP (estándar)
    tags = {
        "assets": "Assets",
        "liabilities": "Liabilities",
        "equity": "StockholdersEquity",
        "revenue": "Revenues",
        "gross_profit": "GrossProfit",
        "net_income": "NetIncomeLoss",
        "operating_cf": "NetCashProvidedByUsedInOperatingActivities",
        "capex": "PaymentsToAcquirePropertyPlantAndEquipment",
        "cash": "CashAndCashEquivalentsAtCarryingValue",
        # Deuda: best effort (no todas reportan igual)
        "debt": "Debt",
    }

    series: Dict[str, List[dict]] = {k: _series_from_companyfacts(facts, tag) for k, tag in tags.items()}

    # Free Cash Flow = OCF + CapEx (CapEx suele ser negativo)
    fcf_rows: List[dict] = []
    ocf_map = {r["year"]: r for r in series.get("operating_cf", []) if r.get("value") is not None}
    cap_map = {r["year"]: r for r in series.get("capex", []) if r.get("value") is not None}
    for y in sorted(set(ocf_map.keys()) & set(cap_map.keys())):
        ocf = float(ocf_map[y]["value"])
        cap = float(cap_map[y]["value"])
        fcf = ocf + cap
        end = ocf_map[y].get("end") or cap_map[y].get("end")
        fcf_rows.append({"year": y, "end": end, "value": fcf})
    series["free_cf"] = fcf_rows

    # Últimos valores (por año más reciente presente)
    def _latest_value(key: str) -> Optional[float]:
        arr = series.get(key) or []
        for r in reversed(arr):
            v = r.get("value")
            if isinstance(v, (int, float)):
                return float(v)
        return None

    latest_year = None
    # buscamos el último año disponible en revenue o assets
    for candidate in ("revenue", "assets", "net_income"):
        arr = series.get(candidate) or []
        if arr:
            latest_year = arr[-1].get("year")
            break

    return {
        "ticker": (ticker or "").strip().upper(),
        "latest_year": latest_year,
        "series": series,
        "latest": {
            "assets": _latest_value("assets"),
            "liabilities": _latest_value("liabilities"),
            "equity": _latest_value("equity"),
            "revenue": _latest_value("revenue"),
            "gross_profit": _latest_value("gross_profit"),
            "net_income": _latest_value("net_income"),
            "operating_cf": _latest_value("operating_cf"),
            "capex": _latest_value("capex"),
            "free_cf": _latest_value("free_cf"),
            "cash": _latest_value("cash"),
            "debt": _latest_value("debt"),
        },
    }
