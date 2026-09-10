"""Tests congelados del contrato cli_search.

Oracle independiente: no importa el target ni cli.py ni search.py. Verifica
la estructura del contrato y los casos congelados (ayuda, busqueda, errores
de argumentos y errores de busqueda) re-derivandolos con una implementacion
de referencia propia de la semantica CLI definida en frozen-cases.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-search.md"
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
    assert "task: cli_search" in frontmatter
    assert "signature: \"def cli_main(argv: list) -> int\"" in frontmatter
    assert "target: src/email/cli.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [argparse, sys]" in frontmatter
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


def test_contract_delegates_to_search_email_nodes():
    text = _contract_text()
    assert "src.email.search.search_email_nodes" in text, (
        "la CLI debe delegar en search_email_nodes"
    )
    assert "def search_email_nodes(root: str, query: str) -> list" in text
    assert "reimplementar la busqueda" in text, (
        "el contrato debe prohibir reimplementar la busqueda"
    )


class _SearchError(Exception):
    """Fallo de la referencia de busqueda (root invalido, query vacio)."""


def _reference_search(root, query):
    root_path = Path(root)
    if not root_path.is_dir():
        raise _SearchError("error: la raiz no existe o no es un directorio")
    terms = query.split()
    if not terms:
        raise _SearchError("error: el query no contiene terminos")
    matches = []
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        if all(term.lower() in lowered for term in terms):
            matches.append(path.relative_to(root_path).as_posix())
    return matches


def _reference_cli(argv):
    usage = "usage: email-cli [--help] | email-cli search ROOT QUERY"
    if argv and argv[0] in ("-h", "--help"):
        return 0, [usage, "  search ROOT QUERY  busca nodos .md"], []
    if not argv or argv[0] != "search":
        return 2, [], ["error: subcomando invalido", usage]
    if len(argv) != 3:
        return 2, [], ["error: search requiere ROOT y QUERY", usage]
    try:
        matches = _reference_search(argv[1], argv[2])
    except _SearchError as exc:
        return 1, [], [str(exc)]
    return 0, list(matches), []


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def _run_case(case):
    """Sustituye <root> por un arbol temporal y ejecuta la referencia CLI."""
    with tempfile.TemporaryDirectory() as tmp:
        tree = case.get("tree", {})
        for relpath, content in tree.items():
            target = Path(tmp) / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        argv = [a.replace("<root>", tmp) for a in case["argv"]]
        return _reference_cli(argv)


def _assert_case(case, code, stdout, stderr):
    assert code == case["code"], "codigo inesperado en " + case["name"]
    if "stdout" in case:
        assert stdout == case["stdout"], "stdout inesperado en " + case["name"]
    for fragment in case.get("stdout_has", []):
        assert fragment in "\n".join(stdout), (
            "stdout sin " + repr(fragment) + " en " + case["name"]
        )
    for fragment in case.get("stderr_has", []):
        assert fragment in "\n".join(stderr).lower(), (
            "stderr sin " + repr(fragment) + " en " + case["name"]
        )
    if case["code"] != 0:
        assert stderr, "falta mensaje amigable en stderr en " + case["name"]
        assert "Traceback" not in "\n".join(stderr), (
            "traceback expuesto al usuario en " + case["name"]
        )


def test_frozen_cases_cover_help_search_and_arg_error():
    cases = _frozen_cases()
    names = {case["name"] for case in cases}
    assert {"help_shows_usage", "search_single_term", "search_missing_query"} <= names, (
        "los casos deben cubrir ayuda, busqueda y error de argumentos"
    )
    assert _case("search_unknown_subcommand")["code"] == 2, (
        "subcomando desconocido debe ser error de argumentos"
    )
    assert _case("search_bad_root")["code"] != 0, (
        "fallo de busqueda debe dar codigo distinto de cero"
    )


def test_frozen_cases_help_shows_usage():
    for name in ("help_shows_usage", "help_short_flag"):
        code, stdout, stderr = _run_case(_case(name))
        _assert_case(_case(name), code, stdout, stderr)
        assert code == 0
        assert "usage:" in "\n".join(stdout).lower(), (
            "la ayuda debe imprimir el usage en stdout"
        )
    assert "search ROOT QUERY" in "\n".join(_run_case(_case("help_shows_usage"))[1]), (
        "la ayuda debe documentar el subcomando search ROOT QUERY"
    )


def test_frozen_cases_search_success_prints_one_per_line():
    for name in ("search_single_term", "search_and_terms", "search_no_matches"):
        case = _case(name)
        assert case["code"] == 0, "una busqueda exitosa debe retornar 0"
        code, stdout, stderr = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        for line in stdout:
            assert line.endswith(".md"), "resultado no .md en " + name
        assert stdout == sorted(stdout), "orden lexicografico esperado en " + name
    assert _case("search_single_term")["stdout"] == ["docs/guia.md", "notes/inbox.md"]
    assert _case("search_and_terms")["stdout"] == ["mail/b.md", "mail/d.md"]


def test_frozen_cases_arg_errors_are_friendly():
    for name in ("search_missing_query", "search_unknown_subcommand"):
        case = _case(name)
        assert case["code"] == 2, "error de argumentos debe retornar 2"
        code, stdout, stderr = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        assert stdout == [], "nada en stdout en error de argumentos"
        assert "usage:" in "\n".join(stderr).lower(), (
            "el error de argumentos debe mostrar el usage"
        )


def test_frozen_cases_search_errors_are_friendly():
    for name in ("search_bad_root", "search_empty_query"):
        case = _case(name)
        assert case["code"] == 1, "fallo de busqueda debe retornar 1"
        code, stdout, stderr = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        assert stdout == [], "nada en stdout en fallo de busqueda"
        assert "error" in "\n".join(stderr).lower(), (
            "el fallo de busqueda debe dar mensaje amigable"
        )


def test_frozen_cases_shape_and_determinism():
    cases = _frozen_cases()
    assert len(cases) >= 8, "el contrato debe congelar al menos 8 casos"
    for case in cases:
        assert isinstance(case["argv"], list), "argv debe ser lista"
        assert case["code"] in (0, 1, 2), "codigo de salida no previsto"
        if case["code"] == 0 and case["argv"][0] == "search":
            assert case.get("stdout") is not None, (
                "los casos search exitosos deben congelar stdout exacto"
            )
        if case["code"] != 0:
            assert case.get("stderr_has"), "falta mensaje amigable congelado"
    codes = {case["name"]: case["code"] for case in cases}
    assert codes["help_shows_usage"] == 0
    assert codes["search_single_term"] == 0
    assert codes["search_missing_query"] == 2
    assert codes["search_bad_root"] == 1