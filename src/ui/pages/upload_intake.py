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
    st.header("Upload & Intake")

    use_samples = st.toggle("Use sample docs", value=False)

    if use_samples:
        escritura_path = SAMPLE_ESCRITURA
        modelo_path = SAMPLE_MODELO
    else:
        escritura_file = st.file_uploader("Upload Escritura PDF", type="pdf")
        modelo_file = st.file_uploader("Upload Modelo 600 PDF", type="pdf")
        escritura_path = _copy_uploaded(escritura_file) if escritura_file else None
        modelo_path = _copy_uploaded(modelo_file) if modelo_file else None

    if escritura_path:
        st.success(f"Escritura ready ({format_size(Path(escritura_path).stat().st_size)})")
    if modelo_path:
        st.success(f"Modelo 600 ready ({format_size(Path(modelo_path).stat().st_size)})")

    ready = escritura_path and modelo_path

    if st.button("Run pipelines", disabled=not ready):
        case.id = "CASE-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        case.files["escritura_path"] = escritura_path
        case.files["modelo_path"] = modelo_path
        case.meta["hashes"] = {
            "escritura": _hash_file(escritura_path),
            "modelo": _hash_file(modelo_path),
        }
        set_case(case)
        st.success("Files registered. Proceed to Extraction & Status page.")
