from __future__ import annotations

import hashlib
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


def _hash_file(path: str) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def render():
    case = get_case()
    st.title("Carga y recepción de documentos")
    st.caption("Organiza los PDF de la escritura y el Modelo 600 antes de procesarlos.")

    with st.container(border=True):
        st.subheader("Selecciona el origen")
        st.caption("Puedes cargar archivos propios o activar los ejemplos para pruebas rápidas.")
        use_samples = st.toggle("Usar documentos de ejemplo", value=False, key="upload_use_samples")
        col_esc, col_mod = st.columns(2)
        if use_samples:
            escritura_path = SAMPLE_ESCRITURA
            modelo_path = SAMPLE_MODELO
            with st.status("Ejemplos listos para usar", state="complete"):
                st.write("Los PDF de ejemplo están precargados para acelerar las pruebas.")
        else:
            with col_esc:
                escritura_file = st.file_uploader(
                    "Sube la escritura en PDF",
                    type="pdf",
                    help="Se utiliza para validar la compraventa",
                )
                escritura_path = _copy_uploaded(escritura_file) if escritura_file else None
            with col_mod:
                modelo_file = st.file_uploader(
                    "Sube el Modelo 600 en PDF",
                    type="pdf",
                    help="Necesario para cruzar la información fiscal",
                )
                modelo_path = _copy_uploaded(modelo_file) if modelo_file else None

    if not (escritura_path or modelo_path):
        with st.container(border=True):
            st.subheader("Sin archivos todavía")
            st.write(
                "Carga los PDF o activa los ejemplos para habilitar el procesamiento. Esta tarjeta es accesible para lectores de pantalla y detalla los pasos siguientes."
            )
            st.button(
                "Activar documentos de ejemplo",
                type="secondary",
                on_click=lambda: st.session_state.update({"upload_use_samples": True}),
                help="Rellena automáticamente con archivos de muestra",
            )

    status_cols = st.columns(2)
    with status_cols[0]:
        st.metric(
            "Estado de la escritura",
            "Listo" if escritura_path else "Pendiente",
            help="Indica si el PDF de la escritura está disponible",
        )
    with status_cols[1]:
        st.metric(
            "Estado del Modelo 600",
            "Listo" if modelo_path else "Pendiente",
            help="Indica si el PDF fiscal está disponible",
        )

    st.divider()

    ready = escritura_path and modelo_path
    if ready:
        with st.status("Documentos preparados", state="complete"):
            st.write("Puedes lanzar las canalizaciones de extracción cuando lo desees.")
            st.caption("Las métricas incluyen el tamaño de cada archivo para confirmar que la carga es correcta.")
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Tamaño escritura", format_size(Path(escritura_path).stat().st_size))
            with col_b:
                st.metric("Tamaño Modelo 600", format_size(Path(modelo_path).stat().st_size))
    else:
        st.info("Sube ambos documentos para habilitar el procesamiento.")

    if st.button("Ejecutar canalizaciones", disabled=not ready, type="primary"):
        case.id = "CASO-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        case.files["escritura_path"] = escritura_path
        case.files["modelo_path"] = modelo_path
        case.meta["hashes"] = {
            "escritura": _hash_file(escritura_path),
            "modelo": _hash_file(modelo_path),
        }
        set_case(case)
        st.success("Archivos registrados. Continúa con Extracción y estado.")
