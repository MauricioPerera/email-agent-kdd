"""Persistencia de un registro normalizado como nodo OKF (Markdown + frontmatter)."""

from pathlib import Path

from src.email.attachments import render_attachment_front_lines

_FRONT_FIELDS = (
    ("type", "Email Message"),
    ("account_id", "account_id"),
    ("subject", "subject"),
    ("from", "from"),
    ("to", "to"),
    ("date", "date"),
    ("raw_sha256", "raw_sha256"),
)

_OPTIONAL_FRONT_FIELDS = ("cc", "message_id", "in_reply_to", "references")


def _resolve_safe(path):
    root = Path.cwd().resolve()
    text = str(path)
    if not text or Path(text).is_absolute() or text.startswith("~"):
        raise ValueError("ruta insegura: absoluta o fuera de la raiz permitida: " + text)
    if ".." in text.replace("\\", "/").split("/"):
        raise ValueError("ruta insegura: segmento '..' no permitido: " + text)
    target = (root / Path(text)).resolve()
    if target != root and root not in target.parents:
        raise ValueError("ruta insegura: resuelve fuera de la raiz permitida: " + text)
    return target


def _validate(record):
    if not isinstance(record, dict):
        raise ValueError("record debe ser un dict")
    for key in ("account_id", "raw_sha256", "body"):
        if key not in record:
            raise ValueError("record sin clave minima: " + key)


def _scalar(value):
    if value is None or value == "":
        return '""'
    return str(value)


def _render(record):
    lines = ["---"]
    for label, key in _FRONT_FIELDS:
        value = "Email Message" if label == "type" else record.get(key)
        lines.append(label + ": " + _scalar(value))
        if label == "to" and record.get("delivered_to"):
            lines.append(
                "delivered_to: "
                + ", ".join(str(addr) for addr in record["delivered_to"])
            )
    for key in _OPTIONAL_FRONT_FIELDS:
        value = record.get(key)
        if value is not None and value != "":
            lines.append(key + ": " + _scalar(value))
    # Identidad de re-descarga por UID: solo cuando el record la trae; los
    # records legacy (sin imap_uid/mailbox) se renderizan igual que antes.
    for key in ("imap_uid", "mailbox", "uidvalidity"):
        value = record.get(key)
        if value is not None and value != "":
            lines.append(key + ": " + str(value))
    if record.get("attachments"):
        lines.append("attachments:")
        for attachment in record["attachments"]:
            lines.extend(render_attachment_front_lines(attachment))
    return "\n".join(lines) + "\n---\n" + str(record["body"])


def persist_email_okf(record: dict, path: str) -> str:
    _validate(record)
    target = _resolve_safe(path)
    text = _render(record)
    if target.exists() and target.read_text(encoding="utf-8") != text:
        raise OSError(
            "destino ya existe con contenido distinto sin confirmacion: " + str(target)
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    tmp.replace(target)
    return str(target)
