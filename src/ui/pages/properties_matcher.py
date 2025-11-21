from __future__ import annotations

import streamlit as st

from ..components.normalizers import normalize_cadastral_ref
from ..navigation import require_stage
from ..state import get_case, set_case


def render():
    case = get_case()
    st.header("Propiedades")

    require_stage("review", case)
    if not case.comparison:
        st.info("Ejecuta la extracción y comparación antes de revisar propiedades.")
        return

    if not isinstance(case.comparison, list):
        st.json(case.comparison)
        return

    for item in case.comparison:
        with st.expander(f"Propiedad {item.get('property_id', 'desconocida')}"):
            st.write(item)
            ref = item.get("ref_catastral")
            if st.button("Normalizar referencia", key=f"norm_{ref}"):
                normalized = normalize_cadastral_ref(ref)
                item["ref_catastral_normalized"] = normalized
                set_case(case)
                st.success(f"Normalizada a {normalized}")


