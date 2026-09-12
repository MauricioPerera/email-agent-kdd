"""Tests congelados del borrado remoto IMAP: src/email/imap_deletion.py.

Fake IMAP en memoria (sin red, sin credenciales reales). Cubre: soft_delete
hace login, select en modo escritura, UID COPY a Trash + UID STORE \\Deleted
y NUNCA llama EXPUNGE ni close(); restore mueve de Trash al mailbox original
sin expunge; purge sin la frase exacta CONFIRMAR BORRADO PERMANENTE no toca
el servidor; purge sin UIDPLUS no llama expunge; purge confirmado con UIDPLUS
usa UID EXPUNGE (solo el uid pedido); la validacion de uid/config falla antes
de conectar, la conexion se libera siempre (logout) y los errores nunca
contienen la password.
"""

import pytest

from src.email.imap_deletion import (
    ImapDeletionProvider,
    MailDeletionProvider,
    PURGE_CONFIRMATION,
)

ACCOUNT = {"account_id": "cuenta-test", "email": "usuario@example.test"}
CONFIG = {
    "uidvalidity": 123,
    "host": "imap.example.test",
    "port": 993,
    "username": "usuario",
    "password": "frozen-placeholder",
}
MAILBOX = "INBOX"
TRASH = "INBOX.Trash"
DELETED_FLAG = "(\\Deleted)"


class FakeIMAP:
    """Conexion IMAP falsa: registra cada llamada, nunca abre sockets."""

    def __init__(self, capabilities=("IMAP4REV1", "UIDPLUS")):
        self.capabilities = capabilities
        self.calls = []

    def login(self, username, password):
        self.calls.append(("login",))

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "UIDVALIDITY", [b"123"]

    def select(self, mailbox, readonly=True):
        self.calls.append(("select", mailbox, readonly))
        return ("OK", [b"1"])

    def uid(self, command, *args):
        self.calls.append(("uid", command) + tuple(args))
        return ("OK", [b"Done"])

    def unselect(self):
        self.calls.append(("unselect",))
        return ("OK", [b"bye"])

    def logout(self):
        self.calls.append(("logout",))
        return ("BYE", [b"bye"])


def _provider(fake):
    return ImapDeletionProvider(connection_factory=lambda host, port: fake)


def _uid_calls(fake):
    return [call for call in fake.calls if call[0] == "uid"]


def test_imap_provider_satisfies_protocol():
    assert isinstance(ImapDeletionProvider(), MailDeletionProvider)


@pytest.mark.parametrize('generation', [None, 122])
@pytest.mark.parametrize('action', ['soft_delete', 'restore', 'permanent_delete'])
def test_stale_generation_never_mutates_mailbox(generation, action):
    fake = FakeIMAP()
    provider = _provider(fake)
    config = dict(CONFIG, uidvalidity=generation)
    with pytest.raises(RuntimeError):
        if action == 'soft_delete':
            provider.soft_delete(ACCOUNT, config, 5, TRASH)
        elif action == 'restore':
            provider.restore(ACCOUNT, config, TRASH, 5, MAILBOX)
        else:
            provider.permanent_delete(ACCOUNT, config, MAILBOX, 5, PURGE_CONFIRMATION)
    assert _uid_calls(fake) == []


def test_soft_delete_copies_flags_deleted_and_never_expunges():
    fake = FakeIMAP()
    receipt = _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, TRASH)
    assert ("login",) in fake.calls, "soft_delete debe autenticarse"
    assert ("uid", "COPY", "5", TRASH) in _uid_calls(fake), (
        "soft_delete debe copiar el mensaje al mailbox Trash"
    )
    assert ("uid", "STORE", "5", "+FLAGS", DELETED_FLAG) in _uid_calls(fake), (
        "soft_delete debe marcar el original como Deleted"
    )
    for call in fake.calls:
        assert "EXPUNGE" not in str(call).upper(), (
            "soft_delete nunca debe llamar EXPUNGE"
        )
    assert ("select", MAILBOX, False) in fake.calls, (
        "el mailbox debe seleccionarse en modo escritura"
    )
    assert ("close",) not in fake.calls, "close expurgaria; no debe usarse"
    assert ("unselect",) in fake.calls and ("logout",) in fake.calls
    assert receipt == {
        "action": "soft_delete",
        "account_id": "cuenta-test",
        "mailbox": MAILBOX,
        "uid": 5,
        "trash_mailbox": TRASH,
        "copied": True,
        "flagged_deleted": True,
        "expunged": False,
    }


