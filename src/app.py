from __future__ import annotations

import streamlit as st

from ui.state import ensure_session
from ui.pages import (
    upload_intake,
    extraction_status,
    review_discrepancies,
    properties_matcher,
    decision_report,
    settings,
)


st.set_page_config(page_title="Revisión Escritura + Modelo 600", layout="wide")
ensure_session()

PAGES = {
    "Carga y recepción": upload_intake.render,
    "Extracción y estado": extraction_status.render,
    "Revisión y discrepancias": review_discrepancies.render,
    "Inmuebles (coincidencias)": properties_matcher.render,
    "Decisión e informe": decision_report.render,
    "Ajustes": settings.render,
}

with st.sidebar:
    page = st.radio("Navegación", list(PAGES.keys()), key="nav_page")
    case = st.session_state.get("case", {})
    st.caption(f"Caso activo: {case.get('id', '—')}")

PAGES[page]()
