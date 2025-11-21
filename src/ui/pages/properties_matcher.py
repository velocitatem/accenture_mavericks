from __future__ import annotations

import streamlit as st

from ..components.normalizers import normalize_cadastral_ref
from ..state import get_case, set_case


def render():
    case = get_case()
    st.title("Coincidencia de inmuebles")
    st.caption("Agrupa referencias catastrales y normaliza campos para informes consistentes.")
    if not case.comparison:
        with st.container(border=True):
            st.subheader("No hay coincidencias disponibles")
            st.write("Ejecuta la comparación para generar la lista de inmuebles a revisar.")
            st.button(
                "Ir a Extracción y estado",
                on_click=lambda: st.session_state.update({"nav_page": "Extracción y estado"}),
                type="secondary",
                help="Accede a la etapa previa para obtener coincidencias",
            )
        return

    if not isinstance(case.comparison, list):
        st.json(case.comparison)
        return

    for item in case.comparison:
        with st.expander(f"Inmueble {item.get('property_id', 'desconocido')}"):
            st.write(item)
            ref = item.get("ref_catastral")
            if st.button("Normalizar referencia catastral", key=f"norm_{ref}"):
                normalized = normalize_cadastral_ref(ref)
                item["ref_catastral_normalized"] = normalized
                set_case(case)
                st.success(f"Referencia normalizada a {normalized}")


