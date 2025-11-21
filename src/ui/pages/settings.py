from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from pipeline import cache
from ..navigation import STAGES
from ..state import get_case


def _hash_file(path: str | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def render():
    case = get_case()
    st.header("Información del caso")

    st.markdown("### Resumen")
    cols = st.columns(4)
    extraction_done = next((s.is_complete(case) for s in STAGES if s.key == "extraction"), False)
    cols[0].metric(
        "Documentos",
        "Cargados" if (case.files.get("escritura_path") and case.files.get("modelo_path")) else "Pendiente",
    )
    cols[1].metric("Extracción", "Completa" if extraction_done else "Pendiente")
    cols[2].metric("Revisión", "Lista" if case.meta.get("revision_lista") else "Pendiente")
    cols[3].metric("Decisión", case.decision.status if case.decision else "Sin decidir")

    st.subheader("Metadatos técnicos")
    hashes = {
        "escritura": _hash_file(case.files.get("escritura_path")),
        "modelo": _hash_file(case.files.get("modelo_path")),
    }
    case.meta["hashes"] = {k: v for k, v in hashes.items() if v}
    st.json({"archivos": case.files, "hashes": case.meta.get("hashes", {}), "meta": case.meta})

    st.subheader("Caché")
    st.write(f"Cache habilitada: {cache.enabled}")
    confirm_cache = st.checkbox("Confirmar limpieza de caché")
    if st.button("Purgar caché", disabled=not confirm_cache):
        cache.clear_all()
        st.success("Caché purgada")

    st.subheader("Reiniciar caso")
    confirm_reset = st.checkbox("Confirmar reinicio del caso")
    if st.button("Restablecer caso", disabled=not confirm_reset):
        st.session_state.pop("case", None)
        st.success("Caso reiniciado. Recarga la página para empezar de nuevo.")