def test_soft_delete_rejects_invalid_uid_and_trash_without_touching_server():
    fake = FakeIMAP()
    for uid in (0, -1, "5", True):
        with pytest.raises(ValueError):
            _provider(fake).soft_delete(ACCOUNT, CONFIG, uid, TRASH)
    for bad_trash in ("", "  INBOX.Trash", None):
        with pytest.raises(ValueError):
            _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, bad_trash)
    assert fake.calls == [], "entradas invalidas no abren ni tocan el buzon"


def test_restore_moves_from_trash_to_original_without_expunge():
    fake = FakeIMAP()
    receipt = _provider(fake).restore(ACCOUNT, CONFIG, TRASH, 9, "INBOX")
    assert ("select", TRASH, False) in fake.calls
    assert ("uid", "COPY", "9", "INBOX") in _uid_calls(fake), (
        "restore debe copiar el mensaje al mailbox original"
    )
    assert ("uid", "STORE", "9", "+FLAGS", DELETED_FLAG) in _uid_calls(fake), (
        "restore debe marcar la copia de Trash como Deleted"
    )
    for call in fake.calls:
        assert "EXPUNGE" not in str(call).upper(), "restore nunca debe expurgar"
    assert ("close",) not in fake.calls
    assert receipt["original_mailbox"] == "INBOX" and receipt["expunged"] is False
    assert ("logout",) in fake.calls


def test_restore_rejects_same_mailbox_without_connecting():
    fake = FakeIMAP()
    with pytest.raises(RuntimeError):
        _provider(fake).restore(ACCOUNT, CONFIG, TRASH, 9, TRASH)
    assert fake.calls == [], "origen y destino iguales no abren conexion"


@pytest.mark.parametrize('expected,allowed', [(123, False), (456, True)])
def test_restore_checks_trash_generation_not_inbox(expected, allowed):
    class SeparateMailboxes(FakeIMAP):
        def select(self, mailbox, readonly=True):
            self.selected = mailbox
            return super().select(mailbox, readonly)

        def response(self, name):
            assert name == 'UIDVALIDITY'
            return name, [b'456' if self.selected == TRASH else b'123']

    fake = SeparateMailboxes()
    provider = _provider(fake)
    config = dict(CONFIG, uidvalidity=expected)
    if allowed:
        provider.restore(ACCOUNT, config, TRASH, 99, MAILBOX)
        assert ('uid', 'COPY', '99', MAILBOX) in _uid_calls(fake)
    else:
        with pytest.raises(RuntimeError, match='identity changed'):
            provider.restore(ACCOUNT, config, TRASH, 99, MAILBOX)
        assert _uid_calls(fake) == []


def test_purge_without_exact_confirmation_never_touches_the_server():
    fake = FakeIMAP()
    for bad in (
        "",
        "confirmar borrado permanente",
        " CONFIRMAR BORRADO PERMANENTE",
        "CONFIRMAR  BORRADO PERMANENTE",
        "CONFIRMAR ENVIO",
        "borrar ya",
    ):
        with pytest.raises(ValueError):
            _provider(fake).permanent_delete(ACCOUNT, CONFIG, MAILBOX, 5, bad)
    assert fake.calls == [], "sin frase exacta el servidor no recibe nada"


@pytest.mark.parametrize("capabilities", [("IMAP4REV1",), (b"IMAP4rev1",), (b"UIDPLUS-extra",)])
def test_purge_without_uidplus_fails_and_never_expunges(capabilities):
    fake = FakeIMAP(capabilities=capabilities)
    with pytest.raises(RuntimeError):
        _provider(fake).permanent_delete(
            ACCOUNT, CONFIG, MAILBOX, 5, PURGE_CONFIRMATION
        )
    for call in fake.calls:
        assert "EXPUNGE" not in str(call).upper(), (
            "sin UIDPLUS no se debe llamar expunge"
        )
    assert ("select", MAILBOX, False) not in fake.calls, (
        "el fallo de capacidad ocurre antes de tocar el buzon"
    )
    assert ("logout",) in fake.calls


