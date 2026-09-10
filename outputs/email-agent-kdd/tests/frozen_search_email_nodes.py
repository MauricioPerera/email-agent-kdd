"""Tests congelados del contrato search_email_nodes.

Oracle independiente: no importa el target ni search.py. Verifica la
estructura del contrato y los casos congelados (coincidencia simple, AND de
terminos, mayusculas, solo .md y sin coincidencias) definidos en frozen-cases.
"""

import json
from pathlib import Path
import re

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "search-email-nodes.md"
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
    assert "task: search_email_nodes" in frontmatter
    assert (
        "signature: \"def search_email_nodes(root: str, query: str) -> list\""
        in frontmatter
    )
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [pathlib, re]" in frontmatter
    assert "forbids: [eval, exec, subprocess, network_access]" in frontmatter


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


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def test_frozen_cases_cover_single_term_match():
    case = _case("single_term_match")
    query = case["query"]
    for path, content in case["tree"].items():
        if not path.endswith(".md"):
            continue
        contains = query.lower() in content.lower()
        listed = path in case["expected"]
        assert contains == listed, "coincidencia inconsistente en " + path
    assert "docs/archivo.txt" not in case["expected"], "los .txt deben ignorarse"
    assert case["expected"] == ["docs/guia.md", "notes/inbox.md", "readme.md"]


def test_frozen_cases_and_terms_all_required():
    case = _case("and_terms_all_required")
    terms = case["query"].split()
    assert len(terms) > 1, "el caso AND debe usar varios terminos"
    partial = {p for p in case["tree"] if p.endswith(".md")} - set(
        case["expected"]
    )
    assert partial, "el caso AND debe incluir archivos con solo parte de los terminos"
    for path in case["tree"]:
        if not path.endswith(".md"):
            assert path not in case["expected"], "no .md listado: " + path
            continue
        lowered = case["tree"][path].lower()
        complete = all(term in lowered for term in terms)
        listed = path in case["expected"]
        assert complete == listed, "AND inconsistente en " + path
    assert case["expected"] == ["mail/b.md", "mail/d.md"]


def test_frozen_cases_case_insensitive():
    case = _case("case_insensitive_terms")
    term = case["query"].lower()
    for path, content in case["tree"].items():
        if not path.endswith(".md"):
            continue
        contains = term in content.lower()
        listed = path in case["expected"]
        assert contains == listed, "coincidencia insensible inconsistente en " + path
    assert len(case["expected"]) == 3, "deben casar minusculas, MAYUSCULAS y Mixtas"


def test_frozen_cases_only_md_files_are_scanned():
    case = _case("only_md_files_are_scanned")
    term = case["query"].lower()
    ignored = [p for p in case["tree"] if not p.endswith(".md")]
    assert ignored, "el caso debe incluir archivos que no sean .md"
    assert all(p not in case["expected"] for p in ignored), "no .md listado"
    assert "inbox/tres.md.bak" in ignored, "la extension final debe ser .md"
    for path, content in case["tree"].items():
        if not path.endswith(".md"):
            continue
        contains = term in content.lower()
        listed = path in case["expected"]
        assert contains == listed, "coincidencia inconsistente en " + path
    assert case["expected"] == ["inbox/cuatro.md", "inbox/uno.md"]


def test_frozen_cases_shape_order_and_empty():
    cases = _frozen_cases()
    assert len(cases) >= 4, "el contrato debe congelar al menos 4 casos"
    for case in cases:
        assert isinstance(case["expected"], list)
        for path in case["expected"]:
            assert "\\" not in path, "separador no normalizado en " + path
            assert not path.startswith("/"), "la ruta debe ser relativa: " + path
            assert path.endswith(".md"), "solo .md puede listarse: " + path
        assert case["expected"] == sorted(case["expected"]), (
            "orden lexicografico esperado en " + case["name"]
        )
        assert case["tree"], "arbol vacio en el caso " + case["name"]
    assert _case("no_match_returns_empty")["expected"] == []