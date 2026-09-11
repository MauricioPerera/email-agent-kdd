"""Parseo determinista de un mensaje RFC 5322 crudo a registro serializable OKF."""

import hashlib

from email import policy
from email.parser import BytesParser

from src.email.delivery import extract_delivered_to


def _header(message, name):
    value = message.get(name)
    return str(value) if value is not None else ""


def _decode_part(part):
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, "replace")
    except LookupError:
        return payload.decode("utf-8", "replace")


def _leaf_parts(message):
    for part in message.walk():
        if not part.is_multipart():
            yield part


def _body(message):
    leaves = [part for part in _leaf_parts(message) if part.get_filename() is None]
    for wanted in ("text/plain", "text/html"):
        for part in leaves:
            if part.get_content_type() == wanted:
                return _decode_part(part)
    return ""


def _attachments(message):
    result = []
    for part in _leaf_parts(message):
        filename = part.get_filename()
        if filename is None:
            continue
        content = part.get_payload(decode=True) or b""
        result.append(
            {
                "filename": str(filename),
                "content_type": part.get_content_type(),
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return result


def parse_raw_email(raw_message: bytes, account_id: str) -> dict:
    if not isinstance(raw_message, bytes):
        raise ValueError("raw_message debe ser bytes")
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id debe ser str no vacio")
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    record = {
        "type": "email",
        "account_id": account_id,
        "subject": _header(message, "Subject"),
        "from": _header(message, "From"),
        "to": _header(message, "To"),
        "cc": _header(message, "Cc"),
        "date": _header(message, "Date"),
        "message_id": _header(message, "Message-ID"),
        "in_reply_to": _header(message, "In-Reply-To"),
        "references": _header(message, "References"),
        "body": _body(message),
        "raw_sha256": hashlib.sha256(raw_message).hexdigest(),
        "attachments": _attachments(message),
    }
    delivered = extract_delivered_to(message)
    if delivered:
        record["delivered_to"] = delivered
    return record