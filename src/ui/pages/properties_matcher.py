from __future__ import annotations

import streamlit as st

from ..components.normalizers import normalize_cadastral_ref
from ..state import get_case, set_case


def render():
    case = get_case()
    st.header("Properties Matcher")
    if not case.comparison:
        st.info("Run comparison first.")
        return

    if not isinstance(case.comparison, list):
        st.json(case.comparison)
        return

    for item in case.comparison:
        with st.expander(f"Property {item.get('property_id', 'unknown')}"):
            st.write(item)
            ref = item.get("ref_catastral")
            if st.button("Normalize cadastral", key=f"norm_{ref}"):
                normalized = normalize_cadastral_ref(ref)
                item["ref_catastral_normalized"] = normalized
                set_case(case)
                st.success(f"Normalized to {normalized}")


