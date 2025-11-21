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
    st.title("Revisión y discrepancias")
    st.caption("Compara los resultados de extracción y corrige campos clave.")

    if not case.extracted.get("escritura"):
        with st.container(border=True):
            st.subheader("No hay datos extraídos aún")
            st.write("Ejecuta la extracción para ver y editar discrepancias entre documentos.")
            st.button(
                "Ir a Extracción y estado",
                on_click=lambda: st.session_state.update({"nav_page": "Extracción y estado"}),
                type="secondary",
                help="Atajo accesible para lanzar las canalizaciones",
            )
        return

    col_left, col_center, col_right = st.columns([1.2, 1.6, 1.2])
    with col_left:
        st.subheader("Escritura")
        show_pdf(case.files.get("escritura_path"))
    with col_right:
        st.subheader("Modelo 600")
        show_pdf(case.files.get("modelo_path"))

    with col_center:
        issues = _collect_issues(case)

        def on_edit(field_path: str, new_value):
            old = case.extracted["escritura"].get(field_path)
            set_deep(case.extracted["escritura"], field_path, new_value)
            log_edit(case, field_path, old, new_value, reason="manual edit")
            case.validation["escritura"] = adapters.fast_validate("escritura", case.extracted["escritura"])
            set_case(case)
            st.experimental_rerun()

        render_discrepancies(issues, on_edit=on_edit)

        st.subheader("Normalizadores rápidos")
        col1, col2 = st.columns(2)
        with col1:
            value = st.text_input("Normalizar referencia catastral")
            if st.button("Normalizar", key="norm_ref"):
                norm = normalize_cadastral_ref(value)
                st.success(f"Referencia normalizada: {norm}")
        with col2:
            nif_val = st.text_input("Comprobar NIF")
            if st.button("Validar NIF"):
                st.info(f"Resultado de validación: {validate_nif(nif_val)}")


