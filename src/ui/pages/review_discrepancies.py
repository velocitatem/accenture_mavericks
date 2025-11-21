from __future__ import annotations

import streamlit as st

from .. import adapters
from ..components.pdf_viewer import show_pdf
from ..components.discrepancy_table import render_discrepancies
from ..components.field_editors import set_deep
from ..components.normalizers import normalize_cadastral_ref, validate_nif
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
    st.header("Review & Discrepancies")

    if not case.extracted.get("escritura"):
        st.warning("Run extraction first.")
        return
    issues = _collect_issues(case)

    def on_edit(field_path: str, new_value):
        old = case.extracted["escritura"].get(field_path)
        set_deep(case.extracted["escritura"], field_path, new_value)
        log_edit(case, field_path, old, new_value, reason="manual edit")
        case.validation["escritura"] = adapters.fast_validate("escritura", case.extracted["escritura"])
        set_case(case)
        st.experimental_rerun()

    render_discrepancies(issues, on_edit=on_edit)

    st.markdown("### Quick normalizers")
    col1, col2 = st.columns(2)
    with col1:
        value = st.text_input("Normalize cadastral ref")
        if st.button("Normalize", key="norm_ref"):
            norm = normalize_cadastral_ref(value)
            st.success(f"Normalized: {norm}")
    with col2:
        nif_val = st.text_input("Check NIF")
        if st.button("Validate NIF"):
            st.info(f"Valid: {validate_nif(nif_val)}")

    col_left, col_right = st.columns([1,1])
    with col_left:
        st.caption("Escritura")
        show_pdf(case.files.get("escritura_path"))
    with col_right:
        st.caption("Modelo 600")
        show_pdf(case.files.get("modelo_path"))
