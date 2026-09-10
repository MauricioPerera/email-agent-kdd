"""Normalizacion determinista de mensajes MIME para evidencia y conocimiento OKF."""

import email
import hashlib


def _validate(raw_message, account_id):
    if not isinstance(raw_message, bytes):
        raise ValueError("raw_message debe ser bytes")
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id debe ser str no vacio")


def _headers_dict(message):
    return {key.lower(): value for key, value in message.items()}


def _payload(part):
    return part.get_payload(decode=True) or b""


def _is_attachment(part):
    return "attachment" in (part.get("Content-Disposition") or "").lower()


def _body(message):
    for part in message.walk():
        if part.is_multipart() or _is_attachment(part):
            continue
        if part.get_content_type() == "text/plain":
            return _payload(part).decode("utf-8", "replace")
    return ""


def _attachment(part):
    content = _payload(part)
    name = part.get_filename()
    if not name:
        name = part.get_param("name", header="content-type") or ""
    return {
        "name": name,
        "mime_type": part.get_content_type(),
        "size": len(content),
        "content": content,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _attachments(message):
    return [_attachment(part) for part in message.walk() if _attachment_part(part)]


def _attachment_part(part):
    return not part.is_multipart() and _is_attachment(part)


def normalize_email(raw_message: bytes, account_id: str) -> dict:
    _validate(raw_message, account_id)
    message = email.message_from_bytes(raw_message)
    return {
        "account_id": account_id,
        "headers": _headers_dict(message),
        "body": _body(message),
        "attachments": _attachments(message),
        "raw": raw_message,
        "raw_sha256": hashlib.sha256(raw_message).hexdigest(),
    }