from __future__ import annotations

import streamlit as st


def confidence_badge(value: float) -> str:
    if value is None:
        return ""
    color = "green" if value >= 0.8 else "orange" if value >= 0.5 else "red"
    return f"<span style='background:{color};color:white;padding:2px 6px;border-radius:4px'>{value:.2f}</span>"


def severity_badge(sev: str) -> str:
    color = {
        "error": "red",
        "warning": "orange",
        "info": "blue",
    }.get((sev or "").lower(), "gray")
    return f"<span style='background:{color};color:white;padding:2px 6px;border-radius:4px'>{sev}</span>"


__all__ = ["confidence_badge", "severity_badge"]
