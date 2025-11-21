from __future__ import annotations

from typing import Any, Callable, List, Dict

import streamlit as st


def render_discrepancies(
    issues: List[Dict[str, Any]],
    on_edit: Callable[[str, Any], None] | None = None,
) -> None:
    if not issues:
        st.success("No issues detected")
        return

    st.markdown("### Discrepancy Board")
    editable_rows = []
    for issue in issues:
        editable_rows.append(
            {
                "Category": issue.get("code") or issue.get("category", ""),
                "Field path": issue.get("field", ""),
                "Escritura value": issue.get("escritura_value"),
                "Modelo value": issue.get("tax_form_value"),
                "Message": issue.get("message", ""),
            }
        )

    edited = st.data_editor(editable_rows, num_rows="dynamic")

    if on_edit:
        for before, after in zip(editable_rows, edited):
            if before != after:
                field = after.get("Field path")
                new_val = after.get("Escritura value") or after.get("Modelo value")
                on_edit(field, new_val)


__all__ = ["render_discrepancies"]
