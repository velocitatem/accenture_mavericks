from ui import adapters


def dummy_ocr(path: str):
    return "text-from-" + path


def dummy_llm(text: str):
    return {"llm": text}


def dummy_validate(payload):
    return payload


def test_run_escritura_pipeline_with_stubs():
    res = adapters.run_escritura_pipeline(
        "doc.pdf", ocr_fn=dummy_ocr, llm_fn=dummy_llm, validate_fn=dummy_validate
    )
    assert res["ocr_text"] == "text-from-doc.pdf"
    assert res["extracted"]["llm"] == "text-from-doc.pdf"
    assert res["validation"]["llm"] == "text-from-doc.pdf"
    assert "timings" in res["meta"]


def test_fast_validate_passthrough():
    obj = {"sample": True}
    validated = adapters.fast_validate("escritura", obj)
    assert validated is not None
