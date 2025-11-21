from __future__ import annotations

import streamlit as st

from pipeline import cache
from ..state import get_case


def render():
    case = get_case()
    st.title("Ajustes")

    st.subheader("Caché")
    st.write(f"Caché activa: {cache.enabled}")
    if st.button("Vaciar caché"):
        cache.clear_all()
        st.success("Caché borrada")

    st.subheader("Metadatos del caso")
    st.json(case.meta)

    if st.button("Reiniciar caso"):
        st.session_state.pop("case", None)
        st.success("Caso reiniciado. Recarga la página.")


