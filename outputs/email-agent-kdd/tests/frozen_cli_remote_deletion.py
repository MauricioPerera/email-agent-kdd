# frozen_cli_remote_deletion.py — Tests de dispatch de los comandos remotos
# (`message remote-delete` / `remote-restore` / `remote-purge`) sobre
# src/email/cli.py con un ImapDeletionProvider FALSO inyectado por monkeypatch.
# Sin red, sin credenciales reales, sin conexiones IMAP: el provider es un
# fake en memoria que registra las llamadas y devuelve un recibo.
#
# Verifica:
# - dispatch y orden exacto de argumentos hacia el provider
#   (soft_delete(account, config, uid, trash) / restore(account, config,
#   trash, uid, original) / permanent_delete(account, config, mailbox, uid,
#   confirmacion)).
# - la cuenta guardada y su credencial se resuelven con los helpers del store
#   (account_store + credentials); sin passwords por argv ni secretos en
#   stdout/stderr.
# - host/puerto guardados en mail-servers.json tienen prioridad; si no hay,
#   se usa el host por defecto del proveedor (gmail/outlook).
# - remote-purge exige la frase literal CONFIRMAR BORRADO PERMANENTE y no
#   toca el provider sin ella.
# - codigos coherentes: 0 exito (una linea JSON), 1 fallo de operacion,
#   2 error de argumentos (aridad, UID invalido).

import json

import pytest

from src.email import cli as cli_mod
from src.email.account import create_email_account
from src.email.account_store import save_email_account
from src.email.mail_server_store import store_mail_server_config

PURGE_PHRASE = "CONFIRMAR BORRADO PERMANENTE"
SECRETO = "SECRETO-ORACLE-FKE-NO-REAL"


def _run(argv):
    """Dispatch cases use an explicit generation; missing-generation tests are separate."""
    if len(argv) > 1 and argv[1].startswith('remote-'):
        argv = [*argv, '--uidvalidity', '123']
    return cli_mod.cli_main(argv)


class _FakeProvider:
    """ImapDeletionProvider falso: registra llamadas, nunca abre sockets."""

    def __init__(self):
        self.calls = []
        self.receipt = {"action": "fake", "copied": True}
        self.error = None

    def _result(self, op):
        if isinstance(self.error, Exception):
            raise self.error
        return dict(self.receipt, action=op)

    def soft_delete(self, account, config, uid, trash_mailbox):
        assert config['uidvalidity'] == 123
        self.calls.append(
            ("soft_delete", account["account_id"], dict(config), uid, trash_mailbox)
        )
        return self._result("soft_delete")

    def restore(self, account, config, trash_mailbox, uid, original_mailbox):
        assert config['uidvalidity'] == 123
        self.calls.append(
            (
                "restore",
                account["account_id"],
                dict(config),
                uid,
                trash_mailbox,
                original_mailbox,
            )
        )
        return self._result("restore")

    def permanent_delete(self, account, config, mailbox, uid, confirmation):
        assert config['uidvalidity'] == 123
        self.calls.append(
            (
                "permanent_delete",
                account["account_id"],
                dict(config),
                mailbox,
                uid,
                confirmation,
            )
        )
        return self._result("permanent_delete")


def _setup_account(monkeypatch, tmp_path, with_servers=True, provider="gmail"):
    """Cuenta guardada + credencial env:// + (opcional) servidores guardados."""
    root = str(tmp_path)
    account = create_email_account("personal", provider, "yo@example.test", "env://TEST_REMOTE_PW")
    save_email_account(root, account)
    if with_servers:
        store_mail_server_config(
            root,
            "personal",
            {
                "imap_host": "imap.saved.test",
                "imap_port": 1143,
                "smtp_host": "smtp.saved.test",
                "smtp_port": 2587,
            },
        )
    monkeypatch.setenv("TEST_REMOTE_PW", SECRETO)
    fake = _FakeProvider()
    monkeypatch.setattr(cli_mod, "ImapDeletionProvider", lambda: fake)
    return root, fake


def _output(capsys):
    captured = capsys.readouterr()
    return captured.out, captured.err


