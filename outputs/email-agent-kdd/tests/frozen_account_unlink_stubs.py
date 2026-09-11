"""Pruebas frozen offline de la desvinculacion transaccional (Sprint 10).

Importan el codigo REAL (`src.email.unlink`, `src.email.cli`) y corren sin
red y sin tocar almacenes nativos: los unicos puntos de inyeccion son
`credential`/`servers` de `unlink_email_account`, los `backend=`/`runner=`
de los modulos de plataforma y los nombres de `src.email.credentials` que
`delete_stored_credential` despacha. Cubre las tres plataformas
(wincred://, keychain://, secretservice://) mas `env://` (no persiste),
confirmacion incorrecta, secreto ausente, errores con rollback y
preservacion byte a byte de los correos descargados.
"""

import ctypes
import json
from pathlib import Path
import socket
import tempfile

import pytest

from src.email import cli, credentials, keychain, secretservice, wincred
from src.email.account_store import load_email_accounts, save_email_account
from src.email.mail_server_store import (
    load_mail_server_config,
    remove_mail_server_config,
    store_mail_server_config,
)
from src.email.unlink import unlink_email_account

_RECORD_KEYS = ("account_id", "provider", "email", "credential_ref", "status")
_RECORD = {
    "account_id": "personal",
    "provider": "gmail",
    "email": "yo@example.com",
    "status": "disconnected",
}
_CONFIG = {
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
}


@pytest.fixture(autouse=True)
def _sin_red_ni_secretos(monkeypatch):
    """Prohibir sockets y cualquier resolucion de secretos durante las pruebas."""

    def _prohibido(*args, **kwargs):
        raise AssertionError("la prueba no debe abrir sockets")

    monkeypatch.setattr(socket.socket, "__new__", _prohibido, raising=False)

    def _resolucion_prohibida(*args, **kwargs):
        raise AssertionError("la desvinculacion no debe resolver el secreto")

    monkeypatch.setattr(credentials, "resolve_credential", _resolucion_prohibida)


def _account_with(ref):
    return {**_RECORD, "credential_ref": ref}


def _prepare(root, ref, with_servers=True):
    save_email_account(str(root), _account_with(ref))
    if with_servers:
        store_mail_server_config(str(root), _RECORD["account_id"], dict(_CONFIG))
    messages = {
        "mail/inbox/nota.md": b"correo descargado \xff\x01 que sobrevive",
        "mail/archivo/otro.md": "otro correo descargado".encode("utf-8"),
    }
    for relpath, content in messages.items():
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return messages


def _messages_intact(root, messages):
    for relpath, content in messages.items():
        assert (root / relpath).read_bytes() == content, (
            "el correo " + relpath + " no sobrevivio a la desvinculacion"
        )


class _StubCred:
    """Doble de `credential`: registra refs borradas o lanza si `fail`."""

    def __init__(self, fail=False):
        self.deleted = []
        self.fail = fail

    def __call__(self, ref):
        if self.fail:
            raise RuntimeError("fallo del almacen nativo")
        self.deleted.append(ref)


class _StubServers:
    """Doble de `servers`: registra y borra en el store real o lanza."""

    def __init__(self, fail=False):
        self.deleted = []
        self.fail = fail

    def __call__(self, root, account_id):
        if self.fail:
            raise RuntimeError("fallo del almacen local")
        self.deleted.append(account_id)
        remove_mail_server_config(str(root), account_id)


# --- Unlink real con dobles: tres plataformas + env:// -----------------------


@pytest.mark.parametrize(
    "ref",
    [
        "wincred://gmail-personal",
        "keychain://gmail-personal",
        "secretservice://gmail-personal",
    ],
)
def test_unlink_deletes_secret_once_and_preserves_messages(tmp_path, ref):
    messages = _prepare(tmp_path, ref)
    cred, servers = _StubCred(), _StubServers()
    result = unlink_email_account(str(tmp_path), "personal", credential=cred, servers=servers)
    assert result == {"account_id": "personal", "email": "yo@example.com", "status": "unlinked"}
    assert set(result) == {"account_id", "email", "status"}, (
        "el resultado jamas incluye credential_ref ni secretos"
    )
    assert cred.deleted == [ref], "el secreto de la plataforma se borra una vez"
    assert servers.deleted == ["personal"]
    assert load_email_accounts(str(tmp_path)) == [], "la cuenta queda desvinculada"
    assert load_mail_server_config(str(tmp_path), "personal") is None
    _messages_intact(tmp_path, messages)


