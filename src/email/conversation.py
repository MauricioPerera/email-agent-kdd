"""Clave de conversacion para records de email (contrato conversation-key).

Deriva una clave determinista de hilo: prioridad References > In-Reply-To >
Message-ID; fallback por subject (sin prefijos Re:/Fwd:/Rv:) + participantes
ordenados y deduplicados. Salida: sha256 hex de 64 chars, seguro como ruta.
"""

import hashlib
import re

_ID_PREFIXES = ("re:", "fwd:", "rv:")


def _norm_ids(value):
    """IDs de hilo normalizados desde un valor str | list | ausente/basura."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        text = str(item).strip().strip("<>").strip()
        if text:
            out.append(text.lower())
    return out


def _norm_subject(subject):
    """Subject base: quita prefijos Re:/Fwd:/Rv: repetidos y colapsa espacios."""
    text = subject if isinstance(subject, str) else ""
    text = text.strip()
    while True:
        low = text.lower()
        for prefix in _ID_PREFIXES:
            if low.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        else:
            return re.sub(r"\s+", " ", text).lower()


def _norm_participants(record):
    """Emails de from/to/cc normalizados, ordenados y sin duplicados."""
    parts = set()
    for key in ("from", "to", "cc"):
        value = record.get(key)
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            continue
        for item in value:
            text = str(item).strip().lower() if item else ""
            if text:
                parts.add(text)
    return sorted(parts)


def conversation_key(record: dict) -> str:
    """Clave sha256 (64 hex) de la conversacion a la que pertenece `record`.

    No muta `record`; es pura y determinista.
    """
    ids = _norm_ids(record.get("references")) + _norm_ids(record.get("in_reply_to")) or _norm_ids(
        record.get("message_id")
    )
    if not ids:
        ids = [_norm_subject(record.get("subject"))] + _norm_participants(record)
    return hashlib.sha256("|".join(ids).encode("utf-8")).hexdigest()