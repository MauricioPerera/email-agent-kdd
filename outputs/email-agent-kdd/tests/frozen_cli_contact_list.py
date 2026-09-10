"""Tests congelados del contrato cli_contact_list.

Oracle independiente: no importa el target ni cli.py ni contact_store.py.
Verifica la estructura del contrato (frontmatter, secciones, delegacion
textual en load_email_contacts y preservacion de account/query/read/
search/sync/draft/send) y los casos congelados (exito, orden del store,
lista vacia, store corrupto/fuera de esquema, arity/subcomando y sin
exposicion de secretos) re-derivandolos con una implementacion de
referencia propia de la semantica CLI definida en frozen-cases, que a su
vez delega en una referencia espejo de load_email_contacts.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-contact-list.md"
)

_CONTACT_KEYS = ("name", "email")
_PRESERVED = ("account", "query", "read", "search", "sync", "draft", "send")


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
    assert "task: cli_contact_list" in frontmatter
    assert "signature: \"def cli_main(argv: list) -> int\"" in frontmatter
    assert "target: src/email/cli.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [argparse, sys, json, pathlib]" in frontmatter
    assert "forbids: [eval, exec, subprocess, network_access]" in frontmatter
    assert "tests: tests/frozen_cli_contact_list.py" in frontmatter


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


def test_contract_delegates_to_load_email_contacts():
    text = _contract_text()
    assert "src.email.contact_store.load_email_contacts" in text, (
        "contact list debe delegar la lectura en load_email_contacts"
    )
    assert "def load_email_contacts(root: str) -> list" in text, (
        "firma de load_email_contacts congelada en el contrato"
    )
    assert "reimplementar la lectura" in text, (
        "el contrato debe prohibir reimplementar la lectura/validacion/esquema"
    )
    assert "contacts.json" in text, "el contrato fija la ruta del store"
    assert "ValueError" in text and "RuntimeError" in text, (
        "los errores del store se traducen al codigo 1"
    )


def test_contract_output_is_name_email_json_lines():
    text = _contract_text()
    assert "una linea JSON por contacto" in text, (
        "contact list imprime una linea JSON por contacto"
    )
    assert "en el MISMO orden devuelto" in text, (
        "el orden del listado sigue al devuelto por la carga"
    )
    for key in _CONTACT_KEYS:
        assert key in text, "el esquema publico debe nombrar " + key
    for extra in ("password", "secret", "token"):
        assert extra in text, "el contrato debe prohibir exponer " + extra


def test_contract_preserves_other_subcommands():
    text = _contract_text()
    for subcommand in _PRESERVED:
        assert subcommand in text, (
            "el contrato debe mantener el subcomando " + subcommand
        )
    assert "conservan exactamente su semantica" in text
    assert "Don't: alterar los subcomandos" in text


# --- Referencia espejo de load_email_contacts -------------------------------


def _reference_load_email_contacts(root):
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root debe ser un str no vacio")
    path = Path(root) / "contacts.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("contacts.json corrupto o ilegible") from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"contacts"}
        or not isinstance(data["contacts"], list)
    ):
        raise RuntimeError("contacts.json no tiene el esquema esperado")
    records = []
    for entry in data["contacts"]:
        if not isinstance(entry, dict) or set(entry) != {"name", "email"}:
            raise RuntimeError("contacto fuera del esquema name/email")
        if not isinstance(entry["email"], str) or not entry["email"].strip():
            raise RuntimeError("contacto con email vacio")
        if not isinstance(entry["name"], str):
            raise RuntimeError("contacto con name no textual")
        records.append({"name": entry["name"], "email": entry["email"]})
    return records


# --- Referencia de la semantica CLI congelada -------------------------------

_USAGE = (
    "usage: email-cli [--help] | email-cli query ROOT INSTRUCTION | "
    "email-cli search ROOT QUERY | email-cli read ROOT REL_PATH | "
    "email-cli account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF | "
    "email-cli account setup ROOT | email-cli account list ROOT | "
    "email-cli contact list ROOT | email-cli sync ROOT ACCOUNT_ID [HOST] | "
    "email-cli draft ROOT ACCOUNT_ID TO SUBJECT BODY | "
    "email-cli send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR ENVIO"
)


def _reference_cli(argv):
    if argv and argv[0] in ("-h", "--help"):
        return 0, [_USAGE], []
    if not argv or argv[0] != "contact":
        return 2, [], ["error: subcomando invalido", _USAGE]
    if len(argv) < 2 or argv[1] != "list":
        return 2, [], ["error: contact requiere el subcomando 'list'", _USAGE]
    if len(argv) != 3:
        return 2, [], ["error: contact list requiere exactamente ROOT", _USAGE]
    try:
        contacts = _reference_load_email_contacts(argv[2])
    except (ValueError, RuntimeError):
        return 1, [], [
            "error: no se pudieron leer los contactos "
            "(almacenamiento invalido)"
        ]
    lines = [
        json.dumps({"name": contact["name"], "email": contact["email"]})
        for contact in contacts
    ]
    return 0, lines, []


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def _run_case(case):
    """Sustituye <root> por un arbol temporal y ejecuta la referencia CLI."""
    with tempfile.TemporaryDirectory() as tmp:
        for relpath, content in case.get("tree", {}).items():
            target = Path(tmp) / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        if case.get("store"):
            store_path = Path(tmp) / "contacts.json"
            payload = json.dumps(
                {"contacts": case["store"]}, sort_keys=True, ensure_ascii=False
            )
            store_path.write_text(payload + "\n", encoding="utf-8")
        argv = [a.replace("<root>", tmp) for a in case["argv"]]
        return _reference_cli(argv)


def _assert_case(case, result):
    code, stdout, stderr = result
    combined = "\n".join(stdout) + "\n" + "\n".join(stderr)
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
    for secret in case.get("secrets", []):
        assert secret not in combined, (
            "secreto " + repr(secret) + " expuesto en " + case["name"]
        )
    if case["code"] != 0:
        assert stderr, "falta mensaje amigable en stderr en " + case["name"]
        assert "Traceback" not in "\n".join(stderr), (
            "traceback expuesto al usuario en " + case["name"]
        )
        assert "MARCADOR" not in combined and "token" not in combined, (
            "contenido de entradas filtrado en " + case["name"]
        )


def test_frozen_cases_cover_success_empty_corrupt_and_arity():
    cases = _frozen_cases()
    names = {case["name"] for case in cases}
    assert {
        "help_shows_usage",
        "contact_list_success",
        "contact_list_empty_root",
        "contact_list_missing_root_arg",
        "contact_unknown_subcommand",
        "contact_list_corrupt_store",
    } <= names, "los casos deben cubrir exito, vacio, corrupto y arity"
    assert len(cases) >= 10, "el contrato debe congelar al menos 10 casos"
    codes = {case["name"]: case["code"] for case in cases}
    assert codes["contact_list_success"] == 0
    assert codes["contact_list_preserves_file_order"] == 0
    assert codes["contact_list_empty_root"] == 0
    assert codes["contact_list_missing_root_arg"] == 2
    assert codes["contact_list_extra_args"] == 2
    assert codes["contact_bare"] == 2
    assert codes["contact_unknown_subcommand"] == 2
    assert codes["unknown_subcommand"] == 2
    assert codes["contact_list_corrupt_store"] == 1
    assert codes["contact_list_out_of_schema"] == 1
    assert codes["contact_list_empty_root_value"] == 1


def test_frozen_cases_help_shows_usage():
    case = _case("help_shows_usage")
    assert case["code"] == 0
    code, stdout, stderr = _run_case(case)
    _assert_case(case, (code, stdout, stderr))
    assert code == 0
    text = "\n".join(stdout).lower()
    assert "usage:" in text, "la ayuda debe imprimir el usage en stdout"
    assert "contact list root" in text, (
        "la ayuda debe documentar contact list ROOT"
    )
    for subcommand in _PRESERVED:
        assert subcommand in text, (
            "la ayuda conserva el subcomando " + subcommand
        )


def test_frozen_cases_contact_list_prints_name_email_json_lines():
    case = _case("contact_list_success")
    assert case["code"] == 0
    code, stdout, stderr = _run_case(case)
    _assert_case(case, (code, stdout, stderr))
    assert code == 0
    assert len(stdout) == 2, "una linea JSON por contacto"
    assert stderr == []
    for line, expected in zip(stdout, case["store"]):
        parsed = json.loads(line)
        assert list(parsed) == ["name", "email"], (
            "el JSON listado tiene exactamente las claves name y email"
        )
        assert parsed == expected, "contacto alterado por el listado"
    assert "token" not in combined_text(stdout, stderr)
    assert "credential_ref" not in combined_text(stdout, stderr)


def combined_text(stdout, stderr):
    return "\n".join(stdout) + "\n" + "\n".join(stderr)


def test_frozen_cases_list_order_follows_load():
    case = _case("contact_list_preserves_file_order")
    assert case["code"] == 0
    code, stdout, stderr = _run_case(case)
    _assert_case(case, (code, stdout, stderr))
    assert code == 0
    assert stdout == case["stdout"], (
        "el orden del listado es el devuelto por la carga, sin reordenar"
    )


def test_frozen_cases_empty_root_is_success():
    case = _case("contact_list_empty_root")
    assert case.get("store") is None, "raiz sin store congelada"
    code, stdout, stderr = _run_case(case)
    _assert_case(case, (code, stdout, stderr))
    assert code == 0
    assert stdout == [], "raiz o store ausente produce lista vacia"
    assert stderr == []


def test_frozen_cases_arg_errors_are_friendly():
    for name in (
        "contact_list_missing_root_arg",
        "contact_list_extra_args",
        "contact_bare",
        "contact_unknown_subcommand",
        "unknown_subcommand",
    ):
        case = _case(name)
        assert case["code"] == 2, "error de argumentos debe retornar 2 en " + name
        code, stdout, stderr = _run_case(case)
        _assert_case(case, (code, stdout, stderr))
        assert stdout == [], "nada en stdout en error de argumentos"
        assert "usage:" in "\n".join(stderr).lower(), (
            "el error de argumentos debe mostrar el usage"
        )


def test_frozen_cases_store_errors_are_generic_and_hide_secrets():
    for name in (
        "contact_list_corrupt_store",
        "contact_list_out_of_schema",
        "contact_list_empty_root_value",
    ):
        case = _case(name)
        assert case["code"] == 1, (
            "error de almacenamiento/validacion debe retornar 1 en " + name
        )
        code, stdout, stderr = _run_case(case)
        _assert_case(case, (code, stdout, stderr))
        assert stdout == [], "nada en stdout en error de almacenamiento"
        stderr_text = "\n".join(stderr)
        assert "error" in stderr_text.lower(), (
            "el error de almacenamiento debe dar mensaje generico"
        )
        assert "Traceback" not in stderr_text, "sin traceback"
        for secret in case.get("secrets", []):
            assert secret not in stderr_text, (
                "secreto filtrado en stderr en " + name
            )


def test_frozen_cases_shape_and_determinism():
    cases = _frozen_cases()
    for case in cases:
        assert isinstance(case["argv"], list), "argv debe ser lista"
        assert case["argv"][0] in ("contact", "--help", "frobnicate"), (
            "argv de caso no previsto: " + case["argv"][0]
        )
        assert case["code"] in (0, 1, 2), "codigo de salida no previsto"
        if case["code"] == 0 and case["argv"][0] == "contact":
            assert case.get("stdout") is not None, (
                "los casos contact exitosos deben congelar stdout exacto"
            )
        if case["code"] != 0:
            assert case.get("stderr_has"), "falta mensaje amigable congelado"
            for fragment in case.get("stderr_has", []):
                assert fragment in ("error", "usage:"), (
                    "mensaje de error congelado con detalle de entradas en "
                    + case["name"]
                )