def test_remote_delete_dispatcha_con_orden_exacto_y_host_guardado(
    monkeypatch, tmp_path, capsys
):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    code = _run(["message", "remote-delete", root, "personal", "7", "INBOX.Trash"])
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    assert len(out.strip().splitlines()) == 1
    receipt = json.loads(out.strip())
    assert receipt["action"] == "soft_delete"
    assert len(fake.calls) == 1
    op, account_id, config, uid, trash = fake.calls[0]
    assert op == "soft_delete"
    assert account_id == "personal"
    assert uid == 7 and trash == "INBOX.Trash"
    # host/puerto guardados en mail-servers.json, credencial resuelta en memoria
    assert config["host"] == "imap.saved.test"
    assert config["port"] == 1143
    assert config["username"] == "yo@example.test"
    assert config["password"] == SECRETO
    # sin secretos ni referencias en la salida
    assert SECRETO not in out + err
    assert "credential_ref" not in out + err


def test_remote_delete_usa_host_por_defecto_sin_servers_guardados(
    monkeypatch, tmp_path, capsys
):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=False)
    code = _run(["message", "remote-delete", root, "personal", "7", "INBOX.Trash"])
    assert code == 0
    _output(capsys)
    config = fake.calls[0][2]
    assert config["host"] == "imap.gmail.com"
    assert "port" not in config, "sin config guardada no debe fijar puerto"


def test_remote_restore_dispatcha_con_orden_exacto(monkeypatch, tmp_path, capsys):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    code = _run(
        ["message", "remote-restore", root, "personal", "9", "INBOX.Trash", "INBOX"]
    )
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    receipt = json.loads(out.strip())
    assert receipt["action"] == "restore"
    op, account_id, config, uid, trash, original = fake.calls[0]
    assert op == "restore"
    assert account_id == "personal"
    assert uid == 9 and trash == "INBOX.Trash" and original == "INBOX"


def test_remote_purge_dispatcha_con_confirmacion_literal(monkeypatch, tmp_path, capsys):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    code = _run(
        ["message", "remote-purge", root, "personal", "3", "INBOX", *PURGE_PHRASE.split()]
    )
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    receipt = json.loads(out.strip())
    assert receipt["action"] == "permanent_delete"
    op, account_id, config, mailbox, uid, confirmation = fake.calls[0]
    assert op == "permanent_delete"
    assert account_id == "personal"
    assert mailbox == "INBOX" and uid == 3
    assert confirmation == PURGE_PHRASE


def test_remote_purge_sin_frase_exacta_no_toca_provider(monkeypatch, tmp_path, capsys):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    for frase in (
        "CONFIRMAR BORRADO",
        "confirmar borrado permanente",
        "CONFIRMAR BORRADO PERMANENTE EXTRA",
        "borrar",
    ):
        code = _run(
            ["message", "remote-purge", root, "personal", "3", "INBOX", *frase.split()]
        )
        assert code == 1, "frase incorrecta debe dar 1: " + frase
        out, err = _output(capsys)
        assert fake.calls == [], "sin frase exacta el provider no debe llamarse"
        assert "confirmacion" in err.lower()
        assert "traceback" not in err.lower()
    # doble espacio, como un solo argumento: tampoco es la frase literal
    code = _run(
        ["message", "remote-purge", root, "personal", "3", "INBOX",
         "CONFIRMAR  BORRADO PERMANENTE"]
    )
    assert code == 1
    assert fake.calls == [], "sin frase exacta el provider no debe llamarse"


def test_remote_purge_frase_concatenada_en_un_argo(monkeypatch, tmp_path, capsys):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    code = _run(
        ["message", "remote-purge", root, "personal", "3", "INBOX", PURGE_PHRASE]
    )
    assert code == 0
    _output(capsys)
    assert len(fake.calls) == 1


