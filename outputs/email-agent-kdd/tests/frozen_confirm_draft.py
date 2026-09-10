"""Tests congelados del contrato confirm_email_draft.

Oracle independiente: no importa el target ni src.email. Verifica la
estructura del contrato, la frase exacta de confirmacion, el estado
confirmed del ejemplo frozen, la no-mutacion del draft de entrada y el
confirmation_hash estable (recomputando el sha256 documentado).
"""

import hashlib
import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "confirm-draft.md"
)

REQUIRED_PHRASE = "CONFIRMAR ENVIO"
HASH_RULE = 'sha256(draft["id"] + "|" + confirmation)'


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    return text.split("---\n", 2)[1]


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_result():
    return json.loads(_fenced_block(_contract_text(), "frozen-example"))


def _frozen_inputs():
    return json.loads(_fenced_block(_contract_text(), "frozen-inputs"))


def _hash_rule(draft_id, confirmation):
    """Regla del confirmation_hash del contrato, reimplementada por el oracle."""
    return hashlib.sha256(
        (draft_id + "|" + confirmation).encode("utf-8")
    ).hexdigest()


def test_contract_frontmatter_budgets_deps_forbids():
    frontmatter = _frontmatter(_contract_text())
    assert "task: confirm_email_draft" in frontmatter
    assert (
        'signature: "def confirm_email_draft(draft: dict, confirmation: str) '
        '-> dict"' in frontmatter
    )
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [hashlib]" in frontmatter
    for forbidden in ("eval", "exec", "subprocess", "network_access", "smtplib"):
        assert forbidden in frontmatter, "forbids sin " + forbidden


def test_contract_has_seven_sections_and_stop_phrase():
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


def test_frozen_result_keeps_fields_and_adds_status_and_hash():
    result = _frozen_result()
    draft = _frozen_inputs()[0]
    for key, value in draft.items():
        assert key in result, "clave del borrador perdida: " + key
        if key != "status":
            assert result[key] == value, "valor alterado para " + key
    assert list(result.keys()) == list(draft.keys()) + [
        "confirmation_hash"
    ], "claves del resultado inesperadas"
    json.dumps(result)


def test_frozen_result_status_is_confirmed():
    assert _frozen_result()["status"] == "confirmed"
    assert _frozen_inputs()[0]["status"] == "pending"


def test_confirmation_phrase_is_exact():
    text = _contract_text()
    assert REQUIRED_PHRASE in text, "frase exacta no documentada"
    assert '"CONFIRMAR ENVIO"' in text, "frase no declarada como cadena exacta"
    invalid_block = _fenced_block(text, "frozen-invalid-inputs")
    for variant in (
        "confirmar envio",
        "CONFIRMAR ENVIO ",
        "  CONFIRMAR ENVIO",
        "CONFIRMAR ENVÍO",
    ):
        assert variant in invalid_block, "variante rechazada no documentada: " + variant


def test_frozen_hash_matches_deterministic_rule():
    inputs = _frozen_inputs()
    expected_hash = _hash_rule(inputs[0]["id"], inputs[1])
    result = _frozen_result()
    assert expected_hash == result["confirmation_hash"]
    assert re.fullmatch(r"[0-9a-f]{64}", result["confirmation_hash"])
    assert expected_hash == _hash_rule(inputs[0]["id"], REQUIRED_PHRASE), (
        "hash no estable para la misma entrada"
    )


def test_hash_rule_is_documented_and_deterministic():
    text = _contract_text()
    assert HASH_RULE in text, "regla del hash no documentada textualmente"
    assert "sin reloj, sin aleatoriedad" in text
    assert "result is not draft" in text, "sin ejemplo de copia no mutada"
    assert "no muta la entrada" in text


def test_invalid_inputs_rejected_with_valueerror():
    text = _contract_text()
    invalid = eval(  # noqa: S307 - contenido propio del contrato congelado
        _fenced_block(text, "frozen-invalid-inputs"),
        {"null": None, "true": True, "false": False},
    )
    assert set(invalid) == {"draft", "confirmation"}
    assert any(case is None for case in invalid["draft"])
    assert any(
        case.get("status") == "confirmed"
        for case in invalid["draft"]
        if isinstance(case, dict)
    ), "sin caso de borrador ya confirmado"
    assert len(invalid["confirmation"]) >= 5, "variantes de frase insuficientes"
    assert "ValueError" in text, "el contrato no declara rechazo con ValueError"