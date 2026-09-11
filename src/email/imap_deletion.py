"""Borrado remoto IMAP reversible y permanente, con conexion inyectable.

``MailDeletionProvider`` es el Protocol estructural (como ``EmailProvider``):
define QUE debe saber hacer un adaptador de borrado, nunca COMO. La
implementacion ``ImapDeletionProvider`` transporta (login -> select en modo
escritura -> UID COPY -> UID STORE \\Deleted -> unselect) y delega las
validaciones en helpers puros.

Reglas de seguridad:
- ``soft_delete`` copia el mensaje al mailbox de papelera (``trash_mailbox``
  explicito en la llamada) con UID COPY y marca el original \\Deleted con
  UID STORE. NUNCA llama EXPUNGE ni ``close()`` (en RFC 3501 close expurga
  silenciosamente): libera con ``unselect()``.
- ``restore`` mueve el mensaje desde Trash a su mailbox original con UID
  COPY + UID STORE \\Deleted en Trash; nunca expurge.
- ``permanent_delete`` exige la frase literal exacta
  ``CONFIRMAR BORRADO PERMANENTE`` y UID EXPUNGE SOLO si el servidor anuncia
  UIDPLUS; si no, aborta ANTES de tocar el buzon para evitar un EXPUNGE
  global.
La password jamas aparece en los errores y la conexion se libera en
``finally`` (logout) incluso ante fallos.
"""

import imaplib

from typing import Protocol, runtime_checkable

PURGE_CONFIRMATION = "CONFIRMAR BORRADO PERMANENTE"
DEFAULT_PORT = 993
_DELETED_FLAG = "(\\Deleted)"
_CAPABILITY = "UIDPLUS"


@runtime_checkable
class MailDeletionProvider(Protocol):
    """Interfaz minima de un adaptador de borrado (solo dicts serializables)."""

    def soft_delete(
        self, account: dict, config: dict, uid: int, trash_mailbox: str
    ) -> dict:
        """Mover el mensaje a la papelera remota sin expurgar; devuelve recibo."""
        ...

    def restore(
        self,
        account: dict,
        config: dict,
        trash_mailbox: str,
        uid: int,
        original_mailbox: str,
    ) -> dict:
        """Devolver el mensaje de la papelera a su mailbox original; recibo."""
        ...

    def permanent_delete(
        self, account: dict, config: dict, mailbox: str, uid: int, confirmation: str
    ) -> dict:
        """Expurgar UN uid SOLO con confirmacion exacta y UIDPLUS; recibo."""
        ...


def _field_ok(mapping, key):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    return isinstance(value, str) and value != ""


def _validate_session(account, config):
    """Valida account/config ANTES de abrir conexion; devuelve (id, host, port)."""
    for mapping, keys, label in (
        (account, ("account_id", "email"), "account"),
        (config, ("host", "username", "password"), "config"),
    ):
        for key in keys:
            if not _field_ok(mapping, key):
                raise ValueError(
                    label + " debe traer '" + key + "' como str no vacio"
                )
    port = config.get("port", DEFAULT_PORT)
    if not isinstance(port, int) or isinstance(port, bool) or port < 1:
        raise ValueError("port debe ser int no bool >= 1")
    return account["account_id"], config["host"], port


def _validate_mailbox(mailbox):
    if not isinstance(mailbox, str) or not mailbox or mailbox != mailbox.strip():
        raise ValueError("mailbox debe ser str no vacio y sin espacios en bordes")
    return mailbox


def _validate_uid(uid):
    if not isinstance(uid, int) or isinstance(uid, bool) or uid < 1:
        raise ValueError("uid debe ser int no bool >= 1")
    return uid


def _wrap_error(account_id, host, config, exc):
    """Envuelve un fallo de transporte en RuntimeError sin exponer la password."""
    message = str(exc)
    password = config["password"] if isinstance(config, dict) else None
    if password and password in message:
        message = message.replace(password, "***")
    return RuntimeError(
        "IMAP fallo para " + account_id + " en " + host + ": " + message
    )


def _uid_check(result, action):
    """Rechaza una respuesta UID que no sea OK (el fallo se envuelve fuera)."""
    typ = result[0] if isinstance(result, tuple) else None
    if typ != "OK":
        raise RuntimeError(action + " rechazado por el servidor: " + str(typ))
    return result


def _announce_uidplus(connection):
    """True solo si la conexion anuncia UIDPLUS (UID EXPUNGE selectivo)."""
    capabilities = getattr(connection, "capabilities", ()) or ()
    return any(str(capability).upper() == _CAPABILITY for capability in capabilities)


def _release(connection):
    """Libera la conexion SIN expurgar: unselect + logout, tolerando fallos."""
    for action in ("unselect", "logout"):
        method = getattr(connection, action, None)
        if method is None:
            continue
        try:
            method()
        except Exception:
            pass


