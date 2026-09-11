"""Pruebas offline del contrato de estados antivirus."""

from src.email.antivirus import scan_bytes


def test_scanner_falso_devuelve_estados_publicos():
    assert scan_bytes(b"x", lambda _: "clean") == "clean"
    assert scan_bytes(b"x", lambda _: "infected") == "infected"


def test_scanner_falso_falla_cerrado_en_estado_o_excepcion():
    assert scan_bytes(b"x", lambda _: "unknown") == "error"
    assert scan_bytes(b"x", lambda _: (_ for _ in ()).throw(RuntimeError())) == "error"


def test_scanner_rechaza_tipo_y_tamano_invalidos():
    assert scan_bytes("x") == "error"
    assert scan_bytes(b"xx", lambda _: "clean", max_bytes=1) == "error"
