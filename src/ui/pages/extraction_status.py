from __future__ import annotations

import streamlit as st

from .. import adapters
from ..state import get_case, set_case
from ..utils import download_json_button


def render():
    case = get_case()
    st.header("Extraction & Status")

    if not (case.files.get("escritura_path") and case.files.get("modelo_path")):
        st.warning("Upload documents first.")
        return

    if st.button("Run extraction now"):
        with st.spinner("Running pipelines..."):
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
            st.success("Pipelines completed")

    st.subheader("Artifacts")
    col1, col2, col3 = st.columns(3)
    with col1:
        download_json_button("Download escritura extraction", case.extracted.get("escritura", {}), "escritura_extracted.json")
    with col2:
        download_json_button("Download modelo extraction", case.extracted.get("modelo", {}), "modelo_extracted.json")
    with col3:
        download_json_button("Download comparison", case.comparison or {}, "comparison_report.json")

    st.json(case.meta)