def test_unlink_env_ref_persists_nothing(tmp_path):
    """env:// no persiste: el unlink usa el delete real y no toca backends."""
    messages = _prepare(tmp_path, "env://GMAIL_APP_PASSWORD")
    result = unlink_email_account(str(tmp_path), "personal")
    assert result == {"account_id": "personal", "email": "yo@example.com", "status": "unlinked"}
    assert load_email_accounts(str(tmp_path)) == []
    _messages_intact(tmp_path, messages)


def test_unlink_deletes_secret_after_local_cleanup(tmp_path):
    """Orden congelado: primero servers y cuentas, despues el secreto."""
    _prepare(tmp_path, "wincred://gmail-personal")
    events = []

    def cred(ref):
        events.append("credential")

    def servers(root, account_id):
        events.append("servers")

    unlink_email_account(str(tmp_path), "personal", credential=cred, servers=servers)
    assert events == ["servers", "credential"], (
        "el borrado del secreto nativo va al final de la transaccion"
    )


def test_unlink_absent_account_and_invalid_ids(tmp_path):
    save_email_account(str(tmp_path), _account_with("env://KEY"))
    with pytest.raises(LookupError):
        unlink_email_account(str(tmp_path), "fantasma")
    with pytest.raises(ValueError):
        unlink_email_account(str(tmp_path), "   ")
    with pytest.raises(ValueError):
        unlink_email_account(str(tmp_path), 123)
    assert load_email_accounts(str(tmp_path)) == [_account_with("env://KEY")], (
        "un fallo de pre-lectura no muta nada"
    )


# --- CLI: confirmacion literal antes de leer disco ---------------------------


def _cli(argv):
    return cli._account_remove(argv)


def test_cli_wrong_confirmation_changes_nothing(tmp_path, monkeypatch, capsys):
    _prepare(tmp_path, "env://GMAIL_APP_PASSWORD")
    calls = []

    def stub(root, account_id):
        calls.append(account_id)
        return {"account_id": account_id, "email": "x", "status": "unlinked"}

    monkeypatch.setattr(cli, "unlink_email_account", stub)
    for argv in (
        ["account", "remove", str(tmp_path), "personal", "DESVINCULAR"],
        ["account", "remove", str(tmp_path), "personal", "CONFIRMAR", "BORRAR"],
        ["account", "remove", str(tmp_path), "personal", "confirmar desvincular"],
    ):
        code = _cli(argv)
        assert code == 1, "confirmacion incorrecta debe retornar 1"
        captured = capsys.readouterr()
        assert captured.out == "", "nada en stdout con confirmacion incorrecta"
        assert "confirmacion explicita requerida para desvincular" in captured.err
        assert "env://" not in captured.err and "credential_ref" not in captured.err
    assert calls == [], "la desvinculacion no se invoca sin confirmacion exacta"
    assert len(load_email_accounts(str(tmp_path))) == 1, "la cuenta sigue intacta"
    assert load_mail_server_config(str(tmp_path), "personal") == dict(_CONFIG)


def test_cli_missing_args_show_usage(tmp_path):
    assert _cli(["account", "remove", str(tmp_path)]) == 2
    assert _cli(["account", "remove"]) == 2


def test_cli_unknown_account_is_generic(tmp_path, capsys):
    _prepare(tmp_path, "env://GMAIL_APP_PASSWORD")
    code = _cli(["account", "remove", str(tmp_path), "fantasma", "CONFIRMAR", "DESVINCULAR"])
    captured = capsys.readouterr()
    assert code == 1 and captured.out == ""
    assert "cuenta no encontrada" in captured.err
    assert "env://" not in captured.err
    assert len(load_email_accounts(str(tmp_path))) == 1


