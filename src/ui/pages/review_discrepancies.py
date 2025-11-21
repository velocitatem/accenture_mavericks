from __future__ import annotations

import streamlit as st

from .. import adapters
from ..components.pdf_viewer import show_pdf
from ..components.discrepancy_table import render_discrepancies
from ..components.field_editors import set_deep
from ..navigation import require_stage
from ..state import get_case, set_case, log_edit


def _collect_issues(case):
    issues = []
    for doc in ("escritura", "modelo"):
        doc_val = case.validation.get(doc) or {}
        if isinstance(doc_val, dict) and doc_val.get("issues"):
            issues.extend(doc_val["issues"])
    if case.comparison:
        # comparison list
        if isinstance(case.comparison, list):
            for item in case.comparison:
                issues.extend(item.get("issues", []))
    return issues


def render():
    case = get_case()
    st.header("Revisión y discrepancias")

    require_stage("review", case)

    issues = _collect_issues(case)
    edit_mode = st.toggle("Modo edición", value=False, help="Activa para ajustar valores de la escritura.")

    def on_edit(field_path: str, new_value):
        old = case.extracted["escritura"].get(field_path)
        set_deep(case.extracted["escritura"], field_path, new_value)
        log_edit(case, field_path, old, new_value, reason="edición manual")
        case.validation["escritura"] = adapters.fast_validate("escritura", case.extracted["escritura"])
        set_case(case)
        st.experimental_rerun()

    render_discrepancies(issues, on_edit=on_edit if edit_mode else None, editable=edit_mode)
    st.caption("Activa el modo edición para habilitar cambios controlados sobre los campos discrepantes.")

    st.divider()
    st.markdown("### Documentos")
    col_left, col_right = st.columns(2)
    with col_left:
        st.caption("Escritura")
        show_pdf(case.files.get("escritura_path"))
    with col_right:
        st.caption("Modelo 600")
        show_pdf(case.files.get("modelo_path"))

    if case.comparison and not case.meta.get("revision_lista"):
        case.meta["revision_lista"] = True
        set_case(case)


