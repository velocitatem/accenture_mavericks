from ui.components.normalizers import normalize_cadastral_ref, normalize_address, validate_nif


def test_normalize_cadastral():
    assert normalize_cadastral_ref(" 12 34-AB ") == "1234AB"


def test_normalize_address():
    assert normalize_address(" Calle  Mayor   5 ") == "CALLE MAYOR 5"


def test_validate_nif():
    assert validate_nif("12345678Z") is True
    assert validate_nif("1234") is False