class ImapDeletionProvider:
    """Implementacion IMAP de MailDeletionProvider (factory inyectable)."""

    def __init__(self, connection_factory=None):
        self._connection_factory = connection_factory or imaplib.IMAP4_SSL

    def soft_delete(self, account, config, uid, trash_mailbox):
        """COPY a Trash/Papelera + STORE \\Deleted en el original; NUNCA expunge."""
        account_id, host, port = _validate_session(account, config)
        uid = _validate_uid(uid)
        trash = _validate_mailbox(trash_mailbox)
        connection = None
        try:
            connection = self._connection_factory(host, port)
            connection.login(config["username"], config["password"])
            mailbox = config.get("mailbox") or "INBOX"
            connection.select(mailbox, readonly=False)
            _uid_check(connection.uid("COPY", str(uid), trash), "UID COPY")
            _uid_check(
                connection.uid("STORE", str(uid), "+FLAGS", _DELETED_FLAG),
                "UID STORE",
            )
            return {
                "action": "soft_delete",
                "account_id": account_id,
                "mailbox": mailbox,
                "uid": uid,
                "trash_mailbox": trash,
                "copied": True,
                "flagged_deleted": True,
                "expunged": False,
            }
        except Exception as exc:
            raise _wrap_error(account_id, host, config, exc) from exc
        finally:
            if connection is not None:
                _release(connection)

    def restore(self, account, config, trash_mailbox, uid, original_mailbox):
        """Mueve el mensaje desde Trash a su mailbox original; sin expunge."""
        account_id, host, port = _validate_session(account, config)
        trash = _validate_mailbox(trash_mailbox)
        original = _validate_mailbox(original_mailbox)
        uid = _validate_uid(uid)
        if trash.lower() == original.lower():
            raise RuntimeError(
                "origen y destino son el mismo mailbox; nada que mover: " + trash
            )
        connection = None
        try:
            connection = self._connection_factory(host, port)
            connection.login(config["username"], config["password"])
            connection.select(trash, readonly=False)
            _uid_check(connection.uid("COPY", str(uid), original), "UID COPY")
            _uid_check(
                connection.uid("STORE", str(uid), "+FLAGS", _DELETED_FLAG),
                "UID STORE",
            )
            return {
                "action": "restore",
                "account_id": account_id,
                "trash_mailbox": trash,
                "uid": uid,
                "original_mailbox": original,
                "copied": True,
                "flagged_deleted": True,
                "expunged": False,
            }
        except Exception as exc:
            raise _wrap_error(account_id, host, config, exc) from exc
        finally:
            if connection is not None:
                _release(connection)

    def permanent_delete(self, account, config, mailbox, uid, confirmation):
        """UID EXPUNGE del uid pedido SOLO con confirmacion exacta y UIDPLUS."""
        if confirmation != PURGE_CONFIRMATION:
            raise ValueError(
                "confirmacion explicita requerida para el borrado permanente"
            )
        account_id, host, port = _validate_session(account, config)
        mailbox = _validate_mailbox(mailbox)
        uid = _validate_uid(uid)
        connection = None
        try:
            connection = self._connection_factory(host, port)
            connection.login(config["username"], config["password"])
            if not _announce_uidplus(connection):
                raise RuntimeError(
                    "el servidor no anuncia UIDPLUS; se cancela el purge "
                    "para evitar un EXPUNGE global"
                )
            connection.select(mailbox, readonly=False)
            _uid_check(
                connection.uid("STORE", str(uid), "+FLAGS", _DELETED_FLAG),
                "UID STORE",
            )
            _uid_check(connection.uid("EXPUNGE", str(uid)), "UID EXPUNGE")
            return {
                "action": "permanent_delete",
                "account_id": account_id,
                "mailbox": mailbox,
                "uid": uid,
                "uidplus": True,
                "expunged": True,
            }
        except Exception as exc:
            if not isinstance(exc, ValueError):
                raise _wrap_error(account_id, host, config, exc) from exc
            raise
        finally:
            if connection is not None:
                _release(connection)


def imap_soft_delete(account, config, uid, trash_mailbox, connection_factory=None) -> dict:
    """soft_delete remoto sobre ImapDeletionProvider (factory opcional)."""
    return ImapDeletionProvider(connection_factory).soft_delete(
        account, config, uid, trash_mailbox
    )


def imap_restore(
    account, config, trash_mailbox, uid, original_mailbox, connection_factory=None
) -> dict:
    """restore remoto sobre ImapDeletionProvider (factory opcional)."""
    return ImapDeletionProvider(connection_factory).restore(
        account, config, trash_mailbox, uid, original_mailbox
    )


def imap_permanent_delete(
    account, config, mailbox, uid, confirmation, connection_factory=None
) -> dict:
    """permanent_delete remoto sobre ImapDeletionProvider (factory opcional)."""
    return ImapDeletionProvider(connection_factory).permanent_delete(
        account, config, mailbox, uid, confirmation
    )