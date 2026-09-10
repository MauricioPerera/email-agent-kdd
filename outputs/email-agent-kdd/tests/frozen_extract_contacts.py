"""Tests congelados del contrato extract_contacts.

Oracle independiente: no importa el target ni normalize.py. Verifica la
estructura del contrato y los casos congelados (From/To/Cc, deduplicacion
por email en minusculas, header ausente, formato top-level de
parse_raw_email y equivalencia entre ambos formatos) definidos en
frozen-cases.
"""

import json
from pathlib import Path
import re

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "extract-contacts.md"
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


def test_contract_frontmatter_and_budgets():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: extract_contacts" in frontmatter
    assert "signature: \"def extract_contacts(record: dict) -> list\"" in frontmatter
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


def test_frozen_cases_cover_from_to_and_cc():
    case = {c["name"]: c for c in _frozen_cases()}["from_to_cc"]
    headers = case["record"]["headers"]
    for header in ("from", "to", "cc"):
        assert header in headers, "header ausente en el caso from_to_cc: " + header
    emails = [contact["email"] for contact in case["expected"]]
    assert "ana@example.com" in emails
    assert "user@example.com" in emails
    assert "bob@example.com" in emails
    assert "carla@example.com" in emails


def test_frozen_cases_dedup_by_lowercase_email():
    case = {c["name"]: c for c in _frozen_cases()}["dedup_by_lowercase_email"]
    headers = case["record"]["headers"]
    assert len({headers[h] for h in ("from", "to", "cc")}) == 3, "el caso dedup no varia el registro del email"
    lowered = set()
    for header in (headers[h] for h in ("from", "to", "cc")):
        match = re.search(r"<([^>]+)>", header)
        lowered.add((match.group(1) if match else header).strip().lower())
    assert lowered == {"ana@example.com"}, "el caso dedup debe representar una sola direccion"
    emails = [contact["email"] for contact in case["expected"]]
    assert emails == ["ana@example.com"], "deduplicacion esperada en un solo contacto"
    for email in emails:
        assert email == email.lower()


def test_frozen_cases_missing_header():
    case = {c["name"]: c for c in _frozen_cases()}["missing_cc_header"]
    headers = case["record"]["headers"]
    assert "cc" not in headers, "el caso missing_cc_header debe omitir cc"
    emails = [contact["email"] for contact in case["expected"]]
    assert "ana@example.com" in emails and "bob@example.com" in emails
    assert "carla@example.com" not in emails
    empty = {c["name"]: c for c in _frozen_cases()}["empty_headers"]
    assert empty["expected"] == []


def test_frozen_contacts_shape_and_order():
    cases = _frozen_cases()
    assert len(cases) >= 3, "el contrato debe congelar al menos 3 casos"
    for case in cases:
        for contact in case["expected"]:
            assert set(contact) == {"name", "email"}, "contacto con claves inesperadas"
            assert isinstance(contact["name"], str)
            assert contact["email"] == contact["email"].lower()
        emails = [contact["email"] for contact in case["expected"]]
        assert len(emails) == len(set(emails)), "duplicados en caso: " + case["name"]
    first = cases[0]
    assert [c["email"] for c in first["expected"]][:2] == [
        "ana@example.com",
        "user@example.com",
    ], "el orden From -> To debe respetarse en el caso from_to_cc"


def test_frozen_cases_top_level_format():
    named = {c["name"]: c for c in _frozen_cases()}
    case = named["top_level_format"]
    record = case["record"]
    assert "headers" not in record, "el caso top_level_format no debe traer headers"
    for field in ("from", "to", "cc"):
        assert isinstance(record.get(field), str) and record[field], (
            "campo top-level ausente en el caso top_level_format: " + field
        )
    emails = [contact["email"] for contact in case["expected"]]
    assert emails == [
        "luis@example.com",
        "dana@example.com",
        "erik@example.com",
        "fina@example.com",
    ], "orden From -> To -> Cc esperado en el caso top_level_format"
    assert emails[1] == "dana@example.com", "el email top-level debe salir en minusculas"


def test_frozen_cases_top_level_equivalent_to_headers():
    named = {c["name"]: c for c in _frozen_cases()}
    top = named["top_level_format"]
    nested = named["top_level_equivalent_to_headers"]
    headers = nested["record"]["headers"]
    assert headers["from"] == top["record"]["from"], "los casos de equivalencia deben usar los mismos valores"
    assert headers["to"] == top["record"]["to"]
    assert headers["cc"] == top["record"]["cc"]
    assert nested["expected"] == top["expected"], (
        "el formato headers y el top-level deben producir la misma lista"
    )