@pytest.mark.parametrize("capabilities", [("IMAP4REV1", "UIDPLUS"), (b"IMAP4rev1", b"UIDPLUS")])
def test_purge_confirmed_with_uidplus_uses_uid_expunge(capabilities):
    fake = FakeIMAP(capabilities=capabilities)
    receipt = _provider(fake).permanent_delete(
        ACCOUNT, CONFIG, MAILBOX, 5, PURGE_CONFIRMATION
    )
    assert ("uid", "STORE", "5", "+FLAGS", DELETED_FLAG) in _uid_calls(fake)
    assert ("uid", "EXPUNGE", "5") in _uid_calls(fake), (
        "con UIDPLUS el purge debe usar UID EXPUNGE selectivo"
    )
    assert ("close",) not in fake.calls
    assert receipt == {
        "action": "permanent_delete",
        "account_id": "cuenta-test",
        "mailbox": MAILBOX,
        "uid": 5,
        "uidplus": True,
        "expunged": True,
    }
    assert ("logout",) in fake.calls


def test_purge_only_expunges_the_requested_uid():
    fake = FakeIMAP()
    _provider(fake).permanent_delete(ACCOUNT, CONFIG, MAILBOX, 12, PURGE_CONFIRMATION)
    expunges = [call for call in _uid_calls(fake) if call[1] == "EXPUNGE"]
    assert expunges == [("uid", "EXPUNGE", "12")], (
        "solo el uid pedido se expurga, nunca el buzon completo"
    )


def test_connection_is_released_and_password_is_never_exposed():
    class BrokenLogin(FakeIMAP):
        def login(self, username, password):
            raise RuntimeError("auth failed for frozen-placeholder")

    fake = BrokenLogin()
    with pytest.raises(RuntimeError) as excinfo:
        _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, TRASH)
    message = str(excinfo.value)
    assert "frozen-placeholder" not in message, "la password jamas sale en errores"
    assert "imap.example.test" in message and "cuenta-test" in message
    assert ("logout",) in fake.calls, "la conexion se libera incluso ante fallos"


def test_missing_account_or_config_fields_fail_before_connecting():
    fake = FakeIMAP()
    for bad_account in (
        {},
        {"account_id": "cuenta-test"},
        {"account_id": "", "email": "usuario@example.test"},
    ):
        with pytest.raises(ValueError):
            _provider(fake).soft_delete(bad_account, CONFIG, 5, TRASH)
    for key in ("host", "username", "password"):
        bad_config = dict(CONFIG)
        del bad_config[key]
        with pytest.raises(ValueError):
            _provider(fake).soft_delete(ACCOUNT, bad_config, 5, TRASH)
    with pytest.raises(ValueError):
        _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, "")
    assert fake.calls == [], "la validacion falla antes de abrir conexion"
# --- Sprint 2: fallos de transporte y liberacion de conexion (fake IMAP) ---


class _CopyFailsIMAP(FakeIMAP):
    """Fake que rechaza todo UID COPY con NO (sin red)."""

    def uid(self, command, *args):
        self.calls.append(("uid", command) + tuple(args))
        if command == "COPY":
            return ("NO", [b"COPY rejected"])
        return ("OK", [b"Done"])


class _StoreFailsIMAP(FakeIMAP):
    """Fake que rechaza todo UID STORE con COPY ok (sin red)."""

    def uid(self, command, *args):
        self.calls.append(("uid", command) + tuple(args))
        if command == "STORE":
            return ("NO", [b"STORE rejected"])
        return ("OK", [b"Done"])


class _PurgeLeaksPasswordIMAP(FakeIMAP):
    """Fake cuyo UID EXPUNGE falla mencionando la password (sin red)."""

    def uid(self, command, *args):
        self.calls.append(("uid", command) + tuple(args))
        if command == "EXPUNGE":
            raise RuntimeError("expunge rejected for frozen-placeholder")
        return ("OK", [b"Done"])


def test_invalid_mailbox_fails_before_connecting():
    """Mailbox invalido (vacio, con bordes, no str) aborta ANTES de conectar."""
    bad_mailboxes = ("", "  INBOX.Trash", None, 42)
    fake = FakeIMAP()
    for bad in bad_mailboxes:
        with pytest.raises(ValueError):
            _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, bad)
        with pytest.raises(ValueError):
            _provider(fake).restore(ACCOUNT, CONFIG, bad, 5, "INBOX")
        with pytest.raises(ValueError):
            _provider(fake).restore(ACCOUNT, CONFIG, TRASH, 5, bad)
        with pytest.raises(ValueError):
            _provider(fake).permanent_delete(
                ACCOUNT, CONFIG, bad, 5, PURGE_CONFIRMATION
            )
    assert fake.calls == [], "mailbox invalido no abre ni toca el buzon"


