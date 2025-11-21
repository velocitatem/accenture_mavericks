from __future__ import annotations

from typing import Any, Callable, List, Dict

import streamlit as st


def render_discrepancies(
    issues: List[Dict[str, Any]],
    on_edit: Callable[[str, Any], None] | None = None,
    editable: bool = True,
) -> None:
    if not issues:
        st.success("Sin discrepancias detectadas")
        return

    st.markdown("### Panel de discrepancias")
    editable_rows = []
    for issue in issues:
        editable_rows.append(
            {
                "Categoría": issue.get("code") or issue.get("category", ""),
                "Campo": issue.get("field", ""),
                "Valor en escritura": issue.get("escritura_value"),
                "Valor en Modelo 600": issue.get("tax_form_value"),
                "Mensaje": issue.get("message", ""),
            }
        )

    edited = st.data_editor(editable_rows, num_rows="dynamic", disabled=not editable)

    if on_edit and editable:
        for before, after in zip(editable_rows, edited):
            if before != after:
                field = after.get("Campo")
                new_val = after.get("Valor en escritura") or after.get("Valor en Modelo 600")
                on_edit(field, new_val)


__all__ = ["render_discrepancies"]
