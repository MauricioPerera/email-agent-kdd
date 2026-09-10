"""Tests congelados del contrato create_email_account.

Oracle independiente: no importa el target ni src.email. Verifica la
estructura del contrato, las reglas de normalizacion documentadas
(recomputadas), el status disconnected, el caracter opaco de
credential_ref y los casos invalidos con ValueError.
"""

import json
import re
from pathlib import Path

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "create-account.md"
)

RESULT_KEYS = ["account_id", "provider", "email", "credential_ref", "status"]


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


def _normalize_provider(provider):
    """Regla del contrato reimplementada por el oracle."""
    return provider.strip().lower()


def _normalize_email(email):
    return "".join(email.split()).lower()


def test_contract_frontmatter_budgets_deps_forbids():
    frontmatter = _frontmatter(_contract_text())
    assert "task: create_email_account" in frontmatter
    assert (
        'signature: "def create_email_account(account_id: str, provider: str, '
        'email: str, credential_ref: str) -> dict"' in frontmatter
    )
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "tests: tests/frozen_create_account.py" in frontmatter
    for forbidden in (
        "eval",
        "exec",
        "subprocess",
        "network_access",
        "smtplib",
        "socket",
        "urllib",
        "requests",
    ):
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


def test_frozen_result_matches_deterministic_rules():
    result = _frozen_result()
    account_id, provider, email, credential_ref = _frozen_inputs()
    assert list(result.keys()) == RESULT_KEYS, "claves del registro inesperadas"
    assert result["account_id"] == account_id, "account_id alterado"
    assert result["provider"] == _normalize_provider(provider)
    assert result["email"] == _normalize_email(email)
    assert result["credential_ref"] == credential_ref, "credential_ref alterado"
    json.dumps(result)


def test_frozen_result_status_is_disconnected_and_deterministic():
    result = _frozen_result()
    assert result["status"] == "disconnected"
    assert _frozen_inputs()[1] != result["provider"], "provider sin normalizar"
    assert "disconnected" in _contract_text(), "estado inicial no documentado"
    assert "sin reloj, sin aleatoriedad" in _contract_text()


def test_credential_ref_is_opaque_never_a_secret():
    text = _contract_text()
    assert "keyring://gmail/personal" in text, "ejemplo de referencia opaca ausente"
    assert "NUNCA el secreto mismo" in text
    assert "nunca contiene secretos" in text
    don_t = text.split("## Do / Don't", 1)[1].split("## Tests", 1)[0]
    assert "loguear secretos" in don_t, "don't de secretos ausente"
    don_t2 = text.split("## Do / Don't", 1)[1]
    assert "Don't: conectarse a un proveedor" in don_t2, "don't de conexion ausente"


def test_email_normalization_removes_all_whitespace():
    text = _contract_text()
    assert '"ana@example.com"' in text, "ejemplo de normalizacion ausente"
    assert "TODOS los caracteres de espacio en blanco" in text, (
        "regla de espacios no documentada"
    )
    assert _normalize_email("  Ana @ Example.COM ") == "ana@example.com"
    assert " " not in _normalize_email("\tAna@Example.COM\n")


def test_invalid_inputs_rejected_with_valueerror():
    text = _contract_text()
    invalid = eval(  # noqa: S307 - contenido propio del contrato congelado
        _fenced_block(text, "frozen-invalid-inputs"),
        {"null": None, "true": True, "false": False},
    )
    assert set(invalid) == {"account_id", "provider", "email", "credential_ref"}
    for name, cases in invalid.items():
        assert any(case in ("", "  ") for case in cases), (
            "sin caso vacio para " + name
        )
        assert any(case is None for case in cases), "sin caso null para " + name
        assert any(isinstance(case, int) for case in cases), (
            "sin caso no-str para " + name
        )
    assert "ValueError" in text, "el contrato no declara rechazo con ValueError"


def test_no_network_no_disk_no_mutation():
    text = _contract_text()
    assert "pura respecto a la red y al disco" in text
    assert "no escribe archivos" in text
    assert "no muta la entrada" in text
    assert "result is not result2" in text, "sin ejemplo de determinismo"
    assert "OAuth" in text, "sin contexto de preparacion OAuth"