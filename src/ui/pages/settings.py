from __future__ import annotations

import streamlit as st

from pipeline import cache
from ..state import get_case


def render():
    case = get_case()
    st.header("Case overview")

    ready_for_extraction = bool(case.files.get("escritura_path") and case.files.get("modelo_path"))
    extraction_complete = bool(case.extracted.get("escritura") and case.extracted.get("modelo"))
    comparison_ready = case.comparison is not None

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Case ID", case.id or "—")
    with col2:
        st.metric("Uploads", "Ready" if ready_for_extraction else "Pending")
    with col3:
        st.metric("Extraction", "Complete" if extraction_complete else "Pending")

    col4, _ = st.columns(2)
    with col4:
        st.metric("Comparison", "Ready" if comparison_ready else "Pending")

    st.subheader("Cache")
    st.write(f"Cache enabled: {cache.enabled}")
    if st.button("Purge cache", type="secondary"):
        st.session_state["confirm_purge_cache"] = True
    if st.session_state.get("confirm_purge_cache"):
        st.warning("This will remove all cached data for the session.")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Yes, purge cache", key="purge_cache_confirm", type="primary"):
                cache.clear_all()
                st.session_state.pop("confirm_purge_cache", None)
                st.success("Cache cleared")
        with cancel_col:
            if st.button("Cancel", key="purge_cache_cancel"):
                st.session_state.pop("confirm_purge_cache", None)

    st.subheader("Case metadata")
    st.caption("Includes document hashes, timings, and other technical details.")
    st.json(case.meta)

    st.subheader("Case management")
    if st.button("Reset case", type="secondary"):
        st.session_state["confirm_reset_case"] = True
    if st.session_state.get("confirm_reset_case"):
        st.warning("Resetting will remove all uploaded files and progress for this case.")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button("Yes, reset case", key="reset_case_confirm", type="primary"):
                st.session_state.pop("case", None)
                st.session_state.pop("confirm_reset_case", None)
                st.success("Case reset. Reload page.")
        with cancel_col:
            if st.button("Cancel", key="reset_case_cancel"):
                st.session_state.pop("confirm_reset_case", None)


