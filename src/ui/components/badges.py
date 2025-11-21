from __future__ import annotations

import streamlit as st


def confidence_badge(value: float) -> None:
    if value is None:
        st.badge("Sin dato", color="gray")
        return
    color = "green" if value >= 0.8 else "orange" if value >= 0.5 else "red"
    st.badge(f"Confianza {value:.2f}", color=color)


def severity_badge(sev: str) -> None:
    color = {
        "error": "red",
        "warning": "orange",
        "info": "blue",
    }.get((sev or "").lower(), "gray")
    st.badge(sev or "", color=color)


__all__ = ["confidence_badge", "severity_badge"]