def test_copy_failure_skips_store_and_logs_out():
    class FailingCopy(_CopyFailsIMAP):
        pass

    fake = FailingCopy()
    with pytest.raises(RuntimeError):
        _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, TRASH)
    assert ("uid", "COPY", "5", TRASH) in _uid_calls(fake), (
        "el fallo ocurre en UID COPY"
    )
    store_calls = [call for call in _uid_calls(fake) if call[1] == "STORE"]
    assert store_calls == [], "COPY fallido no debe ejecutar UID STORE"
    assert ("logout",) in fake.calls, "COPY fallido igual libera la conexion"
    # restore: COPY a INBOX rechazado, tampoco STORE y si logout
    fake = FailingCopy()
    with pytest.raises(RuntimeError):
        _provider(fake).restore(ACCOUNT, CONFIG, TRASH, 9, "INBOX")
    assert ("uid", "COPY", "9", "INBOX") in _uid_calls(fake)
    assert [call for call in _uid_calls(fake) if call[1] == "STORE"] == []
    assert ("logout",) in fake.calls


def test_store_failure_after_copy_logs_out():
    fake = _StoreFailsIMAP()
    with pytest.raises(RuntimeError):
        _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, TRASH)
    assert ("uid", "COPY", "5", TRASH) in _uid_calls(fake), (
        "el COPY si se ejecuto antes del fallo de STORE"
    )
    assert ("uid", "STORE", "5", "+FLAGS", DELETED_FLAG) in _uid_calls(fake), (
        "el fallo ocurre en UID STORE despues del COPY"
    )
    expunge_calls = [call for call in _uid_calls(fake) if call[1] == "EXPUNGE"]
    assert expunge_calls == [], "STORE fallido nunca debe llevar a expunge"
    assert ("logout",) in fake.calls, "STORE fallido igual libera la conexion"
    # restore: mismo contrato sobre Trash
    fake = _StoreFailsIMAP()
    with pytest.raises(RuntimeError):
        _provider(fake).restore(ACCOUNT, CONFIG, TRASH, 9, "INBOX")
    assert ("uid", "COPY", "9", "INBOX") in _uid_calls(fake)
    assert ("uid", "STORE", "9", "+FLAGS", DELETED_FLAG) in _uid_calls(fake)
    assert ("logout",) in fake.calls


def test_unselect_absent_does_not_prevent_logout():
    class BareIMAP:
        def response(self, name):
            return "UIDVALIDITY", [b"123"]
        """Conexion minima SIN atributo unselect (sin red)."""

        def __init__(self):
            self.capabilities = ("IMAP4REV1", "UIDPLUS")
            self.calls = []

        def login(self, username, password):
            self.calls.append(("login",))

        def select(self, mailbox, readonly=True):
            self.calls.append(("select", mailbox, readonly))
            return ("OK", [b"1"])

        def uid(self, command, *args):
            self.calls.append(("uid", command) + tuple(args))
            return ("OK", [b"Done"])

        def logout(self):
            self.calls.append(("logout",))
            return ("BYE", [b"bye"])

    fake = BareIMAP()
    assert not hasattr(fake, "unselect"), "el fake de prueba no define unselect"
    receipt = _provider(fake).soft_delete(ACCOUNT, CONFIG, 5, TRASH)
    assert receipt["copied"] is True and receipt["expunged"] is False
    assert ("unselect",) not in fake.calls
    assert ("logout",) in fake.calls, (
        "sin unselect la liberacion igual debe llegar a logout"
    )
    assert ("close",) not in fake.calls


def test_purge_sanitizes_password_in_errors():
    fake = _PurgeLeaksPasswordIMAP()
    with pytest.raises(RuntimeError) as excinfo:
        _provider(fake).permanent_delete(
            ACCOUNT, CONFIG, MAILBOX, 5, PURGE_CONFIRMATION
        )
    message = str(excinfo.value)
    assert "frozen-placeholder" not in message, (
        "la password jamas debe salir en el error del purge"
    )
    assert "***" in message, "el fallo del purge debe venir sanitizado"
    assert "imap.example.test" in message and "cuenta-test" in message
    assert ("logout",) in fake.calls, "el fallo del purge igual libera la conexion"
