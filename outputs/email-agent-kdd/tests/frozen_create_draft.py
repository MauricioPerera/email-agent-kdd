"""Tests congelados del contrato create_email_draft.

Oracle independiente: no importa el target ni src.email. Verifica la
estructura del contrato, la regla de normalizacion de destinatarios, el
id determinista (recomputando el sha256 documentado), el estado pending
y los campos obligatorios del borrador.
"""

import hashlib
import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "create-draft.md"
)

REQUIRED_FIELDS = ["id", "account_id", "to", "subject", "body", "status"]
ID_RULE = 'sha256(account_id + "|" + ",".join(to_norm) + "|" + subject + "|" + body)'


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _frontmatter(text):
    return text.split("---\n", 2)[1]


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_draft():
    return json.loads(_fenced_block(_contract_text(), "frozen-example"))


def _frozen_inputs():
    return json.loads(_fenced_block(_contract_text(), "frozen-inputs"))


def _normalize_recipients(raw):
    """Regla de normalizacion del contrato, reimplementada por el oracle.

    strip -> descartar vacios -> minusculas -> dedup conservando orden.
    """
    normalized = []
    for entry in raw:
        trimmed = entry.strip()
        if not trimmed:
            continue
        lowered = trimmed.lower()
        if lowered not in normalized:
            normalized.append(lowered)
    return normalized


def test_contract_frontmatter_budgets_deps_forbids():
    frontmatter = _frontmatter(_contract_text())
    assert "task: create_email_draft" in frontmatter
    assert (
        'signature: "def create_email_draft(account_id: str, to: list, '
        'subject: str, body: str) -> dict"' in frontmatter
    )
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [email" in frontmatter
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


def test_draft_required_fields_and_json_serializable():
    draft = _frozen_draft()
    assert list(draft.keys()) == REQUIRED_FIELDS
    json.dumps(draft)
    for field in REQUIRED_FIELDS:
        assert field in draft, "campo obligatorio ausente: " + field


def test_draft_status_is_pending():
    assert _frozen_draft()["status"] == "pending"


def test_recipients_normalized_dedup_ordered():
    inputs = _frozen_inputs()
    expected = _normalize_recipients(inputs[1])
    assert expected, "entrada frozen sin destinatarios validos"
    assert len(expected) == len(set(expected)), "dedup no aplicado"
    assert all(addr == addr.lower() for addr in expected), "minusculas no aplicada"
    assert _frozen_draft()["to"] == expected


def test_frozen_id_matches_deterministic_rule():
    inputs = _frozen_inputs()
    expected_id = hashlib.sha256(
        (
            inputs[0]
            + "|"
            + ",".join(_normalize_recipients(inputs[1]))
            + "|"
            + inputs[2]
            + "|"
            + inputs[3]
        ).encode("utf-8")
    ).hexdigest()
    assert expected_id == _frozen_draft()["id"]
    assert re.fullmatch(r"[0-9a-f]{64}", _frozen_draft()["id"])


def test_id_rule_is_documented_and_deterministic():
    text = _contract_text()
    assert ID_RULE in text, "regla del id no documentada textualmente"
    assert "mismo `id` que llamarlo" in text, "sin ejemplo de equivalencia por dedup"


def test_invalid_inputs_rejected_with_valueerror():
    text = _contract_text()
    invalid = eval(  # noqa: S307 - contenido propio del contrato congelado
        _fenced_block(text, "frozen-invalid-inputs")
    )
    assert set(invalid) == {"account_id", "to", "subject", "body"}
    for field, cases in invalid.items():
        assert cases, "sin casos invalidos para " + field
    assert "ValueError" in text, "el contrato no declara rechazo con ValueError"