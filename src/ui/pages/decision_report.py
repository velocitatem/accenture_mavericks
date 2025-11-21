from __future__ import annotations

import streamlit as st

from ..report import build_report, build_report_html, export_case_json
from ..state import CaseState, Decision, get_case, set_case


def render():
    case = get_case()
    st.header("Decision & Report")

    decision = case.decision.status if case.decision else "approve"
    choice = st.radio("Decision", ["approve", "request_info", "reject"], index=["approve", "request_info", "reject"].index(decision))
    notes = st.text_area("Notes", value=case.decision.notes if case.decision else "")

    if st.button("Save decision"):
        case.decision = Decision(status=choice, notes=notes)
        set_case(case)
        st.success("Decision saved")

    st.markdown("### Export")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Export case JSON", export_case_json(case), "case.json")
    with col2:
        st.download_button("Generate PDF report", build_report(case), "case_report.pdf")

    st.markdown("### Preview")
    st.components.v1.html(build_report_html(case), height=300, scrolling=True)


