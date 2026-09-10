"""Tests congelados del contrato extract_outgoing_contacts.

Oracle independiente: no importa src.email ni el target. Verifica la
estructura del contrato y los casos congelados (direcciones simples y RFC,
deduplicacion primera-gana, entradas invalidas ignoradas, to vacio,
no-filtracion de asunto/cuerpo y rechazos estructurales) definidos en
frozen-cases y frozen-rejects.
"""

import json
from pathlib import Path
import re

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "extract-outgoing-contacts.md"
)


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(
        r"```" + label + r"\n(.*?)\n```", text, re.DOTALL
    )
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_cases():
    return json.loads(_fenced_block(_contract_text(), "frozen-cases"))


def _named(cases):
    return {c["name"]: c for c in cases}


def test_contract_frontmatter_and_budgets():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: extract_outgoing_contacts" in frontmatter
    assert (
        'signature: "def extract_outgoing_contacts(message: dict) -> list"'
        in frontmatter
    )
    assert "target: src/email/outgoing_contacts.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed:" in frontmatter
    assert "forbids:" in frontmatter


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


def test_contract_schema_compatible_with_store_email_contacts():
    text = _contract_text()
    assert "store_email_contacts" in text, "debe declarar compatibilidad con el store"
    assert 'claves `{"name": str, "email": str}`' in text
    for case in _frozen_cases():
        for contact in case["expected"]:
            assert set(contact) == {"name", "email"}, (
                "contacto con claves inesperadas: " + case["name"]
            )
            assert isinstance(contact["name"], str)
            assert isinstance(contact["email"], str)
            assert contact["email"] != "", "email vacio en caso: " + case["name"]


def test_frozen_case_only_reads_to_field():
    for case in _frozen_cases():
        message = case["message"]
        assert "to" in message, "el caso debe traer to: " + case["name"]
        assert isinstance(message["to"], list), "to debe ser list: " + case["name"]
        confirmed = {
            c["name"]
            for c in _frozen_cases()
            if c["name"] != "empty_to"
        }
        assert case["name"] in confirmed or case["name"] == "empty_to"


def test_frozen_addresses_lowercase_and_rfc_names():
    named = _named(_frozen_cases())
    plain = named["plain_and_rfc_addresses"]
    emails = [c["email"] for c in plain["expected"]]
    assert emails == ["ana@example.com", "bob@example.com"], (
        "orden y minusculas esperados en plain_and_rfc_addresses"
    )
    assert plain["message"]["to"][1] == "Bob <BOB@example.com>", (
        "el caso debe usar mayusculas en el header para forzar la normalizacion"
    )
    rfc = named["rfc_name_preserved"]
    assert rfc["expected"] == [{"name": "Ana Garcia", "email": "ana@example.com"}]
    for case in _frozen_cases():
        for contact in case["expected"]:
            assert contact["email"] == contact["email"].lower()
            assert contact["email"] == contact["email"].strip()


def test_frozen_dedup_first_wins():
    named = _named(_frozen_cases())
    case = named["dedup_first_wins"]
    raw = case["message"]["to"]
    assert len(raw) == 3, "el caso dedup debe traer 3 apariciones"
    assert raw[0] == "Ana Garcia <ana@example.com>", (
        "la primera aparicion debe llevar el nombre que gana"
    )
    assert case["expected"] == [{"name": "Ana Garcia", "email": "ana@example.com"}]


def test_frozen_invalid_entries_skipped():
    named = _named(_frozen_cases())
    case = named["invalid_entries_skipped"]
    raw = case["message"]["to"]
    assert len(raw) > len(case["expected"]), "el caso debe contener entradas invalidas"
    for value in raw:
        if not isinstance(value, str) or not value.strip():
            continue
        assert "<" in value or "@" in value, (
            "elemento str del caso invalid_entries_skipped debe ser parseable: " + repr(value)
        )
    emails = [c["email"] for c in case["expected"]]
    assert emails == ["bob@example.com", "carla@example.com"], (
        "los validos conservan su orden relativo"
    )
    empty = named["empty_to"]
    assert empty["message"]["to"] == [] and empty["expected"] == []


def test_frozen_no_secrets_or_body_leak():
    named = _named(_frozen_cases())
    case = named["no_secrets"]
    message = case["message"]
    assert "password" in message, "el caso no_secrets debe incluir una clave de credencial"
    serialized = json.dumps(case["expected"], ensure_ascii=False)
    for secret in (message["subject"], message["body"], message["password"]):
        assert secret not in serialized, "fuga de contenido del mensaje"
    for contact in case["expected"]:
        assert set(contact) == {"name", "email"}
    for forbidden in ("subject", "body", "account_id", "password", "id", "status"):
        for contact in _frozen_cases()[0]["expected"] + case["expected"]:
            assert forbidden not in contact


def test_frozen_rejects_structural_only():
    rejects = json.loads(_fenced_block(_contract_text(), "frozen-rejects"))
    assert len(rejects) >= 3, "deben congelarse los rechazos estructurales"
    named = _named(rejects)
    assert "missing_to" in named, "debe congelarse to ausente"
    assert "to_is_string" in named, "debe congelarse to como string"
    assert "to_is_null" in named, "debe congelarse to null"
    for case in rejects:
        assert set(case) == {"name", "message"}, "caso de rechazo con claves inesperadas"
        assert "to" not in case["message"] or not isinstance(
            case["message"]["to"], list
        ), "todo rechazo debe ser estructural: " + case["name"]
    # Un elemento no-str dentro de to NO rechaza: se ignora (ver invalid_entries_skipped).
    skipped = _named(_frozen_cases())["invalid_entries_skipped"]
    assert any(not isinstance(v, str) for v in skipped["message"]["to"]), (
        "los elementos no str se ignoran, no rechazan"
    )