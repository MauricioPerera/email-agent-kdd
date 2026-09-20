"""Gramática determinista compartida por búsqueda local y notificaciones."""

import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

from src.email.conversation import conversation_key
from src.email.topics import extract_topics

_CONVERSATION_RE = re.compile(r"^[0-9a-f]{64}$")
_TOPIC_RE = re.compile(r"^\w{1,64}$")
_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_BOUNDARY = r"[A-Za-z0-9._%+-]"


@dataclass(frozen=True)
class Filter:
    kind: str
    value: str = ""


def _email(value, prefix):
    local, separator, domain = value.partition("@")
    if not local or not separator or not domain:
        raise ValueError(prefix + " EMAIL malformado")
    return value.casefold()


def parse_filter_query(instruction: str) -> list[Filter]:
    """Parsea filtros AND sin I/O, shell, NLP ni interpretación de contenido."""
    if not isinstance(instruction, str):
        raise ValueError("instruction debe ser str")
    tokens = instruction.split()
    if not tokens:
        raise ValueError("instruction sin criterios tras normalizar espacios")
    parsed = []
    for token in tokens:
        lowered = token.casefold()
        if lowered in ("is:reply", "has:attachment"):
            parsed.append(Filter(lowered))
            continue
        for prefix in ("para", "contact", "from", "to", "cc"):
            marker = prefix + ":"
            if lowered.startswith(marker):
                parsed.append(Filter(prefix, _email(token[len(marker):].strip(), marker)))
                break
        else:
            if lowered.startswith("conversation:"):
                value = token[13:].strip().casefold()
                if not _CONVERSATION_RE.fullmatch(value):
                    raise ValueError("conversation: KEY no es hex-64")
                parsed.append(Filter("conversation", value))
            elif lowered.startswith("topic:"):
                value = token[6:].strip().casefold()
                if not _TOPIC_RE.fullmatch(value):
                    raise ValueError("topic: TOPIC inseguro")
                parsed.append(Filter("topic", value))
            elif lowered.startswith("account:"):
                value = token[8:].strip()
                if not _ACCOUNT_RE.fullmatch(value):
                    raise ValueError("account: ACCOUNT_ID inseguro")
                parsed.append(Filter("account", value.casefold()))
            elif lowered.startswith("date:"):
                value = token[5:].strip()
                if not _DATE_RE.fullmatch(value):
                    raise ValueError("date: DATE fuera del formato estricto YYYY-MM-DD")
                parsed.append(Filter("date", value))
            elif lowered.startswith("subject:"):
                value = token[8:].strip().casefold()
                if not value:
                    raise ValueError("subject: TEXT vacio")
                parsed.append(Filter("subject", value))
            else:
                parsed.append(Filter("text", token.casefold()))
    return parsed


def record_from_markdown(text: str) -> dict:
    """Proyección segura del nodo OKF necesaria para filtros, sin YAML dinámico."""
    if not isinstance(text, str):
        raise ValueError("nodo no es texto")
    if not text.startswith("---\n"):
        return {"body": text, "attachments": [], "_search_text": text}
    front, separator, body = text[4:].partition("\n---\n")
    if not separator:
        raise ValueError("nodo sin cierre de frontmatter")
    record = {"body": body, "attachments": [], "_search_text": text}
    for line in front.splitlines():
        key, marker, value = line.partition(":")
        if not marker:
            continue
        key, value = key.strip(), value.strip()
        if key == "attachments":
            record["attachments"] = [{}]
        elif key == "delivered_to":
            record[key] = [item.strip() for item in value.split(",") if item.strip()]
        else:
            record[key] = "" if value == '\"\"' else value
    return record


def _header_has(record, key, wanted):
    values = record.get(key, "")
    if not isinstance(values, (list, tuple, set)):
        values = [values]
    pattern = r"(?<!" + _EMAIL_BOUNDARY + r")" + re.escape(wanted) + r"(?!" + _EMAIL_BOUNDARY + r")"
    return any(re.search(pattern, str(value).casefold()) for value in values)


def record_matches(record: dict, filters: list[Filter]) -> bool:
    if not isinstance(record, dict):
        return False
    searchable = str(record.get("_search_text") or " ".join(
        str(record.get(key, "")) for key in ("subject", "body")
    )).casefold()
    delivered = {str(value).casefold() for value in record.get("delivered_to", [])}
    for item in filters:
        if item.kind == "text" and item.value not in searchable:
            return False
        if item.kind == "para" and item.value not in delivered:
            return False
        if item.kind in ("from", "to", "cc") and not _header_has(record, item.kind, item.value):
            return False
        if item.kind == "contact" and not any(_header_has(record, key, item.value) for key in ("from", "to", "cc")):
            return False
        if item.kind == "subject" and item.value not in str(record.get("subject", "")).casefold():
            return False
        if item.kind == "account" and item.value != str(record.get("account_id", "")).casefold():
            return False
        if item.kind == "date":
            try:
                actual = parsedate_to_datetime(str(record.get("date", ""))).date().isoformat()
            except (TypeError, ValueError, OverflowError):
                actual = str(record.get("date", ""))[:10]
            if actual != item.value:
                return False
        if item.kind == "is:reply" and not _is_reply(record):
            return False
        if item.kind == "has:attachment" and not record.get("attachments"):
            return False
        if item.kind == "conversation" and conversation_key(record).casefold() != item.value:
            return False
        if item.kind == "topic" and item.value not in {str(topic).casefold() for topic in extract_topics(record)}:
            return False
    return True


def _is_reply(record):
    """Reconoce headers canónicos y nodos legacy cuyo asunto inicia ``Re:``."""
    if record.get("in_reply_to") or record.get("references"):
        return True
    return str(record.get("subject", "")).lstrip().casefold().startswith("re:")
