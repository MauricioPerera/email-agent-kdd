"""Lectura en solo lectura de un buzon IMAP segun el contrato fetch-imap-messages.

Delega el parseo integro en ``src.email.parse.parse_raw_email``; esta capa
solo valida, transporta (login -> select readonly -> search ALL -> fetch
RFC822) y libera la conexion en ``finally``. Sin disco, sin red fuera de la
fabrica inyectada y sin exponer la password en los errores.
"""

import imaplib

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
            if isinstance(item, (bytes, bytearray)):
                return bytes(item)
    return bytes(payload)


def fetch_imap_messages(account: dict, config: dict, connection_factory=None) -> list:
    mailbox, limit, since_uid = _validate(account, config)
    account_id = account["account_id"]
    host = config["host"]
    port = int(config.get("port", DEFAULT_PORT))
    if connection_factory is None:
        connection_factory = imaplib.IMAP4_SSL
    connection = connection_factory(host, port)
    try:
        connection.login(config["username"], config["password"])
        connection.select(mailbox, readonly=True)
        criterion = "UNSEEN" if config.get("unread", False) else "ALL"
        typ, data = connection.search(None, criterion)
        ids = _search_ids((typ, data))
        if since_uid is not None:
            ids = [message_id for message_id in ids if message_id > since_uid]
        ids = sorted(ids)[:limit]
        records = []
        for message_id in ids:
            typ, data = connection.fetch(str(message_id), "(RFC822)")
            record = parse_raw_email(_raw_message((typ, data)), account_id)
            record["imap_uid"] = message_id
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
