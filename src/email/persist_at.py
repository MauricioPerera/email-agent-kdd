"""Persistencia de un registro normalizado como nodo OKF con raiz explicita."""

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


def _validate_root(root: str) -> Path:
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root debe ser str no vacio")
    return Path(root).resolve()


def _resolve_rel_path(root: Path, rel_path: str) -> Path:
    text = str(rel_path)
    portable_text = text.replace("\\", "/")
    windows_absolute = len(portable_text) >= 3 and portable_text[1:3] == ":/"
    if (
        not text
        or Path(portable_text).is_absolute()
        or windows_absolute
        or portable_text.startswith("~")
    ):
        raise ValueError("rel_path insegura: absoluta o fuera de la raiz: " + text)
    if ".." in portable_text.split("/"):
        raise ValueError("rel_path insegura: segmento '..' no permitido: " + text)
    target = (root / Path(portable_text)).resolve()
    if target != root and root not in target.parents:
        raise ValueError("rel_path insegura: resuelve fuera de la raiz: " + text)
    return target


def _validate_record(record):
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
            delivered = record.get("delivered_to")
            lines.append("delivered_to: " + ", ".join(str(addr) for addr in delivered))
    # Identidad de re-descarga por UID: solo cuando el record la trae; los
    # records legacy (sin imap_uid/mailbox) se renderizan igual que antes.
    for key in ("imap_uid", "mailbox"):
        value = record.get(key)
        if value is not None and value != "":
            lines.append(key + ": " + str(value))
    if record.get("attachments"):
        lines.append("attachments:")
        for attachment in record["attachments"]:
            lines.extend(render_attachment_front_lines(attachment))
    return "\n".join(lines) + "\n---\n" + str(record["body"])


def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str:
    _validate_record(record)
    root_path = _validate_root(root)
    target = _resolve_rel_path(root_path, rel_path)
    content = _render(record).encode("utf-8")
    if target.exists():
        if target.read_bytes() != content:
            raise OSError(
                "destino ya existe con contenido distinto: " + str(target)
            )
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(target)
    return str(target)
