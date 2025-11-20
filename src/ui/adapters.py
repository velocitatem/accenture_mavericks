"""UI-level adapters to existing backend functions.

These helpers inspect available signatures and provide a stable call surface for
Streamlit pages. They also log detected integration details to help operators
understand how the underlying pipelines are wired.
"""
from __future__ import annotations

import time
from typing import Any, Dict

try:  # Streamlit is optional in tests
    import streamlit as st
except Exception:  # pragma: no cover - fallback for non-Streamlit contexts
    st = None  # type: ignore

from pipeline import build_llm_function, build_ocr_function, cached_validate, cache
from core.comparison import compare_escritura_with_tax_forms
from core.validation import Escritura, Modelo600, validate_data


def _log(msg: str) -> None:
    if st:
        st.sidebar.write(msg)
    else:
        print(msg)


def _detect_signature(name: str, fn: Any) -> None:
    sig = getattr(fn, "__name__", str(fn))
    _log(f"Detected {name}: {sig}")


def run_escritura_pipeline(pdf_path: str, *, ocr_fn=None, llm_fn=None, validate_fn=None) -> Dict[str, Any]:
    """Run the escritura pipeline step by step, exposing intermediate artifacts."""
    ocr_callable = ocr_fn or build_ocr_function(autoliquidacion=False)
    llm_callable = llm_fn or build_llm_function
    validate_callable = validate_fn or cached_validate

    _detect_signature("ocr", ocr_callable)

    pre_cached = cache.get("ocr_escritura", pdf_path)
    start = time.time()
    ocr_text = ocr_callable(pdf_path)
    ocr_time = time.time() - start

    model = Escritura if llm_fn is None else None
    llm_step = llm_callable(model) if llm_fn is None else llm_callable
    _detect_signature("llm", llm_step)

    prefix = f"llm_{model.__name__}" if model else f"llm_{getattr(llm_step, '__name__', 'llm')}"
    pre_llm_cache = cache.get(prefix, ocr_text)
    start = time.time()
    extracted = llm_step(ocr_text)
    llm_time = time.time() - start

    _detect_signature("validation", validate_callable)
    start = time.time()
    validated = validate_callable(extracted)
    validation_time = time.time() - start

    return {
        "ocr_text": ocr_text,
        "extracted": getattr(extracted, "model_dump", lambda: extracted)(),
        "validation": getattr(validated, "model_dump", lambda: validated)(),
        "meta": {
            "ocr_cached": pre_cached is not None,
            "llm_cached": pre_llm_cache is not None,
            "timings": {
                "ocr": ocr_time,
                "llm": llm_time,
                "validation": validation_time,
            },
        },
    }


def run_modelo_pipeline(pdf_path: str, *, ocr_fn=None, llm_fn=None, validate_fn=None) -> Dict[str, Any]:
    ocr_callable = ocr_fn or build_ocr_function(autoliquidacion=True)
    llm_callable = llm_fn or build_llm_function
    validate_callable = validate_fn or cached_validate

    pre_cached = cache.get("ocr_autoliq", pdf_path)
    start = time.time()
    ocr_text = ocr_callable(pdf_path)
    ocr_time = time.time() - start

    model = Modelo600 if llm_fn is None else None
    llm_step = llm_callable(model) if llm_fn is None else llm_callable

    prefix = f"llm_{model.__name__}" if model else f"llm_{getattr(llm_step, '__name__', 'llm')}"
    pre_llm_cache = cache.get(prefix, ocr_text)
    start = time.time()
    extracted = llm_step(ocr_text)
    llm_time = time.time() - start

    start = time.time()
    validated = validate_callable(extracted)
    validation_time = time.time() - start

    return {
        "ocr_text": ocr_text,
        "extracted": getattr(extracted, "model_dump", lambda: extracted)(),
        "validation": getattr(validated, "model_dump", lambda: validated)(),
        "meta": {
            "ocr_cached": pre_cached is not None,
            "llm_cached": pre_llm_cache is not None,
            "timings": {
                "ocr": ocr_time,
                "llm": llm_time,
                "validation": validation_time,
            },
        },
    }


def fast_validate(doc_type: str, obj_dict: Dict[str, Any]) -> Any:
    """Validate without OCR/LLM. Falls back to validate_data."""
    _detect_signature("fast_validate", validate_data)
    try:
        return validate_data(obj_dict)
    except Exception:
        return obj_dict


def run_comparison(escritura_obj: Dict[str, Any], modelo_obj: Dict[str, Any]) -> Any:
    _detect_signature("comparison", compare_escritura_with_tax_forms)
    payload = {"escrituras": [escritura_obj], "tax_forms": [modelo_obj]}
    return compare_escritura_with_tax_forms(payload)


__all__ = [
    "run_escritura_pipeline",
    "run_modelo_pipeline",
    "run_comparison",
    "fast_validate",
]
