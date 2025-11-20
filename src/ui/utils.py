from __future__ import annotations

import io
import json
import streamlit as st


def download_json_button(label: str, payload, file_name: str) -> None:
    buffer = io.BytesIO(json.dumps(payload, ensure_ascii=False, default=str, indent=2).encode("utf-8"))
    st.download_button(label, buffer, file_name=file_name, mime="application/json")


def format_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024.0:
            return f"{num:3.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}TB"


__all__ = ["download_json_button", "format_size"]
