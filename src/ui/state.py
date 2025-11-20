from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import streamlit as st


@dataclass
class EditEntry:
    field_path: str
    old: Any
    new: Any
    reason: Optional[str]
    ts: float


@dataclass
class Decision:
    status: str  # "approve" | "request_info" | "reject"
    notes: str


@dataclass
class CaseState:
    id: Optional[str] = None
    files: dict = field(default_factory=lambda: {"escritura_path": None, "modelo_path": None})
    ocr: dict = field(default_factory=lambda: {"escritura": None, "modelo": None})
    extracted: dict = field(default_factory=lambda: {"escritura": None, "modelo": None})
    validation: dict = field(default_factory=lambda: {"escritura": None, "modelo": None})
    comparison: Optional[dict] = None
    edits: list[EditEntry] = field(default_factory=list)
    decision: Optional[Decision] = None
    meta: dict = field(default_factory=dict)  # timings, cache hits, etc.


# --- Session helpers ---

def _serialize_case(case: CaseState) -> dict:
    data = asdict(case)
    return data


def ensure_session() -> None:
    if "case" not in st.session_state:
        st.session_state["case"] = _serialize_case(CaseState())


def get_case() -> CaseState:
    ensure_session()
    data = st.session_state["case"]
    edits = [EditEntry(**e) for e in data.get("edits", [])]
    decision = data.get("decision")
    decision_obj = Decision(**decision) if decision else None
    return CaseState(
        id=data.get("id"),
        files=data.get("files", {}),
        ocr=data.get("ocr", {}),
        extracted=data.get("extracted", {}),
        validation=data.get("validation", {}),
        comparison=data.get("comparison"),
        edits=edits,
        decision=decision_obj,
        meta=data.get("meta", {}),
    )


def set_case(case: CaseState) -> None:
    st.session_state["case"] = _serialize_case(case)


def log_edit(case: CaseState, field_path: str, old: Any, new: Any, reason: Optional[str] = None) -> CaseState:
    case.edits.append(EditEntry(field_path=field_path, old=old, new=new, reason=reason, ts=time.time()))
    return case


__all__ = [
    "CaseState",
    "Decision",
    "EditEntry",
    "ensure_session",
    "get_case",
    "set_case",
    "log_edit",
]
