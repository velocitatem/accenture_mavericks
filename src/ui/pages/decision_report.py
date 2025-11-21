from __future__ import annotations

import streamlit as st

from ..navigation import require_stage
from ..report import build_report, build_report_html, export_case_json
from ..state import CaseState, Decision, get_case, set_case


def render():
    case = get_case()
    st.header("Decisión y reporte")

    require_stage("decision", case)

    opciones = {
        "Aprobar": "approve",
        "Solicitar información": "request_info",
        "Rechazar": "reject",
    }
    decision = case.decision.status if case.decision else "approve"
    choice_label = {
        v: k for k, v in opciones.items()
    }.get(decision, "Aprobar")
    choice = st.radio("Decisión", list(opciones.keys()), index=list(opciones.keys()).index(choice_label))
    notes = st.text_area(
        "Notas", value=case.decision.notes if case.decision else "", help="Agrega comentarios o requisitos de información."
    )

    if st.button("Guardar decisión"):
        status_value = opciones[choice]
        if status_value in {"reject", "request_info"} and not notes.strip():
            st.warning("Añade notas obligatorias para rechazar o solicitar información.")
        else:
            case.decision = Decision(status=status_value, notes=notes)
            set_case(case)
            st.success("Decisión guardada y lista para el reporte.")

    st.markdown("### Exportar")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Exportar caso (JSON)", export_case_json(case), "case.json")
    with col2:
        st.download_button("Generar reporte PDF", build_report(case), "case_report.pdf")

    st.markdown("### Vista previa")
    st.components.v1.html(build_report_html(case), height=300, scrolling=True)


