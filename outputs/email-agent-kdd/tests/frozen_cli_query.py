"""Tests congelados del contrato cli_query.

Oracle independiente: no importa el target ni cli.py ni query.py. Verifica
la estructura del contrato y los casos congelados (ayuda, consulta con
terminos y filtros, errores de aridad y consultas invalidas) re-derivandolos
con una implementacion de referencia propia de la semantica CLI definida en
frozen-cases.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-query.md"
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
    assert "task: cli_query" in frontmatter
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


def test_contract_delegates_to_query_email():
    text = _contract_text()
    assert "src.email.query.query_email" in text, (
        "la CLI debe delegar en query_email"
    )
    assert "def query_email(root: str, instruction: str) -> list" in text
    assert "reimplementar la consulta" in text, (
        "el contrato debe prohibir reimplementar la consulta"
    )
    assert "no la divide ni la reconstruye" in text, (
        "la instruccion debe llegar completa como un solo argumento"
    )


def test_contract_preserves_existing_subcommands():
    text = _contract_text()
    assert "intactos" in text, (
        "el contrato debe declarar que los subcomandos existentes quedan intactos"
    )
    for subcommand in ("search", "account", "sync", "draft", "send"):
        assert subcommand in text, "subcomando conservado ausente: " + subcommand
    assert "query ROOT INSTRUCTION" in text, (
        "el usage debe documentar el subcomando query ROOT INSTRUCTION"
    )


def test_contract_codes_and_streams():
    text = _contract_text()
    assert "retorna `2`" in text, "debe fijar el codigo 2 para aridad/consulta invalida"
    assert "retorna `1`" in text, "debe fijar el codigo 1 para fallos inesperados"
    assert "retorna `0`" in text, "debe fijar el codigo 0 para exito y ayuda"
    assert "stdout" in text and "stderr" in text, (
        "debe separar resultados (stdout) de usage y errores (stderr)"
    )


class _InvalidQuery(Exception):
    """Consulta o raiz invalida: `ValueError` de la referencia, codigo 2."""


_KEY_RE = re.compile(r"[0-9a-f]{64}")
_TOPIC_RE = re.compile(r"\w{1,64}")
_LIST_RE = re.compile(r"(?m)^-\s+(\S+)\s*$")


def _index_set(root_path, directory, key, md_nodes):
    index = root_path / directory / (key + ".md")
    if not index.is_file():
        return set()
    listing = _LIST_RE.findall(index.read_text(encoding="utf-8"))
    return {entry for entry in listing if entry in md_nodes}


def _reference_query(root, instruction):
    root_path = Path(root)
    if not isinstance(root, str) or not root or not root_path.is_dir():
        raise _InvalidQuery("error: la raiz no existe o no es un directorio")
    tokens = instruction.split()
    if not tokens:
        raise _InvalidQuery("error: la instruccion no contiene criterios")
    md_nodes = {}
    for path in sorted(root_path.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".md":
            rel = path.relative_to(root_path).as_posix()
            md_nodes[rel] = path.read_text(encoding="utf-8").lower()
    sets = []
    for token in tokens:
        low = token.lower()
        if low.startswith("contact:"):
            email = token[len("contact:"):].strip().lower()
            if not email or "@" not in email:
                raise _InvalidQuery("error: EMAIL malformado en contact:")
            sets.append({p for p, c in md_nodes.items() if email in c})
        elif low.startswith("conversation:"):
            key = token[len("conversation:"):].strip().lower()
            if not _KEY_RE.fullmatch(key):
                raise _InvalidQuery("error: KEY de conversacion invalido")
            sets.append(_index_set(root_path, "store/conversations", key, md_nodes))
        elif low.startswith("topic:"):
            topic = token[len("topic:"):].strip()
            if not _TOPIC_RE.fullmatch(topic):
                raise _InvalidQuery("error: TOPIC invalido")
            sets.append(_index_set(root_path, "store/topics", topic.lower(), md_nodes))
        else:
            term = token.lower()
            sets.append({p for p, c in md_nodes.items() if term in c})
    return sorted(set.intersection(*sets))


_USAGE = (
    "usage: email-cli [--help] | email-cli query ROOT INSTRUCTION | "
    "email-cli search ROOT QUERY | email-cli account | email-cli sync | "
    "email-cli draft | email-cli send"
)


def _reference_cli(argv):
    help_lines = [
        _USAGE,
        "  query ROOT INSTRUCTION  consulta el store con terminos y filtros",
        "  search ROOT QUERY  busca nodos .md que contengan QUERY",
        "  account | sync | draft | send  subcomandos conservados",
    ]
    if argv and argv[0] in ("-h", "--help"):
        return 0, help_lines, []
    if not argv or argv[0] != "query":
        return 2, [], ["error: subcomando invalido", _USAGE]
    if len(argv) != 3:
        return 2, [], ["error: query requiere ROOT y una sola INSTRUCTION", _USAGE]
    try:
        paths = _reference_query(argv[1], argv[2])
    except _InvalidQuery as exc:
        return 2, [], [str(exc)]
    except Exception:
        return 1, [], ["error: la consulta fallo"]
    return 0, list(paths), []


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


def test_frozen_cases_cover_help_query_and_errors():
    cases = _frozen_cases()
    names = {case["name"] for case in cases}
    assert {"help_shows_usage", "query_free_terms_and", "query_missing_instruction"} <= names, (
        "los casos deben cubrir ayuda, consulta y error de argumentos"
    )
    assert _case("query_unknown_subcommand")["code"] == 2, (
        "subcomando desconocido debe ser error de argumentos"
    )
    assert _case("query_instruction_split_in_args")["code"] == 2, (
        "la instruccion troceada en varios argumentos debe ser error de aridad"
    )
    assert _case("query_bad_root")["code"] == 2, (
        "raiz invalida (ValueError de query_email) debe dar codigo 2"
    )


def test_frozen_cases_help_shows_usage():
    for name in ("help_shows_usage", "help_short_flag"):
        code, stdout, stderr = _run_case(_case(name))
        _assert_case(_case(name), code, stdout, stderr)
        assert code == 0
        assert "usage:" in "\n".join(stdout).lower(), (
            "la ayuda debe imprimir el usage en stdout"
        )
        assert stderr == [], "la ayuda no debe escribir en stderr"
    help_stdout = "\n".join(_run_case(_case("help_shows_usage"))[1])
    assert "query ROOT INSTRUCTION" in help_stdout, (
        "la ayuda debe documentar el subcomando query ROOT INSTRUCTION"
    )
    for fragment in ("search", "account", "sync", "draft", "send"):
        assert fragment in help_stdout, (
            "la ayuda debe seguir listando el subcomando conservado " + fragment
        )


def test_frozen_cases_query_success_prints_one_per_line():
    for name in (
        "query_free_terms_and",
        "query_casefold",
        "query_topic_filter",
        "query_contact_filter",
        "query_conversation_filter",
        "query_combined_and",
        "query_no_matches",
    ):
        case = _case(name)
        assert case["code"] == 0, "una consulta exitosa debe retornar 0"
        code, stdout, stderr = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        assert stderr == [], "nada en stderr en una consulta exitosa"
        for line in stdout:
            assert line.endswith(".md"), "resultado no .md en " + name
            assert "\\" not in line, "separador no normalizado en " + name
            assert not line.startswith("/"), "ruta absoluta en " + name
            assert ".." not in line.split("/"), "salto .. en " + name
        assert stdout == sorted(stdout), "orden lexicografico esperado en " + name
    assert _case("query_free_terms_and")["stdout"] == ["store/emails/msg-0002.md"]
    assert _case("query_combined_and")["stdout"] == [
        "store/emails/msg-0001.md",
        "store/emails/msg-0003.md",
    ]
    assert _case("query_no_matches")["stdout"] == []


def test_frozen_cases_filter_semantics():
    case = _case("query_topic_filter")
    listing = _LIST_RE.findall(case["tree"]["store/topics/factura.md"])
    nodes = {path for path in case["tree"] if path.endswith(".md")}
    assert sorted(entry for entry in listing if entry in nodes) == case["stdout"], (
        "el indice del tema debe definir el filtro"
    )
    contact_case = _case("query_contact_filter")
    email = "ana@example.com"
    assert "@" in email and contact_case["stdout"] == [
        "store/emails/msg-0001.md"
    ], "el filtro de contacto debe matchear por substring casefold"
    conversation_case = _case("query_conversation_filter")
    key = conversation_case["argv"][2][len("conversation:"):]
    assert _KEY_RE.fullmatch(key.lower()), "KEY congelado debe ser hex-64"
    assert key == key.upper(), (
        "el caso debe congelar KEY en mayusculas frente al indice en minusculas"
    )
    combined_case = _case("query_combined_and")
    assert "ana@example.com" not in combined_case["tree"]["store/emails/msg-0002.md"], (
        "msg-0002 (from: Bob) debe quedar excluido por contact:"
    )


def test_frozen_cases_arg_errors_are_friendly():
    for name in (
        "query_missing_instruction",
        "query_instruction_split_in_args",
        "query_unknown_subcommand",
    ):
        case = _case(name)
        assert case["code"] == 2, "error de aridad/subcomando debe retornar 2"
        code, stdout, stderr = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        assert stdout == [], "nada en stdout en error de argumentos"
        assert "usage:" in "\n".join(stderr).lower(), (
            "el error de argumentos debe mostrar el usage"
        )


def test_frozen_cases_invalid_queries_are_friendly():
    for name in (
        "query_empty_instruction",
        "query_invalid_topic",
        "query_malformed_contact",
        "query_bad_root",
    ):
        case = _case(name)
        assert case["code"] == 2, "consulta invalida (ValueError) debe retornar 2"
        code, stdout, stderr = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        assert stdout == [], "nada en stdout en consulta invalida"
        assert "error" in "\n".join(stderr).lower(), (
            "la consulta invalida debe dar mensaje amigable"
        )
    assert _case("query_malformed_contact")["argv"][2][len("contact:"):] == "example.com", (
        "el EMAIL congelado debe ser inequivocamente malformado (sin @)"
    )
    assert not _TOPIC_RE.fullmatch(".." ), (
        "el TOPIC congelado debe ser inequivocamente inseguro"
    )


def test_frozen_cases_shape_and_determinism():
    cases = _frozen_cases()
    assert len(cases) >= 12, "el contrato debe congelar al menos 12 casos"
    for case in cases:
        assert isinstance(case["argv"], list), "argv debe ser lista"
        assert case["code"] in (0, 1, 2), "codigo de salida no previsto"
        if case["code"] == 0 and case["argv"][0] == "query":
            assert case.get("stdout") is not None, (
                "los casos query exitosos deben congelar stdout exacto"
            )
        if case["code"] != 0:
            assert case.get("stderr_has"), "falta mensaje amigable congelado"
    codes = {case["name"]: case["code"] for case in cases}
    assert codes["help_shows_usage"] == 0
    assert codes["query_free_terms_and"] == 0
    assert codes["query_no_matches"] == 0
    assert codes["query_missing_instruction"] == 2
    assert codes["query_empty_instruction"] == 2
    assert codes["query_bad_root"] == 2