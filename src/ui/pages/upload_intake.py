from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from ..state import get_case, set_case
from ..utils import format_size

_root_up = Path(__file__).resolve().parents[3]
SAMPLE_ESCRITURA = str((_root_up / "Pdfs_prueba" / "Escritura.pdf").resolve())
SAMPLE_MODELO = str((_root_up / "Pdfs_prueba" / "Autoliquidacion.pdf").resolve())

def _copy_uploaded(file) -> str:
    suffix = Path(file.name).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.read())
        return tmp.name


def render():
    case = get_case()
    st.header("Carga de documentos")

    st.info(
        "Carga la escritura **y** el Modelo 600 para iniciar el caso. Ambos documentos son obligatorios para comparar y validar los datos."
    )

    use_samples = st.toggle("Usar datos de ejemplo", value=False, help="Activa un par de PDFs de prueba para explorar el flujo.")
    if use_samples:
        st.caption("Modo demostración activo: se cargarán documentos de ejemplo.")

    if use_samples:
        escritura_path = SAMPLE_ESCRITURA
        modelo_path = SAMPLE_MODELO
    else:
        escritura_file = st.file_uploader(
            "Escritura (PDF)",
            type="pdf",
            help="Arrastra o selecciona el archivo PDF de la escritura.",
        )
        modelo_file = st.file_uploader(
            "Modelo 600 (PDF)",
            type="pdf",
            help="Añade el PDF de la autoliquidación (Modelo 600).",
        )
        escritura_path = _copy_uploaded(escritura_file) if escritura_file else None
        modelo_path = _copy_uploaded(modelo_file) if modelo_file else None

    if escritura_path:
        st.success(
            f"Escritura lista: {Path(escritura_path).name} ({format_size(Path(escritura_path).stat().st_size)})."
        )
    if modelo_path:
        st.success(
            f"Modelo 600 listo: {Path(modelo_path).name} ({format_size(Path(modelo_path).stat().st_size)})."
        )

    st.caption("Consejo: valida que los PDF se lean correctamente antes de continuar.")

    ready = escritura_path and modelo_path

    if st.button("Registrar documentos y continuar", disabled=not ready):
        case.id = case.id or ("CASO-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        case.files["escritura_path"] = escritura_path
        case.files["modelo_path"] = modelo_path
        set_case(case)
        st.success("Documentos registrados. Continúa con la extracción en la barra lateral.")
