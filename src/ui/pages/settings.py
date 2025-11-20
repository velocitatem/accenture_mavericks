from __future__ import annotations

import streamlit as st

from pipeline import cache
from ..state import get_case


def render():
    case = get_case()
    st.header("Settings")

    st.subheader("Cache")
    st.write(f"Cache enabled: {cache.enabled}")
    if st.button("Purge cache"):
        cache.clear_all()
        st.success("Cache cleared")

    st.subheader("Case metadata")
    st.json(case.meta)

    if st.button("Reset case"):
        st.session_state.pop("case", None)
        st.success("Case reset. Reload page.")


