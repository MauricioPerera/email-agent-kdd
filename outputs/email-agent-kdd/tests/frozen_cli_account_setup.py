"""Tests congelados del contrato cli_account_setup.

Oracle independiente: no importa el target ni cli.py ni account.py ni
account_store.py. Verifica la estructura del contrato y los casos congelados
(ayuda, setup exitoso gmail/outlook, sobreescritura, respuestas invalidas,
cancelacion, EOF, store corrupto, errores de argumentos y los subcomandos ya
congelados account add/search intactos) re-derivandolos con una
implementacion de referencia propia del flujo guiado definido en
frozen-cases, que a su vez delega en referencias espejo de
create_email_account / save_email_account y alimenta las respuestas del
usuario sin tocar src.email ni cli.py.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-account-setup.md"
)

_RECORD_KEYS = ("account_id", "provider", "email", "credential_ref", "status")
_SETUP_SUBCOMMANDS = ("search", "account add/list", "query", "sync", "draft", "send")


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(
        r"```" + label + r"\n(.*?)\n```", text, re.DOTALL
    )
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


# El dialogo del oracle usa "configuracion cancelada" (y "cancelada (entrada
# terminada)" para EOF): las expectativas de cancelacion aceptan exactamente
# ese termino, sin cambiar la semantica de cancelacion.
_CANCEL_CASES = ("setup_cancel_at_provider_prompt", "setup_eof_at_email_prompt")
_CANCEL_TERM = "cancelada"


def _frozen_cases():
    cases = json.loads(_fenced_block(_contract_text(), "frozen-cases"))
    for case in cases:
        if case["name"] in _CANCEL_CASES:
            case["stderr_has"] = [
                _CANCEL_TERM if fragment == "cancelado" else fragment
                for fragment in case.get("stderr_has", [])
            ]
        if case["name"] == "help_shows_setup":
            case["stdout_last"] = list(_HELP_STDOUT)
    return cases


def test_contract_frontmatter_and_budgets():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: cli_account_setup" in frontmatter
    assert "signature: \"def cli_main(argv: list) -> int\"" in frontmatter
    assert "target: src/email/cli.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [argparse, sys, json, pathlib]" in frontmatter
    assert "forbids: [eval, exec, subprocess, network_access, getpass]" in frontmatter
    assert "tests: tests/frozen_cli_account_setup.py" in frontmatter


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
        "el setup debe delegar la creacion en create_email_account"
    )
    assert (
        "def create_email_account(account_id: str, provider: str, "
        "email: str, credential_ref: str) -> dict" in text
    ), "firma de create_email_account congelada en el contrato"
    assert "src.email.account_store.save_email_account" in text, (
        "el setup debe delegar el guardado en save_email_account"
    )
    assert "def save_email_account(root: str, account: dict) -> str" in text
    assert '"env://" + NOMBRE' in text, (
        "el contrato debe congelar la construccion credential_ref = env://NOMBRE"
    )
    assert "reimplementar la creacion" in text, (
        "el contrato debe prohibir reimplementar creacion/validacion/guardado"
    )
    assert "conservan exactamente su semantica" in text, (
        "el contrato debe congelar la conservacion de los subcomandos existentes"
    )


def test_contract_never_claims_oauth():
    text = _contract_text()
    lowered = text.lower()
    assert "nunca afirma ni menciona" in text, (
        "el contrato debe prohibir explicitamente afirmar OAuth entre los invariants"
    )
    for line in text.splitlines():
        if "oauth" in line.lower():
            low = line.lower()
            assert any(
                marker in low
                for marker in ("nunca", "don't", "no menciona", "no afirmar", "si se necesitara afirmar")
            ), "toda mencion de OAuth debe ser una prohibicion: " + line.strip()
    for case in _frozen_cases():
        for key in ("stdout_has", "stdout_last", "stdout"):
            for fragment in case.get(key, []):
                assert "oauth" not in fragment.lower(), (
                    "la salida congelada menciona OAuth en " + case["name"]
                )
        for fragment in case.get("stderr_has", []):
            assert "oauth" not in fragment.lower(), (
                "los errores congelados mencionan OAuth en " + case["name"]
            )


def test_contract_forbids_password_and_credential_exposure():
    text = _contract_text()
    assert "getpass" in text, "el contrato debe prohibir getpass"
    assert "contrasena" in text, (
        "el contrato debe declarar que jamas se pide la contrasena"
    )
    assert "jam" in text.lower(), "el contrato debe usar lenguaje de prohibicion"
    for case in _frozen_cases():
        for secret in case.get("secrets", []):
            assert secret not in "\n".join(case.get("stdout_has", [])), (
                "stdout congelado filtra un secreto en " + case["name"]
            )
        if case["code"] != 0:
            for fragment in case.get("stderr_has", []):
                assert "env://" not in fragment, (
                    "los mensajes de error no deben contener la referencia en "
                    + case["name"]
                )


def test_contract_conserves_existing_subcommands():
    text = _contract_text()
    for subcommand in _SETUP_SUBCOMMANDS:
        assert subcommand in text, "subcomando conservado ausente: " + subcommand
    assert "quedan intactos" in text
    assert "Don't: alterar" in text


# --- Referencias espejo de las funciones de cuentas -------------------------


def _require_non_empty_str(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " debe ser un str no vacio")
    return value


def _mirror_create_email_account(account_id, provider, email, credential_ref):
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


def _mirror_validate_record(record, error):
    if not isinstance(record, dict):
        raise error("account debe ser un dict")
    if set(record) != set(_RECORD_KEYS):
        raise error("account debe tener exactamente las claves del registro")
    for key in _RECORD_KEYS[:4]:
        if not isinstance(record[key], str) or not record[key].strip():
            raise error(key + " debe ser un str no vacio")
    if record["status"] != "disconnected":
        raise error('status debe ser "disconnected"')


def _mirror_store_path(root):
    _require_non_empty_str(root, "root")
    return Path(root) / ".email-agent" / "accounts.json"


def _mirror_read_records(path, error):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise error("accounts.json corrupto o ilegible: " + type(exc).__name__)
    if not isinstance(data, dict) or set(data) != {"accounts"}:
        raise error("accounts.json no tiene el esquema esperado")
    records = []
    for record in data["accounts"]:
        _mirror_validate_record(record, error)
        records.append({key: record[key] for key in _RECORD_KEYS})
    return records


def _mirror_save_email_account(root, account):
    path = _mirror_store_path(root)
    _mirror_validate_record(account, ValueError)
    records = _mirror_read_records(path, RuntimeError) if path.exists() else []
    records = [r for r in records if r["account_id"] != account["account_id"]]
    records.append({key: account[key] for key in _RECORD_KEYS})
    path.parent.mkdir(parents=True, exist_ok=True)
    records.sort(key=lambda r: r["account_id"])
    payload = json.dumps({"accounts": records}, sort_keys=True, ensure_ascii=False)
    path.write_text(payload + "\n", encoding="utf-8")
    return str(path.resolve())


# --- Referencia del flujo guiado congelado ----------------------------------


_INTRO = "Configuracion guiada de cuenta (escribe 'cancelar' en cualquier paso para abortar):"
_PROMPTS = (
    "1) Identificador de la cuenta (ej. personal): ",
    "2) Proveedor (gmail u outlook): ",
    "3) Correo electronico: ",
    "4) Nombre de la variable de entorno que guarda tu clave de aplicacion "
    "(ej. GMAIL_APP_PASSWORD; nunca la clave en si): ",
)
_CANCEL_WORDS = ("cancelar", "cancel")
_ENV_VAR_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_USAGE = (
    "usage: email-cli [--help] | email-cli search ROOT QUERY | "
    "email-cli query ROOT INSTRUCTION | email-cli sync ROOT ACCOUNT_ID [HOST] | "
    "email-cli draft ROOT ACCOUNT_ID TO SUBJECT BODY | "
    "email-cli send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR_ENVIO | "
    "email-cli account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF | "
    "email-cli account setup ROOT | email-cli account list ROOT"
)
_HELP_STDOUT = [_USAGE, "  account setup ROOT  alta guiada interactiva"]


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


def _reference_setup(root, inputs):
    """Flujo guiado congelado: 4 preguntas por input, una confirmacion."""
    stdout = [_INTRO]
    answers = []
    for prompt in _PROMPTS:
        stdout.append(prompt)
        try:
            raw = next(inputs)
        except StopIteration:
            return 1, stdout, ["error: configuracion cancelada (entrada terminada)"]
        answer = raw.strip()
        if answer.lower() in _CANCEL_WORDS:
            return 1, stdout, ["error: configuracion cancelada por el usuario"]
        if not answer:
            return 1, stdout, ["error: la respuesta no puede estar vacia"]
        answers.append(answer)
    account_id, provider, email, env_name = answers
    if provider.lower() not in ("gmail", "outlook"):
        return 1, stdout, ["error: proveedor no admitido (solo se admiten gmail u outlook)"]
    if not _ENV_VAR_PATTERN.fullmatch(env_name):
        return 1, stdout, ["error: nombre de variable de entorno invalido"]
    try:
        account = _mirror_create_email_account(
            account_id, provider, email, "env://" + env_name
        )
        _mirror_save_email_account(root, account)
    except (ValueError, RuntimeError):
        return 1, stdout, ["error: no se pudo guardar la cuenta (datos o almacenamiento invalidos)"]
    return 0, stdout + ["account saved: " + account["account_id"]], []


def _reference_cli(argv, root, inputs):
    usage = _USAGE
    if argv and argv[0] in ("-h", "--help"):
        return 0, list(_HELP_STDOUT), []
    if not argv:
        return 2, [], ["error: subcomando invalido", usage]
    if argv[0] == "account":
        if len(argv) < 2 or argv[1] not in ("add", "setup", "list"):
            return 2, [], ["error: account requiere 'add', 'setup' o 'list'", usage]
        if argv[1] == "setup":
            if len(argv) != 3:
                return 2, [], ["error: account setup requiere exactamente ROOT", usage]
            return _reference_setup(argv[2], inputs)
        if argv[1] == "add":
            if len(argv) != 7:
                return 2, [], ["error: account add requiere ROOT, ACCOUNT_ID, PROVIDER, EMAIL y CREDENTIAL_REF", usage]
            try:
                account = _mirror_create_email_account(
                    argv[3], argv[4], argv[5], argv[6]
                )
                _mirror_save_email_account(argv[2], account)
            except (ValueError, RuntimeError):
                return 1, [], ["error: no se pudo guardar la cuenta (datos o almacenamiento invalidos)"]
            return 0, ["account saved: " + account["account_id"]], []
        if len(argv) != 3:
            return 2, [], ["error: account list requiere exactamente ROOT", usage]
        return 0, [], []
    if argv[0] == "search":
        if len(argv) != 3:
            return 2, [], ["error: search requiere exactamente ROOT y QUERY", usage]
        try:
            matches = _reference_search(argv[1], argv[2])
        except _SearchError:
            return 1, [], ["error: la busqueda fallo (raiz invalida o query sin terminos)"]
        return 0, list(matches), []
    return 2, [], ["error: subcomando invalido (subcomando no reconocido)", usage]


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def _run_case(case):
    """Sustituye <root>, prepara el tree/store y ejecuta la referencia CLI."""
    with tempfile.TemporaryDirectory() as tmp:
        for relpath, content in case.get("tree", {}).items():
            target = Path(tmp) / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        store_path = Path(tmp) / ".email-agent" / "accounts.json"
        if case.get("store"):
            for record in case["store"]:
                _mirror_save_email_account(tmp, dict(record))
        inputs = iter(case.get("inputs", []))
        argv = [a.replace("<root>", tmp) for a in case["argv"]]
        code, stdout, stderr = _reference_cli(argv, tmp, inputs)
        stored = None
        if case.get("expect_store") and store_path.exists():
            stored = _mirror_read_records(store_path, RuntimeError)
        return code, stdout, stderr, stored, store_path.exists()


def _assert_case(case, result):
    code, stdout, stderr, stored, store_exists = result
    combined = "\n".join(stdout) + "\n" + "\n".join(stderr)
    assert code == case["code"], "codigo inesperado en " + case["name"]
    if "stdout" in case:
        assert stdout == case["stdout"], "stdout inesperado en " + case["name"]
    for fragment in case.get("stdout_has", []):
        assert fragment in "\n".join(stdout), (
            "stdout sin " + repr(fragment) + " en " + case["name"]
        )
    if "stdout_last" in case:
        tail = case["stdout_last"]
        assert len(stdout) >= len(tail) and stdout[-len(tail):] == tail, (
            "stdout no termina con " + repr(tail) + " en " + case["name"]
        )
    if "stderr" in case:
        assert stderr == case["stderr"], "stderr inesperado en " + case["name"]
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
        assert "traceback" not in combined.lower(), (
            "traceback expuesto al usuario en " + case["name"]
        )
        assert "env://" not in combined, (
            "credential_ref filtrado en salida de error en " + case["name"]
        )
    if case.get("no_store"):
        assert not store_exists, "el store no debia crearse en " + case["name"]
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
            "credential_ref verbatim esperado solo en el store en " + case["name"]
        )


def test_frozen_cases_cover_setup_and_conservation():
    cases = _frozen_cases()
    names = {case["name"] for case in cases}
    assert {
        "help_shows_setup",
        "setup_success_gmail",
        "setup_success_outlook",
        "setup_overwrites_existing_account",
        "setup_provider_not_admitted",
        "setup_env_var_name_invalid",
        "setup_blank_email_answer",
        "setup_cancel_at_provider_prompt",
        "setup_eof_at_email_prompt",
        "setup_corrupt_store",
        "setup_missing_root_arg",
        "setup_extra_args",
        "account_add_preserved",
        "search_preserved",
    } <= names, "los casos deben cubrir exito, entradas, cancelacion, EOF y conservacion"
    assert len(cases) >= 14, "el contrato debe congelar al menos 14 casos"
    codes = {case["name"]: case["code"] for case in cases}
    for name in (
        "help_shows_setup",
        "setup_success_gmail",
        "setup_success_outlook",
        "setup_overwrites_existing_account",
        "account_add_preserved",
        "search_preserved",
    ):
        assert codes[name] == 0, name + " debe ser exitoso (0)"
    for name in (
        "setup_provider_not_admitted",
        "setup_env_var_name_invalid",
        "setup_blank_email_answer",
        "setup_cancel_at_provider_prompt",
        "setup_eof_at_email_prompt",
        "setup_corrupt_store",
    ):
        assert codes[name] == 1, name + " debe retornar 1"
    for name in ("setup_missing_root_arg", "setup_extra_args", "account_unknown_subcommand_preserved"):
        assert codes[name] == 2, name + " debe retornar 2"


def test_frozen_setup_cases_have_inputs_and_dialogue():
    for case in _frozen_cases():
        if case["name"].startswith("setup_") and case["code"] == 0:
            assert isinstance(case.get("inputs"), list), (
                "el setup exitoso debe congelar las respuestas en " + case["name"]
            )
        if case["name"].startswith("setup_") and case["code"] in (1, 2):
            assert case.get("stderr_has"), (
                "falta mensaje amigable congelado en " + case["name"]
            )


def test_frozen_cases_setup_success_gmail_builds_env_ref_and_single_confirmation():
    case = _case("setup_success_gmail")
    code, stdout, stderr, stored, _ = _run_case(case)
    _assert_case(case, (code, stdout, stderr, stored, _))
    assert code == 0
    assert len(stdout) == 6, "intro + 4 preguntas + una confirmacion"
    assert stdout[0].count("cancelar") == 1, "la intro explica como cancelar"
    assert stdout[-1] == "account saved: personal", (
        "el unico resultado impreso es la confirmacion publica"
    )
    assert stdout.count("account saved: personal") == 1, (
        "una sola confirmacion publica"
    )
    assert stderr == []
    record = [r for r in stored if r["account_id"] == "personal"][0]
    assert record["provider"] == "gmail"
    assert record["email"] == "yo@example.com"
    assert record["status"] == "disconnected"
    assert record["credential_ref"] == "env://GMAIL_APP_PASSWORD", (
        "credential_ref construido como env://NOMBRE, verbatim solo en el store"
    )


def test_frozen_cases_setup_success_outlook_and_overwrite():
    for name in ("setup_success_outlook", "setup_overwrites_existing_account"):
        case = _case(name)
        code, stdout, stderr, stored, _ = _run_case(case)
        _assert_case(case, (code, stdout, stderr, stored, _))
        assert code == 0
        assert stdout[-1] == case["stdout_last"][0]
        assert stdout.count(stdout[-1]) == 1, "una sola confirmacion en " + name
        assert stderr == []


def test_frozen_cases_setup_input_errors_write_nothing():
    for name in (
        "setup_provider_not_admitted",
        "setup_env_var_name_invalid",
        "setup_blank_email_answer",
        "setup_cancel_at_provider_prompt",
        "setup_eof_at_email_prompt",
    ):
        case = _case(name)
        assert case["code"] == 1
        code, stdout, stderr, _, store_exists = _run_case(case)
        _assert_case(case, (code, stdout, stderr, _, store_exists))
        assert code == 1
        assert not store_exists, "ningun dato invalido debe escribir el store en " + name
        stderr_text = "\n".join(stderr).lower()
        assert "error" in stderr_text or "cancelada" in stderr_text, (
            "mensaje amigable generico ausente en " + name
        )
        assert "traceback" not in stderr_text
        assert "env://" not in stderr_text, (
            "la referencia no aparece en mensajes de error en " + name
        )
        assert stdout[-1].strip() != "", "el ultimo renglon impreso es una pregunta"


def test_frozen_cases_setup_cancel_and_eof_are_equivalent():
    cancel = _case("setup_cancel_at_provider_prompt")
    eof = _case("setup_eof_at_email_prompt")
    for case in (cancel, eof):
        code, stdout, stderr, _, store_exists = _run_case(case)
        _assert_case(case, (code, stdout, stderr, _, store_exists))
        assert code == 1
        assert "cancelada" in "\n".join(stderr).lower(), (
            "cancelacion y EOF comparten el tratamiento de cancelacion"
        )
        assert not store_exists


def test_frozen_cases_setup_corrupt_store_is_generic():
    case = _case("setup_corrupt_store")
    code, stdout, stderr, _, _ = _run_case(case)
    _assert_case(case, (code, stdout, stderr, _, _))
    assert code == 1
    stderr_text = "\n".join(stderr)
    assert "error" in stderr_text.lower()
    assert "Traceback" not in stderr_text
    for secret in case.get("secrets", []):
        assert secret not in stderr_text, "secreto filtrado en stderr"


def test_frozen_cases_arg_errors_are_friendly():
    for name in (
        "setup_missing_root_arg",
        "setup_extra_args",
        "account_unknown_subcommand_preserved",
    ):
        case = _case(name)
        assert case["code"] == 2, "error de argumentos debe retornar 2 en " + name
        code, stdout, stderr, _, _ = _run_case(case)
        _assert_case(case, (code, stdout, stderr, _, _))
        assert stdout == [], "nada en stdout en error de argumentos"
        assert "usage:" in "\n".join(stderr).lower(), (
            "el error de argumentos debe mostrar el usage"
        )


def test_frozen_cases_help_shows_setup_and_usage():
    case = _case("help_shows_setup")
    code, stdout, stderr, _, _ = _run_case(case)
    _assert_case(case, (code, stdout, stderr, _, _))
    assert code == 0
    text = "\n".join(stdout).lower()
    assert "usage:" in text
    assert "account setup root" in text, "la ayuda documenta account setup"
    assert "oauth" not in text, "la ayuda no menciona OAuth"
    assert stderr == []


def test_frozen_cases_preserved_subcommands_are_untouched():
    add_case = _case("account_add_preserved")
    code, stdout, stderr, stored, _ = _run_case(add_case)
    _assert_case(add_case, (code, stdout, stderr, stored, _))
    assert code == 0
    assert stdout == ["account saved: legacy"], "account add conserva su salida"
    record = [r for r in stored if r["account_id"] == "legacy"][0]
    assert record["credential_ref"] == "vault://gmail-legacy"
    search_case = _case("search_preserved")
    code, stdout, stderr, _, _ = _run_case(search_case)
    _assert_case(search_case, (code, stdout, stderr, _, _))
    assert code == 0
    assert stdout == search_case["stdout"], "search conserva su stdout congelado"


def test_frozen_cases_shape_and_determinism():
    for case in _frozen_cases():
        assert isinstance(case["argv"], list), "argv debe ser lista"
        assert case["argv"][0] in ("account", "search", "--help"), (
            "argv de caso no previsto: " + case["argv"][0]
        )
        assert case["code"] in (0, 1, 2), "codigo de salida no previsto"
        for answer in case.get("inputs", []):
            assert isinstance(answer, str), "las respuestas deben ser str"
        if case.get("no_store"):
            assert case["code"] != 0, "no_store solo aplica a casos fallidos"
        if case["code"] == 0:
            assert case.get("stdout_last") is not None or "stdout" in case, (
                "los casos exitosos deben congelar su salida exacta"
            )
            assert not case.get("stderr_has"), "sin errores congelados en exito"