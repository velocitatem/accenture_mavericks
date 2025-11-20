from ui.report import build_report_html
from ui.state import CaseState, EditEntry, Decision


def test_report_contains_edits_and_decision():
    case = CaseState(
        id="CASE-1",
        comparison={"summary": "ok"},
        edits=[EditEntry(field_path="buyers[0].nif", old="123", new="12345678Z", reason="fix", ts=1.0)],
        decision=Decision(status="request_info", notes="Need docs"),
    )
    html = build_report_html(case)
    assert "CASE-1" in html
    assert "12345678Z" in html
    assert "request_info" in html
    assert "Need docs" in html
