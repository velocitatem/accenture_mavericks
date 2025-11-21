from __future__ import annotations

import streamlit as st

from ui.navigation import render_sidebar_progress
from ui.state import ensure_session, get_case
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

PAGES = [
    {"label": "Carga de documentos", "renderer": upload_intake.render, "stage": "upload"},
    {"label": "Estado de extracción", "renderer": extraction_status.render, "stage": "extraction"},
    {"label": "Revisión y discrepancias", "renderer": review_discrepancies.render, "stage": "review"},
    {"label": "Propiedades", "renderer": properties_matcher.render, "stage": "review"},
    {"label": "Decisión y reporte", "renderer": decision_report.render, "stage": "decision"},
    {"label": "Información del caso", "renderer": settings.render, "stage": None},
]

page_labels = [p["label"] for p in PAGES]

with st.sidebar:
    page_label = st.radio("Navegación", page_labels)
    case = get_case()
    st.caption(f"Caso: {case.id or '—'}")
    active_page = next(p for p in PAGES if p["label"] == page_label)
    render_sidebar_progress(active_page.get("stage"), case)

active_page["renderer"]()
