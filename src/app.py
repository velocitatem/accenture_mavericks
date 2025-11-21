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
    "Upload & Intake": upload_intake.render,
    "Extraction & Status": extraction_status.render,
    "Review & Discrepancies": review_discrepancies.render,
    "Properties (Matcher)": properties_matcher.render,
    "Decision & Report": decision_report.render,
    "Case overview": settings.render,
}

with st.sidebar:
    page = st.radio("Navegación", list(PAGES.keys()))
    case = st.session_state.get("case", {})
    st.caption(f"Caso: {case.get('id', '—')}")

PAGES[page]()
