"""Envio de correos ya confirmados por SMTP, con recibo serializable. Valida toda la entrada
(confirmacion estricta ``is True``) antes de conectar; ``quit()`` corre en ``finally``; los
errores de transporte se relanzan como ``RuntimeError`` sin password ni cuerpo. Sin disco,
sin logs; la unica red es la fabrica inyectada (465: ``smtplib.SMTP_SSL``; resto: ``SMTP``)."""

import smtplib
from src.email.transport import open_smtp, secure_smtp
from email.message import EmailMessage

_DEFAULT_PORT = 587


def _ok(value):
    return isinstance(value, str) and value != ""


def _resolve_port(config):
    if "port" not in config:
        return _DEFAULT_PORT
    value = config["port"]
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 65535:
        raise ValueError("port invalido")
    return value


def _resolve_from_email(account, config):
    if "from_email" in config and not _ok(config["from_email"]):
        raise ValueError("from_email invalido")
    return config.get("from_email", account["email"])


def _validate(account, config, message):
    if not isinstance(account, dict) or not _ok(account.get("account_id")) or not _ok(account.get("email")):
        raise ValueError("account invalido")
    if not isinstance(config, dict) or not _ok(config.get("host")) or not _ok(config.get("username")) or not _ok(config.get("password")):
        raise ValueError("config invalido")
    if not isinstance(message, dict) or message.get("confirmed") is not True:
        raise ValueError("envio no confirmado")
    to = message.get("to")
    if not isinstance(to, list) or not to or not all(_ok(x) for x in to):
        raise ValueError("to invalido")
    if not _ok(message.get("subject")) or not _ok(message.get("body")):
        raise ValueError("subject o body invalido")


def _deliver(factory, endpoint, credentials, msg):
    connection = None
    try:
        connection = factory(*endpoint)
        secure_smtp(connection, endpoint[1])
        connection.login(*credentials)
        connection.send_message(msg)
    finally:
        if connection is not None:
            try:
                connection.quit()
            except Exception:
                # QUIT cannot undo an accepted DATA transaction or replace
                # the original delivery error with a cleanup error.
                try:
                    connection.close()
                except Exception:
                    pass


def send_smtp_message(account, config, message, connection_factory=None):
    _validate(account, config, message)
    port = _resolve_port(config)
    endpoint = (config["host"], port)
    from_email = _resolve_from_email(account, config)
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = ", ".join(message["to"])
    msg["Subject"] = message["subject"]
    msg.set_content(message["body"])
    default = open_smtp
    factory = connection_factory if connection_factory is not None else default
    try:
        _deliver(factory, endpoint, (config["username"], config["password"]), msg)
    except Exception as exc:
        raise RuntimeError(
            "smtp send failed for " + account["account_id"] + " via " + endpoint[0]
            + ": " + type(exc).__name__
        ) from exc
    return {
        "account_id": account["account_id"],
        "from_email": from_email,
        "to": list(message["to"]),
        "subject": message["subject"],
        "sent": True,
    }
