from __future__ import annotations

from typing import Any, Callable, List, Dict

import streamlit as st


def render_discrepancies(
    issues: List[Dict[str, Any]],
    on_edit: Callable[[str, Any], None] | None = None,
) -> None:
    if not issues:
        with st.container(border=True):
            st.subheader("Sin discrepancias por ahora")
            st.write(
                "No se encontraron diferencias entre los documentos. Puedes refrescar los resultados o volver a ejecutar la extracción si necesitas validar cambios."
            )
            st.button(
                "Refrescar vista",
                type="secondary",
                on_click=st.experimental_rerun,
                help="Acción rápida para actualizar la tabla",
            )
        return

    st.subheader("Tablero de discrepancias")
    editable_rows = []
    for issue in issues:
        editable_rows.append(
            {
                "Categoría": issue.get("code") or issue.get("category", ""),
                "Ruta de campo": issue.get("field", ""),
                "Valor en escritura": issue.get("escritura_value"),
                "Valor en Modelo 600": issue.get("tax_form_value"),
                "Mensaje": issue.get("message", ""),
            }
        )

    edited = st.data_editor(editable_rows, num_rows="dynamic")

    if on_edit:
        for before, after in zip(editable_rows, edited):
            if before != after:
                field = after.get("Ruta de campo")
                new_val = after.get("Valor en escritura") or after.get("Valor en Modelo 600")
                on_edit(field, new_val)


__all__ = ["render_discrepancies"]
