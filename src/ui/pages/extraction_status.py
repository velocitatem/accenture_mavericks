from __future__ import annotations

import streamlit as st

from .. import adapters
from ..navigation import require_stage
from ..state import get_case, set_case
from ..utils import download_json_button


def render():
    case = get_case()
    st.header("Estado de extracción")

    require_stage("extraction", case)

    st.info(
        "Ejecuta la extracción para obtener OCR, campos clave y validaciones automáticas."
    )

    if st.button("Ejecutar extracción"):
        with st.spinner("Procesando documentos..."):
            escritura_res = adapters.run_escritura_pipeline(case.files["escritura_path"])
            modelo_res = adapters.run_modelo_pipeline(case.files["modelo_path"])
            case.ocr["escritura"] = escritura_res["ocr_text"]
            case.ocr["modelo"] = modelo_res["ocr_text"]
            case.extracted["escritura"] = escritura_res["extracted"]
            case.extracted["modelo"] = modelo_res["extracted"]
            case.validation["escritura"] = escritura_res["validation"]
            case.validation["modelo"] = modelo_res["validation"]
            case.meta.setdefault("timings", {})["escritura"] = escritura_res["meta"]
            case.meta.setdefault("timings", {})["modelo"] = modelo_res["meta"]
            case.comparison = adapters.run_comparison(
                case.extracted["escritura"], case.extracted["modelo"]
            )
            set_case(case)
            st.success("Extracción completada. Revisa las discrepancias en el siguiente paso.")

    st.subheader("Resumen del pipeline")
    etapas = st.columns(4)
    etapas[0].metric("OCR", "Listo" if case.ocr.get("escritura") else "Pendiente")
    etapas[1].metric("Extracción", "Listo" if case.extracted.get("escritura") else "Pendiente")
    etapas[2].metric(
        "Validación",
        "Listo" if case.validation.get("escritura") else "Pendiente",
    )
    etapas[3].metric("Comparación", "Listo" if case.comparison else "Pendiente")

    st.divider()
    st.markdown("### Descargas técnicas")
    col1, col2, col3 = st.columns(3)
    with col1:
        download_json_button(
            "Extracción escritura (JSON)",
            case.extracted.get("escritura", {}),
            "escritura_extracted.json",
        )
    with col2:
        download_json_button(
            "Extracción Modelo 600 (JSON)",
            case.extracted.get("modelo", {}),
            "modelo_extracted.json",
        )
    with col3:
        download_json_button(
            "Comparación (JSON)",
            case.comparison or {},
            "comparison_report.json",
        )


