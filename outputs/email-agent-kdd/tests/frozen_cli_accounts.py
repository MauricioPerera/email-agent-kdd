"""Tests congelados del contrato cli_accounts.

Oracle independiente: no importa el target ni cli.py ni account.py ni
account_store.py. Verifica la estructura del contrato y los casos congelados
(help, account add, account list, errores de argumentos, errores de
almacenamiento/validacion y search intacto) re-derivandolos con una
implementacion de referencia propia de la semantica CLI definida en
frozen-cases, que a su vez delega en referencias espejo de
create_email_account / save_email_account / load_email_accounts.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-accounts.md"
)

_RECORD_KEYS = ("account_id", "provider", "email", "credential_ref", "status")
_PUBLIC_KEYS = ("account_id", "provider", "email", "status")


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
    assert "task: cli_accounts" in frontmatter
    assert "signature: \"def cli_main(argv: list) -> int\"" in frontmatter
    assert "target: src/email/cli.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [argparse, sys, json]" in frontmatter
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


def test_contract_delegates_to_account_functions():
    text = _contract_text()
    assert "src.email.account.create_email_account" in text, (
        "account add debe delegar la creacion en create_email_account"
    )
    assert (
        "def create_email_account(account_id: str, provider: str, "
        "email: str, credential_ref: str) -> dict" in text
    ), "firma de create_email_account congelada en el contrato"
    assert "src.email.account_store.save_email_account" in text, (
        "account add debe delegar el guardado en save_email_account"
    )
    assert "def save_email_account(root: str, account: dict) -> str" in text
    assert "src.email.account_store.load_email_accounts" in text, (
        "account list debe delegar la lectura en load_email_accounts"
    )
    assert "def load_email_accounts(root: str) -> list" in text
    assert "reimplementar la creacion" in text, (
        "el contrato debe prohibir reimplementar la creacion/guardado/lectura"
    )


def test_contract_forbids_credential_ref_in_output():
    text = _contract_text()
    assert "credential_ref" in text
    assert "jam" in text.lower() and "credential_ref" in text
    assert "PARAR y reportar si" in text and "credential_ref" in text.split(
        "PARAR y reportar si", 1
    )[1], "el stop del contrato debe nombrar credential_ref"
    for case in _frozen_cases():
        for secret in case.get("secrets", []):
            assert secret not in "\n".join(case.get("stdout", [])), (
                "stdout congelado filtra un secreto en " + case["name"]
            )
        if case["code"] != 0:
            assert "credential_ref" not in "\n".join(
                case.get("stderr_has", [])
            ), "los mensajes de error no deben nombrar credential_ref"


def test_contract_preserves_search_semantics():
    text = _contract_text()
    assert "src.email.search.search_email_nodes" in text, (
        "el contrato debe mantener search sobre search_email_nodes"
    )
    assert "conserva exactamente su semantica" in text
    assert "Don't: alterar el subcomando" in text


# --- Referencias espejo de las funciones de cuentas -------------------------


def _require_non_empty_str(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " debe ser un str no vacio")
    return value


def _reference_create_email_account(account_id, provider, email, credential_ref):
    _require_non_empty_str(account_id, "account_id")
    _require_non_empty_str(provider, "provider")
    _require_non_empty_str(email, "email")
    _require_non_empty_str(credential_ref, "credential_ref")
    return {
        "account_id": account_id,
        "provider": provider.strip().lower(),
        "email": "".join(email.split()).lower(),
        "credential_ref": credential_ref,
        "status": "disconnected",
    }


def _reference_validate_record(record, error):
    if not isinstance(record, dict):
        raise error("account debe ser un dict")
    if set(record) != set(_RECORD_KEYS):
        raise error("account debe tener exactamente las claves del registro")
    for key in _RECORD_KEYS[:4]:
        if not isinstance(record[key], str) or not record[key].strip():
            raise error(key + " debe ser un str no vacio")
    if record["status"] != "disconnected":
        raise error('status debe ser "disconnected"')


def _reference_store_path(root):
    _require_non_empty_str(root, "root")
    return Path(root) / ".email-agent" / "accounts.json"


def _reference_read_records(path, error):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise error("accounts.json corrupto o ilegible: " + type(exc).__name__)
    if not isinstance(data, dict) or set(data) != {"accounts"}:
        raise error("accounts.json no tiene el esquema esperado")
    records = []
    for record in data["accounts"]:
        _reference_validate_record(record, error)
        records.append({key: record[key] for key in _RECORD_KEYS})
    return records


def _reference_save_email_account(root, account):
    path = _reference_store_path(root)
    _reference_validate_record(account, ValueError)
    records = (
        _reference_read_records(path, RuntimeError) if path.exists() else []
    )
    records = [r for r in records if r["account_id"] != account["account_id"]]
    records.append({key: account[key] for key in _RECORD_KEYS})
    path.parent.mkdir(parents=True, exist_ok=True)
    records.sort(key=lambda r: r["account_id"])
    payload = json.dumps({"accounts": records}, sort_keys=True, ensure_ascii=False)
    path.write_text(payload + "\n", encoding="utf-8")
    return str(path.resolve())


def _reference_load_email_accounts(root):
    path = _reference_store_path(root)
    if not path.exists():
        return []
    records = _reference_read_records(path, RuntimeError)
    records.sort(key=lambda r: r["account_id"])
    return records


# --- Referencia de la semantica CLI congelada -------------------------------


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


def _reference_cli(argv, root):
    usage = (
        "usage: email-cli [--help] | email-cli search ROOT QUERY | "
        "email-cli account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF | "
        "email-cli account list ROOT"
    )
    if argv and argv[0] in ("-h", "--help"):
        return 0, [usage, "  account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF", "  account list ROOT", "  search ROOT QUERY  busca nodos .md"], []
    if not argv:
        return 2, [], ["error: subcomando invalido", usage]
    if argv[0] == "account":
        if len(argv) < 2 or argv[1] not in ("add", "list"):
            return 2, [], ["error: account requiere 'add' o 'list'", usage]
        if argv[1] == "add":
            if len(argv) != 7:
                return 2, [], ["error: account add requiere ROOT, ACCOUNT_ID, PROVIDER, EMAIL y CREDENTIAL_REF", usage]
            try:
                account = _reference_create_email_account(
                    argv[3], argv[4], argv[5], argv[6]
                )
                _reference_save_email_account(argv[2], account)
            except (ValueError, RuntimeError):
                return 1, [], ["error: no se pudo guardar la cuenta (datos o almacenamiento invalidos)"]
            return 0, ["account saved: " + account["account_id"]], []
        if len(argv) != 3:
            return 2, [], ["error: account list requiere exactamente ROOT", usage]
        try:
            records = _reference_load_email_accounts(argv[2])
        except (ValueError, RuntimeError):
            return 1, [], ["error: no se pudieron leer las cuentas (almacenamiento invalido)"]
        lines = [
            json.dumps(
                {key: record[key] for key in _PUBLIC_KEYS}, sort_keys=True
            )
            for record in records
        ]
        return 0, lines, []
    if argv[0] == "search":
        if len(argv) != 3:
            return 2, [], ["error: search requiere exactamente ROOT y QUERY", usage]
        try:
            matches = _reference_search(argv[1], argv[2])
        except _SearchError:
            return 1, [], ["error: la busqueda fallo (raiz invalida o query sin terminos)"]
        return 0, list(matches), []
    return 2, [], ["error: subcomando invalido (se esperaba 'search' o 'account')", usage]


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def _run_case(case):
    """Sustituye <root> por un arbol temporal y ejecuta la referencia CLI."""
    with tempfile.TemporaryDirectory() as tmp:
        for relpath, content in case.get("tree", {}).items():
            target = Path(tmp) / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        store_path = Path(tmp) / ".email-agent" / "accounts.json"
        if case.get("store"):
            for record in case["store"]:
                _reference_save_email_account(tmp, dict(record))
        argv = [a.replace("<root>", tmp) for a in case["argv"]]
        code, stdout, stderr = _reference_cli(argv, tmp)
        stored = None
        if case.get("expect_store") and store_path.exists():
            stored = _reference_read_records(store_path, RuntimeError)
        return code, stdout, stderr, stored


def _assert_case(case, result):
    code, stdout, stderr, stored = result
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
        assert "credential_ref" not in combined, (
            "credential_ref filtrado en salida de error en " + case["name"]
        )
    if case["code"] != 0:
        assert stderr, "falta mensaje amigable en stderr en " + case["name"]
        assert "Traceback" not in "\n".join(stderr), (
            "traceback expuesto al usuario en " + case["name"]
        )
    expected = case.get("expect_store")
    if expected:
        assert stored is not None, "el store no se escribio en " + case["name"]
        matches = [r for r in stored if r["account_id"] == expected["account_id"]]
        assert len(matches) == 1, "registro esperado ausente en " + case["name"]
        for key, value in expected.items():
            assert matches[0][key] == value, (
                "campo " + key + " inesperado en " + case["name"]
            )
        assert matches[0]["credential_ref"] in case.get("secrets", []), (
            "credential_ref verbatim esperado en el store en " + case["name"]
        )


def test_frozen_cases_cover_account_add_list_and_errors():
    cases = _frozen_cases()
    names = {case["name"] for case in cases}
    assert {
        "help_shows_usage",
        "account_add_success",
        "account_list_success",
        "account_list_empty_root",
        "account_add_missing_args",
        "account_list_missing_root_arg",
        "search_semantics_preserved",
    } <= names, "los casos deben cubrir add, list, lista vacia, arity y search"
    assert len(cases) >= 10, "el contrato debe congelar al menos 10 casos"
    codes = {case["name"]: case["code"] for case in cases}
    assert codes["account_add_success"] == 0
    assert codes["account_list_empty_root"] == 0
    assert codes["account_add_missing_args"] == 2
    assert codes["account_unknown_subcommand"] == 2
    assert codes["account_add_invalid_input"] == 1
    assert codes["account_add_corrupt_store"] == 1
    assert codes["account_list_corrupt_store"] == 1
    assert codes["search_semantics_preserved"] == 0
    assert codes["search_arg_error_preserved"] == 2


def test_frozen_cases_help_shows_usage():
    case = _case("help_shows_usage")
    assert case["code"] == 0
    code, stdout, stderr, _ = _run_case(case)
    _assert_case(case, (code, stdout, stderr, _))
    assert code == 0
    text = "\n".join(stdout).lower()
    assert "usage:" in text, "la ayuda debe imprimir el usage en stdout"
    assert "account add root account_id provider email credential_ref" in text, (
        "la ayuda debe documentar account add"
    )
    assert "account list root" in text, "la ayuda debe documentar account list"
    assert "search root query" in text, "la ayuda conserva search ROOT QUERY"


def test_frozen_cases_account_add_delegates_and_prints_only_saved_line():
    case = _case("account_add_success")
    assert case["code"] == 0
    code, stdout, stderr, stored = _run_case(case)
    _assert_case(case, (code, stdout, stderr, stored))
    assert code == 0
    assert stdout == ["account saved: personal"], (
        "account add imprime unicamente 'account saved: ACCOUNT_ID'"
    )
    assert stderr == []
    record = [r for r in stored if r["account_id"] == "personal"][0]
    assert record["provider"] == "gmail", "provider normalizado en minusculas"
    assert record["email"] == "yo@example.com", "email normalizado"
    assert record["status"] == "disconnected"
    assert record["credential_ref"] == "vault://gmail-personal", (
        "credential_ref verbatim solo en el store, nunca en stdout/stderr"
    )


def test_frozen_cases_account_list_prints_json_without_secrets():
    case = _case("account_list_success")
    assert case["code"] == 0
    code, stdout, stderr, _ = _run_case(case)
    _assert_case(case, (code, stdout, stderr, _))
    assert code == 0
    assert len(stdout) == 2, "una linea JSON por cuenta"
    assert stdout[0] < stdout[1] or "a1" in stdout[0], (
        "el orden del listado sigue al store (por account_id)"
    )
    assert stdout[0].startswith('{"account_id": "a1"'), (
        "primera cuenta ordenada por account_id"
    )
    for line in stdout:
        parsed = json.loads(line)
        assert set(parsed) == set(_PUBLIC_KEYS), (
            "el JSON listado solo expone account_id, provider, email y status"
        )
        assert "credential_ref" not in line, (
            "el listado jamas imprime credential_ref"
        )


def test_frozen_cases_account_list_empty_root_is_success():
    case = _case("account_list_empty_root")
    assert case.get("store") is None, "raiz sin store congelada"
    code, stdout, stderr, _ = _run_case(case)
    _assert_case(case, (code, stdout, stderr, _))
    assert code == 0
    assert stdout == [], "raiz o archivo ausente produce lista vacia"
    assert stderr == []


def test_frozen_cases_arg_errors_are_friendly():
    for name in (
        "account_add_missing_args",
        "account_list_missing_root_arg",
        "account_unknown_subcommand",
        "search_arg_error_preserved",
    ):
        case = _case(name)
        assert case["code"] == 2, "error de argumentos debe retornar 2 en " + name
        code, stdout, stderr, _ = _run_case(case)
        _assert_case(case, (code, stdout, stderr, _))
        assert stdout == [], "nada en stdout en error de argumentos"
        assert "usage:" in "\n".join(stderr).lower(), (
            "el error de argumentos debe mostrar el usage"
        )


def test_frozen_cases_storage_errors_are_generic_and_hide_secrets():
    for name in (
        "account_add_invalid_input",
        "account_add_corrupt_store",
        "account_list_corrupt_store",
    ):
        case = _case(name)
        assert case["code"] == 1, "error de almacenamiento/validacion debe retornar 1"
        code, stdout, stderr, _ = _run_case(case)
        _assert_case(case, (code, stdout, stderr, _))
        assert stdout == [], "nada en stdout en error de almacenamiento"
        stderr_text = "\n".join(stderr)
        assert "error" in stderr_text.lower(), (
            "el error de almacenamiento debe dar mensaje generico"
        )
        assert "Traceback" not in stderr_text, "sin traceback"
        for secret in case.get("secrets", []):
            assert secret not in stderr_text, (
                "credential_ref/secreto filtrado en stderr en " + name
            )


def test_frozen_cases_search_semantics_are_untouched():
    case = _case("search_semantics_preserved")
    assert case["argv"][0] == "search"
    code, stdout, stderr, _ = _run_case(case)
    _assert_case(case, (code, stdout, stderr, _))
    assert code == 0
    assert stdout == case["stdout"], "search conserva su stdout congelado"
    assert stderr == []


def test_frozen_cases_shape_and_determinism():
    cases = _frozen_cases()
    for case in cases:
        assert isinstance(case["argv"], list), "argv debe ser lista"
        assert case["argv"][0] in ("account", "search", "--help"), (
            "argv de caso no previsto: " + case["argv"][0]
        )
        assert case["code"] in (0, 1, 2), "codigo de salida no previsto"
        if case["code"] == 0 and case["argv"][0] == "account":
            assert case.get("stdout") is not None, (
                "los casos account exitosos deben congelar stdout exacto"
            )
        if case["code"] != 0:
            assert case.get("stderr_has"), "falta mensaje amigable congelado"
            assert "credential_ref" not in " ".join(case.get("stderr_has", [])), (
                "los mensajes de error congelados no nombran credential_ref"
            )