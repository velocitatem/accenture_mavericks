from __future__ import annotations

import streamlit as st

from ..report import build_report, build_report_html, export_case_json
from ..state import CaseState, Decision, get_case, set_case


def render():
    case = get_case()
    st.title("Decisión e informe")
    st.caption("Registra la resolución final y genera el informe para compartir.")

    decision = case.decision.status if case.decision else "approve"
    choice = st.radio(
        "Decisión",
        ["approve", "request_info", "reject"],
        index=["approve", "request_info", "reject"].index(decision),
        help="Selecciona el resultado de la revisión",
    )
    notes = st.text_area("Notas", value=case.decision.notes if case.decision else "", help="Añade contexto para el solicitante")

    if st.button("Guardar decisión", type="primary"):
        case.decision = Decision(status=choice, notes=notes)
        set_case(case)
        st.success("Decisión guardada")

    st.subheader("Exportar")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Exportar caso en JSON", export_case_json(case), "case.json")
    with col2:
        st.download_button("Generar informe PDF", build_report(case), "case_report.pdf")

    st.subheader("Vista previa")
    st.components.v1.html(build_report_html(case), height=300, scrolling=True)


