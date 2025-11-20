from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

import streamlit as st


def show_pdf(pdf_path: str, *, height: int = 700, page: Optional[int] = None) -> None:
    """Render a PDF inside Streamlit via iframe."""
    if not pdf_path:
        st.info("No PDF available")
        return

    path = Path(pdf_path)
    if not path.exists():
        st.warning(f"PDF not found: {pdf_path}")
        return

    data = path.read_bytes()
    b64_pdf = base64.b64encode(data).decode("utf-8")
    src = f"data:application/pdf;base64,{b64_pdf}"
    if page:
        src += f"#page={page}"
    st.markdown(
        f'<iframe src="{src}" width="100%" height="{height}" style="border:1px solid #ddd"></iframe>',
        unsafe_allow_html=True,
    )


__all__ = ["show_pdf"]
