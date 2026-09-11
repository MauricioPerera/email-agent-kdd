# -*- coding: utf-8 -*-
"""Oracle congelado e independiente para extract_delivered_to.

NO importa el target para calcular esperados: el modelo de referencia se
reimplementa aqui con stdlib (parser de email + getaddresses + dedup exacta +
orden lexicografico). Los casos contra el target se activan cuando existe.
"""

import email
import email.utils
import re
from pathlib import Path

import pytest

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "delivery-recipient.md"
)
TARGET = Path(__file__).resolve().parents[3] / "src" / "email" / "delivery.py"

ENVELOPE_HEADERS = ("Delivered-To", "X-Original-To", "Envelope-To")


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Modelo de referencia (oraculo independiente).
# ---------------------------------------------------------------------------


def _model(message):
    collected = []
    for name in ENVELOPE_HEADERS:
        for value in message.get_all(name, []):
            for _display, addr_spec in email.utils.getaddresses([str(value)]):
                addr = addr_spec.strip()
                if addr and "@" in addr:
                    collected.append(addr)
    return sorted(set(collected))


def _message(raw_headers):
    text = "\r\n".join(raw_headers) + "\r\n\r\n\ncuerpo\n"
    return email.message_from_string(text)


def _target():
    if not TARGET.exists():
        pytest.skip("target no implementado todavia")
    namespace = {}
    exec(  # noqa: S307 - carga puntual del target para el caso congelado
        TARGET.read_text(encoding="utf-8"), namespace
    )
    if "extract_delivered_to" not in namespace:
        pytest.skip("target sin extract_delivered_to")
    return namespace["extract_delivered_to"]


# ---------------------------------------------------------------------------
# Estructura del contrato.
# ---------------------------------------------------------------------------


def test_contract_frontmatter_and_budgets():
    frontmatter = _contract_text().split("---\n", 2)[1]
    assert "task: extract_delivered_to" in frontmatter
    assert 'signature: "def extract_delivered_to(message) -> list"' in frontmatter
    assert "target: src/email/delivery.py" in frontmatter
    assert "tests: tests/frozen_delivery_recipient.py" in frontmatter
    assert "cyclomatic_max: 8" in frontmatter
    assert "nesting_max: 3" in frontmatter
    assert "lines_max: 50" in frontmatter
    assert "params_max: 1" in frontmatter
    assert "deps_allowed: [email]" in frontmatter
    assert "forbids:" in frontmatter


def test_contract_has_sections_and_stop_phrase():
    text = _contract_text()
    for section in (
        "## Intent",
        "## Interface",
        "## Invariants",
        "## Examples",
        "## Do / Don't",
        "## Tests",
        "## Constraints",
    ):
        assert section in text, "seccion ausente: " + section
    assert "PARAR y reportar si" in text


def test_contract_declares_verbatim_no_canonicalization():
    text = _contract_text()
    for header in ENVELOPE_HEADERS:
        assert header in text, "header de envelope ausente: " + header
    assert "verbatim" in text, "extraccion verbatim no declarada"
    for banned in ("minusculas", "+tag", "puntos del local part"):
        assert banned in text, "prohibicion de canonicalizacion ausente: " + banned
    assert "To`, `Cc" not in text and "`To`/`Cc`" in text or "`To`, `Cc`" in text, (
        "el contrato debe excluir To/Cc/Bcc/Return-Path como fuente"
    )


def test_contract_frozen_inputs_exist():
    assert "```frozen-inputs\n" in _contract_text(), (
        "bloque frozen-inputs ausente"
    )


# ---------------------------------------------------------------------------
# Casos congelados del modelo y contra el target.
# ---------------------------------------------------------------------------


FROZEN_CASES = [
    (
        "dos_variantes_puntos_no_colapsan",
        ["Delivered-To: user@ardf.dev", "X-Original-To: u.s.e.r+tag@ardf.dev"],
        ["u.s.e.r+tag@ardf.dev", "user@ardf.dev"],
    ),
    (
        "mayusculas_se_conservan_verbatim",
        ["Delivered-To: USER@ARDF.dev", "Envelope-To: user@ardf.dev"],
        ["USER@ARDF.dev", "user@ardf.dev"],
    ),
    (
        "display_name_descartado",
        ["Delivered-To: Mail Delivery System <user@ardf.dev>"],
        ["user@ardf.dev"],
    ),
    (
        "lista_en_un_solo_header",
        ["Envelope-To: a@x.dev, b@x.dev"],
        ["a@x.dev", "b@x.dev"],
    ),
    (
        "sin_envelope_headers_devuelve_vacia",
        ["To: user@ardf.dev", "Cc: other@ardf.dev"],
        [],
    ),
    (
        "malformados_se_saltan",
        ["Delivered-To: <>", "X-Original-To: basura-sin-arroba"],
        [],
    ),
    (
        "nombre_header_minusculas",
        ["delivered-to: user@ardf.dev"],
        ["user@ardf.dev"],
    ),
    (
        "duplicado_exacto_dedup",
        ["Delivered-To: user@ardf.dev", "Envelope-To: user@ardf.dev"],
        ["user@ardf.dev"],
    ),
]


@pytest.mark.parametrize("name,headers,expected", FROZEN_CASES, ids=[c[0] for c in FROZEN_CASES])
def test_model_matches_expected(name, headers, expected):
    assert _model(_message(headers)) == expected


@pytest.mark.parametrize("name,headers,expected", FROZEN_CASES, ids=[c[0] for c in FROZEN_CASES])
def test_target_matches_oracle(name, headers, expected):
    extract = _target()
    message = _message(headers)
    result = extract(message)
    assert result == expected, "caso congelado: " + name
    # La salida es estable: orden lexicografico y sin mutar el mensaje.
    assert result == sorted(set(result))
    assert "Delivered-To" not in (message.get("X-Modificada") or "")


def test_target_does_not_consume_to_cc_or_return_path():
    extract = _target()
    message = _message(
        [
            "To: user@ardf.dev",
            "Cc: cc@ardf.dev",
            "Return-Path: <bounce@ardf.dev>",
            "Reply-To: reply@ardf.dev",
        ]
    )
    assert extract(message) == []


def test_target_rejects_non_message():
    extract = _target()
    with pytest.raises(TypeError):
        extract(None)
    with pytest.raises(TypeError):
        extract("no es un mensaje")


def test_target_stable_across_header_order():
    extract = _target()
    forward = _message(["Delivered-To: a@x.dev", "Envelope-To: b@x.dev"])
    backward = _message(["Envelope-To: b@x.dev", "Delivered-To: a@x.dev"])
    assert extract(forward) == extract(backward) == ["a@x.dev", "b@x.dev"]