from __future__ import annotations

import streamlit as st

from .. import adapters
from ..state import get_case, set_case
from ..utils import download_json_button


def render():
    case = get_case()
    st.title("Extracción y estado")
    st.caption("Ejecuta las canalizaciones y consulta los artefactos generados.")

    if not (case.files.get("escritura_path") and case.files.get("modelo_path")):
        with st.container(border=True):
            st.subheader("Faltan documentos para procesar")
            st.write(
                "Carga la escritura y el Modelo 600 desde la sección de recepción para poder extraer la información."
            )
            st.button(
                "Ir a carga y recepción",
                on_click=lambda: st.session_state.update({"nav_page": "Carga y recepción"}),
                type="secondary",
                help="Acceso rápido para completar la carga",
            )
        return

    with st.container(border=True):
        st.subheader("Estado de preparación")
        col1, col2 = st.columns(2)
        with col1:
            st.badge("Escritura lista", color="green") if case.files.get("escritura_path") else st.badge(
                "Escritura pendiente", color="orange"
            )
        with col2:
            st.badge("Modelo 600 listo", color="green") if case.files.get("modelo_path") else st.badge(
                "Modelo 600 pendiente", color="orange"
            )

    st.divider()

    if st.button("Ejecutar extracción ahora", type="primary"):
        with st.status("Ejecutando canalizaciones", expanded=True, state="running"):
            st.write("Lanzando OCR y extracción estructurada para ambos documentos...")
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
            case.comparison = adapters.run_comparison(case.extracted["escritura"], case.extracted["modelo"])
            set_case(case)
            st.write("Canalizaciones completadas correctamente.")

    with st.container(border=True):
        st.subheader("Artefactos descargables")
        col1, col2, col3 = st.columns(3)
        with col1:
            download_json_button(
                "Descargar extracción de escritura", case.extracted.get("escritura", {}), "escritura_extracted.json"
            )
        with col2:
            download_json_button(
                "Descargar extracción de Modelo 600", case.extracted.get("modelo", {}), "modelo_extracted.json"
            )
        with col3:
            download_json_button("Descargar comparación", case.comparison or {}, "comparison_report.json")

    st.divider()
    st.subheader("Metadatos del caso")
    st.json(case.meta)


