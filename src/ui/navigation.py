from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import streamlit as st

from .state import CaseState


@dataclass
class Stage:
    key: str
    label: str
    description: str
    is_complete: Callable[[CaseState], bool]


STAGES: list[Stage] = [
    Stage(
        key="upload",
        label="Carga de documentos",
        description="Sube la escritura y el Modelo 600 antes de continuar.",
        is_complete=lambda case: bool(
            case.files.get("escritura_path") and case.files.get("modelo_path")
        ),
    ),
    Stage(
        key="extraction",
        label="Extracción",
        description="Ejecuta la extracción y validación de datos.",
        is_complete=lambda case: bool(
            case.extracted.get("escritura") and case.extracted.get("modelo") and case.comparison
        ),
    ),
    Stage(
        key="review",
        label="Revisión",
        description="Revisa discrepancias y marca el estado.",
        is_complete=lambda case: bool(case.meta.get("revision_lista")),
    ),
    Stage(
        key="decision",
        label="Decisión y reporte",
        description="Registra la decisión y genera el reporte final.",
        is_complete=lambda case: case.decision is not None,
    ),
]


def _stages_before(target_key: str) -> Iterable[Stage]:
    for stage in STAGES:
        if stage.key == target_key:
            break
        yield stage


def require_stage(stage_key: str, case: CaseState) -> None:
    """Detiene la página si las etapas previas no están completas."""
    blocking = [s for s in _stages_before(stage_key) if not s.is_complete(case)]
    if blocking:
        first = blocking[0]
        st.info(
            f"Completa **{first.label}** primero. {first.description}"
        )
        st.stop()


def render_sidebar_progress(active_stage: str | None, case: CaseState) -> None:
    st.markdown("### Progreso del caso")
    for stage in STAGES:
        completo = stage.is_complete(case)
        icon = "✅" if completo else "⏳"
        if stage.key == active_stage:
            icon = f"👉 {icon}"
        st.write(f"{icon} {stage.label}")
    st.divider()