def test_remote_arity_y_uid_invalidos_devuelven_2(monkeypatch, tmp_path, capsys):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    bad_cases = [
        ["message", "remote-delete"],
        ["message", "remote-delete", root, "personal"],
        ["message", "remote-delete", root, "personal", "7"],
        ["message", "remote-delete", root, "personal", "7", "INBOX.Trash", "extra"],
        ["message", "remote-restore", root, "personal", "9", "INBOX.Trash"],
        ["message", "remote-restore", root, "personal", "9", "INBOX.Trash", "INBOX", "x"],
        ["message", "remote-purge", root, "personal", "3"],
        ["message", "remote-delete", root, "personal", "0", "INBOX.Trash"],
        ["message", "remote-delete", root, "personal", "abc", "INBOX.Trash"],
        ["message", "remote-delete", root, "personal", "-1", "INBOX.Trash"],
        ["message", "remote-restore", root, "personal", "7.5", "INBOX.Trash", "INBOX"],
        ["message", "remote-purge", root, "personal", "", "INBOX", *PURGE_PHRASE.split()],
    ]
    for argv in bad_cases:
        code = _run(argv)
        assert code == 2, "argv " + repr(argv) + " debe dar 2"
        out, err = _output(capsys)
        assert fake.calls == [], "error de argumentos no debe tocar el provider"
        assert "usage:" in err.lower()
        assert out.strip() == ""


def test_remote_cuenta_ausente_devuelve_1_sin_llamar_provider(
    monkeypatch, tmp_path, capsys
):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    code = _run(
        ["message", "remote-delete", root, "otra-cuenta", "7", "INBOX.Trash"]
    )
    assert code == 1
    out, err = _output(capsys)
    assert fake.calls == []
    assert "cuenta no encontrada" in err.lower()
    assert out.strip() == ""


def test_remote_credencial_ausente_devuelve_1_sin_llamar_provider(
    monkeypatch, tmp_path, capsys
):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    monkeypatch.delenv("TEST_REMOTE_PW")
    code = _run(
        ["message", "remote-delete", root, "personal", "7", "INBOX.Trash"]
    )
    assert code == 1
    out, err = _output(capsys)
    assert fake.calls == []
    assert SECRETO not in out + err
    assert "credential_ref" not in err.lower()


def test_remote_provider_valueerror_devuelve_1(monkeypatch, tmp_path, capsys):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    fake.error = ValueError("uid debe ser int no bool >= 1")
    code = _run(
        ["message", "remote-delete", root, "personal", "7", "INBOX.Trash"]
    )
    assert code == 1
    out, err = _output(capsys)
    assert fake.calls and "traceback" not in err.lower()
    assert out.strip() == ""


def test_remote_provider_runtimeerror_devuelve_1_sin_password(
    monkeypatch, tmp_path, capsys
):
    root, fake = _setup_account(monkeypatch, tmp_path, with_servers=True)
    fake.error = RuntimeError("IMAP fallo: login rejected con " + SECRETO)
    code = _run(
        ["message", "remote-purge", root, "personal", "3", "INBOX", *PURGE_PHRASE.split()]
    )
    assert code == 1
    out, err = _output(capsys)
    assert fake.calls, "el fallo ocurre dentro del provider (una llamada)"
    assert out.strip() == ""
    assert "traceback" not in err.lower()
    assert SECRETO not in err, "la password jamas debe aparecer en el error"


def test_remote_outlook_host_por_defecto(monkeypatch, tmp_path, capsys):
    root, fake = _setup_account(
        monkeypatch, tmp_path, with_servers=False, provider="outlook"
    )
    code = _run(
        ["message", "remote-restore", root, "personal", "2", "INBOX.Trash", "INBOX"]
    )
    assert code == 0
    _output(capsys)
    assert fake.calls[0][2]["host"] == "outlook.office365.com"


def test_help_documenta_los_comandos_remotos_con_orden_pedido(capsys):
    code = _run(["--help"])
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    for fragmento in (
        "message remote-delete ROOT ACCOUNT_ID UID TRASH_MAILBOX",
        "message remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX ORIGINAL_MAILBOX",
        "message remote-purge ROOT ACCOUNT_ID UID MAILBOX",
    ):
        assert fragmento in out, "la ayuda debe documentar " + fragmento
