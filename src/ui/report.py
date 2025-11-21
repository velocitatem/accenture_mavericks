from __future__ import annotations

import io
import json
from typing import Any, Dict

from .state import CaseState


def build_report_html(case: CaseState) -> str:
    edits_rows = "".join(
        f"<tr><td>{e.field_path}</td><td>{e.old}</td><td>{e.new}</td><td>{e.reason or ''}</td><td>{e.ts}</td></tr>"
        for e in case.edits
    )
    decision = case.decision.status if case.decision else "pending"
    notes = case.decision.notes if case.decision else ""
    html = f"""
    <html>
    <head><style>table, td, th {{ border:1px solid #ccc; border-collapse: collapse; padding:6px; }}</style></head>
    <body>
    <h1>Case {case.id or 'N/A'}</h1>
    <h2>Decision: {decision}</h2>
    <p>{notes}</p>
    <h3>Edits</h3>
    <table><tr><th>Field</th><th>Old</th><th>New</th><th>Reason</th><th>Timestamp</th></tr>{edits_rows}</table>
    <h3>Comparison</h3>
    <pre>{json.dumps(case.comparison, indent=2, ensure_ascii=False)}</pre>
    </body></html>
    """
    return html


def render_pdf_bytes(html: str) -> bytes:
    try:
        from weasyprint import HTML  # type: ignore

        return HTML(string=html).write_pdf()
    except Exception:
        # Fallback: return HTML bytes to keep download functional
        return html.encode("utf-8")


def build_report(case: CaseState) -> bytes:
    html = build_report_html(case)
    return render_pdf_bytes(html)


def export_case_json(case: CaseState) -> bytes:
    payload: Dict[str, Any] = {
        "files": case.files,
        "ocr": case.ocr,
        "extracted": case.extracted,
        "validation": case.validation,
        "comparison": case.comparison,
        "edits": [e.__dict__ for e in case.edits],
        "decision": case.decision.__dict__ if case.decision else None,
        "meta": case.meta,
    }
    return json.dumps(payload, ensure_ascii=False, default=str, indent=2).encode("utf-8")


__all__ = ["build_report_html", "render_pdf_bytes", "build_report", "export_case_json"]