def test_cli_success_prints_unlinked_without_credential_ref(tmp_path, capsys):
    _prepare(tmp_path, "env://GMAIL_APP_PASSWORD")
    code = _cli(
        ["account", "remove", str(tmp_path), "personal", "CONFIRMAR", "DESVINCULAR"]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == '{"account_id": "personal", "status": "unlinked"}'
    assert "credential_ref" not in captured.out and "env://" not in captured.out
    assert captured.err == ""
    assert load_email_accounts(str(tmp_path)) == []


# --- Secreto ausente: cada plataforma lo trata como ya desvinculado ---------


def test_wincred_delete_absent_is_ok():
    class _FakeAdvapi32:
        def CredDeleteW(self, *args):
            ctypes.set_last_error(1168)  # ERROR_NOT_FOUND
            return 0

    backend = object.__new__(wincred._WindowsCredentialBackend)
    backend._advapi32 = _FakeAdvapi32()
    wincred.delete_windows_credential("wincred://gmail-personal", backend=backend)


def test_keychain_delete_absent_code_44_is_ok():
    runner = lambda argv, stdin=None: (44, b"", b"")  # 44 = item not found
    backend = object.__new__(keychain._KeychainBackend)
    backend._run = runner
    backend.delete("gmail-personal")


def test_secretservice_delete_absent_is_ok():
    runner = lambda argv, stdin=None: (0, b"", b"")
    secretservice.delete_secretservice_secret(
        "secretservice://gmail-personal", runner=runner
    )


def test_delete_stored_credential_treats_absent_as_unlinked(monkeypatch):
    calls = []

    def _ausente_ok(ref, **kwargs):
        calls.append(ref)

    monkeypatch.setattr(credentials, "delete_windows_credential", _ausente_ok)
    monkeypatch.setattr(credentials, "delete_keychain_secret", _ausente_ok)
    monkeypatch.setattr(credentials, "delete_secretservice_secret", _ausente_ok)
    for ref in (
        "wincred://gmail-personal",
        "keychain://gmail-personal",
        "secretservice://gmail-personal",
        "env://GMAIL_APP_PASSWORD",
    ):
        credentials.delete_stored_credential(ref)  # no levanta
    assert calls == [
        "wincred://gmail-personal",
        "keychain://gmail-personal",
        "secretservice://gmail-personal",
    ], "env:// no persiste nada: no se despacha a ningun backend"


# --- Errores y rollback best-effort ------------------------------------------


def test_servers_failure_propagates_and_mutates_nothing(tmp_path):
    _prepare(tmp_path, "wincred://gmail-personal")
    accounts_before = (tmp_path / ".email-agent" / "accounts.json").read_bytes()
    servers_before = (tmp_path / ".email-agent" / "mail-servers.json").read_bytes()
    with pytest.raises(RuntimeError, match="fallo del almacen local"):
        unlink_email_account(
            str(tmp_path), "personal", credential=_StubCred(), servers=_StubServers(fail=True)
        )
    assert (tmp_path / ".email-agent" / "accounts.json").read_bytes() == accounts_before
    assert (tmp_path / ".email-agent" / "mail-servers.json").read_bytes() == servers_before


def test_credential_failure_restores_account_and_servers(tmp_path):
    _prepare(tmp_path, "secretservice://gmail-personal")
    accounts_before = (tmp_path / ".email-agent" / "accounts.json").read_bytes()
    servers_before = (tmp_path / ".email-agent" / "mail-servers.json").read_bytes()
    with pytest.raises(RuntimeError, match="fallo del almacen nativo") as excinfo:
        unlink_email_account(
            str(tmp_path), "personal", credential=_StubCred(fail=True), servers=_StubServers()
        )
    assert "fallo del almacen nativo" in str(excinfo.value), "se propaga el error ORIGINAL"
    assert (tmp_path / ".email-agent" / "accounts.json").read_bytes() == accounts_before, (
        "la cuenta se restauro tras el rollback"
    )
    assert (tmp_path / ".email-agent" / "mail-servers.json").read_bytes() == servers_before, (
        "la config de servidores se restauro tras el rollback"
    )


def test_rollback_failure_does_not_mask_original_error(tmp_path, monkeypatch):
    _prepare(tmp_path, "wincred://gmail-personal", with_servers=False)
    cred, servers = _StubCred(fail=True), _StubServers()

    def _save_fallado(root, account):
        raise OSError("rollback roto")

    monkeypatch.setattr("src.email.unlink.save_email_account", _save_fallado)
    with pytest.raises(RuntimeError, match="fallo del almacen nativo"):
        unlink_email_account(str(tmp_path), "personal", credential=cred, servers=servers)


def test_unlink_without_servers_store_still_unlinks(tmp_path):
    _prepare(tmp_path, "keychain://gmail-personal", with_servers=False)
    result = unlink_email_account(
        str(tmp_path), "personal", credential=_StubCred(), servers=_StubServers()
    )
    assert result["status"] == "unlinked"
    assert (tmp_path / ".email-agent" / "mail-servers.json").exists() is False