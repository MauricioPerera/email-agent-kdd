"""Lectura en solo lectura de un buzon IMAP segun el contrato fetch-imap-messages.

Delega el parseo integro en ``src.email.parse.parse_raw_email``; esta capa
solo valida, transporta (login -> select readonly -> search ALL -> fetch
RFC822) y libera la conexion en ``finally``. Sin disco, sin red fuera de la
fabrica inyectada y sin exponer la password en los errores.
"""

import imaplib
from src.email.transport import open_imap
from src.email.imap_identity import require_uidvalidity, selected_uidvalidity

from src.email.parse import parse_raw_email

DEFAULT_MAILBOX = "INBOX"
DEFAULT_LIMIT = 50
DEFAULT_PORT = 993
LIMIT_MIN = 1
LIMIT_MAX = 100


def _field_ok(mapping, key):
    value = mapping.get(key) if isinstance(mapping, dict) else None
    return isinstance(value, str) and value != ""


def _validate(account, config):
    """Valida account/config ANTES de abrir conexion; devuelve (mailbox, limit, since_uid)."""
    for mapping, keys, label in (
        (account, ("account_id", "email"), "account"),
        (config, ("host", "username", "password"), "config"),
    ):
        for key in keys:
            if not _field_ok(mapping, key):
                raise ValueError(
                    label + " debe traer '" + key + "' como str no vacio"
                )
    limit = config.get("limit", DEFAULT_LIMIT)
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not LIMIT_MIN <= limit <= LIMIT_MAX
    ):
        raise ValueError("limit debe ser int entre 1 y 100 inclusive")
    mailbox = config.get("mailbox", DEFAULT_MAILBOX)
    if not isinstance(mailbox, str) or not mailbox:
        raise ValueError("mailbox debe ser str no vacio")
    since_uid = config.get("since_uid")
    if since_uid is not None and (
        not isinstance(since_uid, int) or isinstance(since_uid, bool) or since_uid < 0
    ):
        raise ValueError("since_uid debe ser int no bool >= 0")
    if "unread" in config and not isinstance(config["unread"], bool):
        raise ValueError("unread debe ser bool")
    return mailbox, limit, since_uid


def _search_ids(data):
    """IDs enteros desde la respuesta de search(None, ALL)."""
    if isinstance(data, tuple):
        data = data[1]
    tokens = []
    for chunk in data:
        text = bytes(chunk).decode("ascii") if isinstance(chunk, (bytes, bytearray)) else str(chunk)
        tokens.extend(int(token) for token in text.split())
    return tokens


def _raw_message(result):
    """Bytes RFC822 desde la respuesta de fetch(id, '(RFC822)')."""
    payload = result[1] if isinstance(result, tuple) else result
    if isinstance(payload, (list, tuple)):
        for item in payload:
            if isinstance(item, (tuple, list)) and item and isinstance(item[-1], (bytes, bytearray)):
                return bytes(item[-1])
    raise RuntimeError("UID FETCH returned no message literal")


def fetch_raw_message_by_uid(
    account: dict, config: dict, uid: int, connection_factory=None
) -> bytes:
    """Fetch RFC822 readonly de UN mensaje por UID: devuelve los bytes crudos.

    Reutiliza la validacion (`_validate`), la limpieza de conexion (`finally`)
    y la sanitizacion de password de `fetch_imap_messages`. Solo lectura: no
    muta el cursor ni el mailbox.
    """
    if not isinstance(uid, int) or isinstance(uid, bool) or uid < 1:
        raise ValueError("uid debe ser int no bool >= 1")
    mailbox, _limit, _since_uid = _validate(account, config)
    account_id = account["account_id"]
    host = config["host"]
    port = int(config.get("port", DEFAULT_PORT))
    if connection_factory is None:
        connection_factory = open_imap
    connection = connection_factory(host, port)
    try:
        connection.login(config["username"], config["password"])
        selected, _ = connection.select(mailbox, readonly=True)
        if selected != "OK":
            raise RuntimeError("mailbox selection failed")
        require_uidvalidity(connection, config.get("uidvalidity"))
        typ, data = connection.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if typ != "OK":
            raise RuntimeError("UID FETCH failed")
        return _raw_message((typ, data))
    except Exception as exc:
        message = type(exc).__name__ + ": " + str(exc)
        password = config["password"]
        if password and password in message:
            message = message.replace(password, "***")
        raise RuntimeError(
            "IMAP fallo para " + account_id + " en " + host + ": " + message
        ) from exc
    finally:
        for action in ("close", "logout"):
            try:
                getattr(connection, action)()
            except Exception:
                pass


def fetch_imap_messages(
    account: dict, config: dict, connection_factory=None, include_raw=False
) -> list:
    """Sincroniza el buzon; con `include_raw=True` cada record lleva el RFC822.

    `include_raw` es opt-in (solo `sync --attachments`): adjunta el RFC822 ya
    descargado en `record["raw_message"]` para que la extraccion de adjuntos
    reutilice esos bytes sin re-fetch. Por defecto (False) el record queda
    exactamente igual que antes y los bytes se descartan.
    """
    mailbox, limit, since_uid = _validate(account, config)
    account_id = account["account_id"]
    host = config["host"]
    port = int(config.get("port", DEFAULT_PORT))
    if connection_factory is None:
        connection_factory = open_imap
    connection = connection_factory(host, port)
    try:
        connection.login(config["username"], config["password"])
        selected, _ = connection.select(mailbox, readonly=True)
        if selected != "OK":
            raise RuntimeError("mailbox selection failed")
        uidvalidity = selected_uidvalidity(connection)
        if config.get("uidvalidity") != uidvalidity:
            since_uid = 0
        criterion = "UNSEEN" if config.get("unread", False) else "ALL"
        typ, data = connection.uid("SEARCH", None, criterion)
        if typ != "OK":
            raise RuntimeError("UID SEARCH failed")
        ids = _search_ids((typ, data))
        if since_uid is not None:
            ids = [message_id for message_id in ids if message_id > since_uid]
        ids = sorted(ids)[:limit]
        records = []
        for message_id in ids:
            typ, data = connection.uid("FETCH", str(message_id), "(BODY.PEEK[])")
            if typ != "OK":
                raise RuntimeError("UID FETCH failed")
            raw = _raw_message((typ, data))
            record = parse_raw_email(raw, account_id)
            record["imap_uid"] = message_id
            record["uidvalidity"] = uidvalidity
            record["mailbox"] = mailbox
            if include_raw:
                record["raw_message"] = raw
            records.append(record)
        return records
    except Exception as exc:
        message = type(exc).__name__ + ": " + str(exc)
        password = config["password"]
        if password and password in message:
            message = message.replace(password, "***")
        raise RuntimeError(
            "IMAP fallo para " + account_id + " en " + host + ": " + message
        ) from exc
    finally:
        for action in ("close", "logout"):
            try:
                getattr(connection, action)()
            except Exception:
                pass
