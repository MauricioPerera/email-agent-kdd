"""Tests congelados del contrato cli_account_remove.

Oracle independiente: no importa src.email.unlink ni cli.py. Verifica la
estructura del contrato (frontmatter, secciones, budgets, prohibiciones) y
re-deriva los casos congelados con una implementacion de referencia propia
de la transaccion de desvinculacion, espejo de account_store /
mail_server_store con stubs de borrado de secreto en memoria.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-account-remove.md"
)

_RECORD_KEYS = ("account_id", "provider", "email", "credential_ref", "status")
_CONFIRMATION = ("CONFIRMAR", "DESVINCULAR")


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(r"```" + label + r"\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_cases():
    return json.loads(_fenced_block(_contract_text(), "frozen-cases"))


def test_contract_frontmatter_and_budgets():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: cli_account_remove" in frontmatter
    assert (
        'signature: "def unlink_email_account(root: str, account_id: str, '
        'credential=None, servers=None) -> dict"' in frontmatter
    )
    assert "target: src/email/unlink.py + src/email/cli.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "forbids: [eval, exec, subprocess, network_access, getpass]" in frontmatter
    assert "tests:" in frontmatter and "frozen_cli_account_remove" in frontmatter
    assert "frozen_account_unlink_stubs" in frontmatter


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


def test_contract_freezes_transactional_semantics():
    text = _contract_text()
    assert "delete_stored_credential" in text, (
        "el borrado del secreto debe delegar en delete_stored_credential"
    )
    assert "resolve_credential" in text, (
        "el contrato debe congelar que no se resuelve el secreto"
    )
    assert "credential_ref" in text and 'jam' in text.lower(), (
        "el contrato debe congelar la salida sin credential_ref"
    )
    assert "best-effort" in text and "error ORIGINAL" in text, (
        "el contrato debe congelar el rollback best-effort re-lanzando el error"
    )
    assert "correos descargados" in text and "byte a byte" in text, (
        "el contrato debe congelar la preservacion de los correos"
    )
    assert "CONFIRMAR DESVINCULAR" in text, (
        "la confirmacion literal debe estar congelada en el contrato"
    )
    assert "remove_email_account(root, account_id) -> dict" in text
    assert "load_mail_server_config(root, account_id) -> dict|None" in text
    assert "no se reimplementa" in text or "no reimplementa" in text


def test_contract_forbids_secret_exposure_and_platform_coupling():
    text = _contract_text()
    assert "al reves" in text, "el orden transaccional debe estar congelado"
    assert "ausente no es un error" in text, (
        "el secreto ausente debe estar congelado como exito"
    )
    lowered = text.lower()
    for platform in ("wincred", "keychain", "secretservice"):
        assert platform in lowered, "plataforma no cubierta: " + platform
    for case in _frozen_cases():
        for fragment in case.get("stdout", []) + case.get("stderr_has", []):
            assert "://" not in fragment, (
                "la salida congelada filtra una referencia en " + case["name"]
            )
            assert "password" not in fragment.lower()


# --- Referencias espejo de los stores ----------------------------------------


def _mirror_read_accounts(root):
    path = Path(root) / ".email-agent" / "accounts.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and set(data) == {"accounts"}
    for record in data["accounts"]:
        assert set(record) == set(_RECORD_KEYS)
    return [dict(record) for record in data["accounts"]]


def _mirror_write_accounts(root, records):
    path = Path(root) / ".email-agent" / "accounts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"accounts": records}, sort_keys=True, ensure_ascii=False)
    path.write_text(payload + "\n", encoding="utf-8")


def _mirror_read_servers(root):
    path = Path(root) / ".email-agent" / "mail-servers.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("servers", {})


def _mirror_remove_mail_server(root, account_id):
    path = Path(root) / ".email-agent" / "mail-servers.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"servers": {}}
    if account_id in data["servers"]:
        del data["servers"][account_id]
        path.write_text(
            json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
        )


def _mirror_store_mail_server(root, account_id, config):
    path = Path(root) / ".email-agent" / "mail-servers.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"servers": {}}
    data["servers"][account_id] = dict(config)
    path.write_text(
        json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class _RecordingSecretStub:
    """Stub del borrado de secreto: registra refs o lanza si `fail`."""

    def __init__(self, fail=False):
        self.deleted = []
        self.fail = fail

    def __call__(self, ref):
        if self.fail:
            raise RuntimeError("fallo del almacen nativo")
        self.deleted.append(ref)


class _ServersStub:
    """Stub de `remove_mail_server_config`: registra y borra en espejo."""

    def __init__(self, fail=False, root=None):
        self.deleted = []
        self.fail = fail
        self._root = root

    def __call__(self, root, account_id):
        if self.fail:
            raise RuntimeError("fallo del almacen local")
        self.deleted.append(account_id)
        _mirror_remove_mail_server(root, account_id)


# --- Referencia de la transaccion congelada ----------------------------------


def _reference_unlink(root, account_id, credential, servers):
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id debe ser un str no vacio")
    found = None
    for record in _mirror_read_accounts(root):
        if record["account_id"] == account_id:
            found = record
    if found is None:
        raise LookupError("cuenta no encontrada")
    path_servers = _mirror_read_servers(root)
    snapshot = path_servers.get(account_id) if path_servers else None
    try:
        servers(root, account_id)
        remaining = [r for r in _mirror_read_accounts(root) if r["account_id"] != account_id]
        _mirror_write_accounts(root, remaining)
    except (ValueError, RuntimeError, OSError):
        if snapshot is not None:
            _mirror_store_mail_server(root, account_id, snapshot)
        raise
    try:
        credential(found["credential_ref"])
    except (ValueError, RuntimeError, OSError):
        try:
            _mirror_write_accounts(root, [dict(found)])
            if snapshot is not None:
                _mirror_store_mail_server(root, account_id, snapshot)
        except (ValueError, RuntimeError, OSError):
            pass
        raise
    return {
        "account_id": found["account_id"],
        "email": found["email"],
        "status": "unlinked",
    }


def _reference_cli(argv, root, credential, servers):
    if len(argv) < 5:
        return 2, [], ["error: account remove requiere ROOT, ACCOUNT_ID y confirmacion", "usage:"]
    if " ".join(argv[4:]) != " ".join(_CONFIRMATION):
        return 1, [], ["error: confirmacion explicita requerida para desvincular"]
    try:
        removed = _reference_unlink(argv[2], argv[3], credential, servers)
    except LookupError:
        return 1, [], ["error: cuenta no encontrada"]
    except (ValueError, RuntimeError, OSError):
        return 1, [], ["error: no se pudo desvincular la cuenta"]
    return 0, [json.dumps({"account_id": removed["account_id"], "status": "unlinked"}, sort_keys=True)], []


def _run_case(case):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        accounts = root / ".email-agent" / "accounts.json"
        servers_file = root / ".email-agent" / "mail-servers.json"
        for record in case.get("store", []):
            existing = _mirror_read_accounts(root)
            _mirror_write_accounts(root, existing + [dict(record)])
        if case.get("servers_store"):
            _mirror_store_mail_server(root, "personal", case["servers_store"])
        messages = {}
        for relpath, content in case.get("messages", {}).items():
            target = root / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode("utf-8"))
            messages[relpath] = target.read_bytes()
        stub = _RecordingSecretStub(fail=case.get("fail") == "credential")
        servers = _ServersStub(fail=case.get("fail") == "servers", root=root)
        argv = [a.replace("<root>", tmp) for a in case["argv"]]
        code, stdout, stderr = _reference_cli(argv, root, stub, servers)
        stored = _mirror_read_accounts(root) if accounts.exists() else None
        servers_after = _mirror_read_servers(root)
        for relpath, content in messages.items():
            assert (root / relpath).read_bytes() == content, (
                "el correo " + relpath + " no sobrevivio en " + case["name"]
            )
        return code, stdout, stderr, stored, servers_after, stub.deleted, servers.deleted


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


def _assert_case(case, result):
    code, stdout, stderr, stored, servers_after, secret_deleted, servers_deleted = result
    combined = "\n".join(stdout) + "\n" + "\n".join(stderr)
    assert code == case["code"], "codigo inesperado en " + case["name"]
    if "stdout" in case:
        assert stdout == case["stdout"], "stdout inesperado en " + case["name"]
    for fragment in case.get("stderr_has", []):
        assert fragment in "\n".join(stderr), (
            "stderr sin " + repr(fragment) + " en " + case["name"]
        )
    for ref in secret_deleted:
        assert ref not in combined, (
            "referencia de secreto filtrada en la salida de " + case["name"]
        )
    if case.get("no_store_write"):
        expected_accounts = [dict(r) for r in case.get("store", [])]
        assert stored == expected_accounts or (stored is None and not expected_accounts), (
            "accounts.json cambio cuando no debia en " + case["name"]
        )
        expected_servers = case.get("servers_store")
        servers_map = servers_after or {}
        if expected_servers:
            assert servers_map.get("personal") == expected_servers, (
                "mail-servers.json cambio cuando no debia en " + case["name"]
            )
    if "secret_deleted" in case:
        assert case["secret_deleted"] in secret_deleted, (
            "el secreto no se borro al final en " + case["name"]
        )
    if "secret_not_deleted" in case:
        assert case["secret_not_deleted"] not in secret_deleted, (
            "el secreto se borro cuando debia conservarse en " + case["name"]
        )
    expected = case.get("expect_store")
    if expected is not None:
        assert stored == [dict(r) for r in expected], (
            "accounts.json no quedo como se esperaba en " + case["name"]
        )


def test_frozen_cases_cover_confirmation_errors_rollback_and_messages():
    names = {case["name"] for case in _frozen_cases()}
    assert {
        "remove_success_unlinks_and_keeps_messages",
        "remove_wrong_confirmation_changes_nothing",
        "remove_missing_confirmation_changes_nothing",
        "remove_unknown_account",
        "remove_storage_failure_rolls_back",
        "remove_secret_failure_rolls_back_and_keeps_secret",
    } <= names, "los casos deben cubrir confirmacion, errores, rollback y correos"
    assert len(_frozen_cases()) >= 6, "el contrato debe congelar al menos 6 casos"
    codes = {case["name"]: case["code"] for case in _frozen_cases()}
    assert codes["remove_success_unlinks_and_keeps_messages"] == 0
    for name in (
        "remove_wrong_confirmation_changes_nothing",
        "remove_unknown_account",
        "remove_storage_failure_rolls_back",
        "remove_secret_failure_rolls_back_and_keeps_secret",
    ):
        assert codes[name] == 1, name + " debe retornar 1"
    assert codes["remove_missing_confirmation_changes_nothing"] == 2


def test_frozen_success_deletes_secret_last_and_keeps_messages():
    case = _case("remove_success_unlinks_and_keeps_messages")
    result = _run_case(case)
    _assert_case(case, result)
    code, stdout, stderr, stored, servers_after, secret_deleted, servers_deleted = result
    assert code == 0 and stderr == []
    assert secret_deleted == ["wincred://gmail-personal"], (
        "el secreto se borra una vez, al final de la transaccion"
    )
    assert servers_deleted == ["personal"], "la config de servidores se limpia"
    assert stored == [], "el registro se quito de accounts.json"
    assert servers_after == {}, "mail-servers.json queda sin la cuenta"
    assert stdout == ['{"account_id": "personal", "status": "unlinked"}'], (
        "la salida solo incluye account_id y status"
    )


def test_frozen_wrong_and_missing_confirmation_change_nothing():
    for name in (
        "remove_wrong_confirmation_changes_nothing",
        "remove_missing_confirmation_changes_nothing",
    ):
        case = _case(name)
        result = _run_case(case)
        _assert_case(case, result)
        _, stdout, stderr, _, _, secret_deleted, _ = result
        assert stdout == [], "nada en stdout con confirmacion incorrecta en " + name
        assert secret_deleted == [], (
            "ningun secreto se borra con confirmacion incorrecta en " + name
        )
        assert "traceback" not in "\n".join(stderr).lower()


def test_frozen_unknown_account_is_generic():
    case = _case("remove_unknown_account")
    result = _run_case(case)
    _assert_case(case, result)
    code, stdout, stderr, stored, _, secret_deleted, _ = result
    assert code == 1 and stdout == []
    assert "cuenta no encontrada" in "\n".join(stderr)
    assert len(stored) == 1, "la cuenta existente no debe verse afectada"
    assert secret_deleted == [], "ningun secreto se borra si la cuenta falta"


def test_frozen_storage_failure_rolls_back_servers():
    case = _case("remove_storage_failure_rolls_back")
    result = _run_case(case)
    _assert_case(case, result)
    code, _, stderr, stored, servers_after, secret_deleted, _ = result
    assert code == 1
    assert "no se pudo desvincular la cuenta" in "\n".join(stderr)
    assert "traceback" not in "\n".join(stderr).lower()
    assert secret_deleted == [], "el secreto no se toca si falla lo local"
    assert stored is not None and len(stored) == 1, "la cuenta sigue en accounts.json"
    assert (servers_after or {}).get("personal") == case["servers_store"], (
        "mail-servers.json se restauro al snapshot"
    )


def test_frozen_secret_failure_restores_account_and_servers():
    case = _case("remove_secret_failure_rolls_back_and_keeps_secret")
    result = _run_case(case)
    _assert_case(case, result)
    code, _, stderr, stored, servers_after, secret_deleted, _ = result
    assert code == 1
    assert "no se pudo desvincular la cuenta" in "\n".join(stderr)
    assert "traceback" not in "\n".join(stderr).lower()
    assert secret_deleted == [], "el borrado del secreto fallo: nada se elimino"
    assert stored == [dict(r) for r in case["expect_store"]], (
        "la cuenta se restauro en accounts.json tras el rollback"
    )
    assert (servers_after or {}).get("personal") == case["servers_store"], (
        "la config de servidores se restauro tras el rollback"
    )


def test_frozen_cases_shape_and_determinism():
    for case in _frozen_cases():
        assert isinstance(case["argv"], list), "argv debe ser lista"
        assert case["argv"][:2] == ["account", "remove"], "caso fuera del subcomando"
        assert case["code"] in (0, 1, 2), "codigo de salida no previsto"
        if case["code"] == 0:
            assert case.get("stdout"), "los casos exitosos congelan su stdout"
            assert not case.get("stderr_has"), "sin errores congelados en exito"
            assert case.get("secret_deleted"), "el exito borra el secreto al final"
        if case.get("fail"):
            assert case["fail"] in ("servers", "credential"), "fallo no previsto"
            assert case["code"] != 0, "el fallo inyectado debe fracasar el caso"