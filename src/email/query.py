"""Consulta del store Markdown (contrato query_email).

Parser lexico determinista: tokens por espacios; filtros `contact:EMAIL`,
`conversation:KEY`, `topic:TOPIC`, `account:ACCOUNT_ID`, `date:YYYY-MM-DD`
y terminos libres, combinados por AND (substring casefold sobre `.md` y los
indices). Sin NLP, sin red, sin ejecutar contenido: solo lectura.
"""

import re
from pathlib import Path

_CONVERSATION_RE = re.compile(r"^[0-9a-f]{64}$")
_TOPIC_RE = re.compile(r"^\w{1,64}$")
_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_root(root: str) -> Path:
    if not isinstance(root, str) or not root or not Path(root).is_dir():
        raise ValueError("root invalido (str no vacio y directorio existente): " + str(root))
    return Path(root).resolve()


def _parse_filters(instruction: str):
    if not isinstance(instruction, str):
        raise ValueError("instruction debe ser str")
    tokens = instruction.split()
    if not tokens:
        raise ValueError("instruction sin criterios tras normalizar espacios")
    terms = []
    indexes = []
    for token in tokens:
        lowered = token.lower()
        if lowered.startswith("contact:"):
            email = token[8:].strip().lower()
            local, _, domain = email.partition("@")
            if not local or not domain:
                raise ValueError("contact: EMAIL malformado (sin @ o partes vacias): " + token[8:])
            terms.append(email)
        elif lowered.startswith("conversation:"):
            key = token[13:].strip().lower()
            if not _CONVERSATION_RE.match(key):
                raise ValueError("conversation: KEY no es hex-64: " + token[13:])
            indexes.append("store/conversations/" + key + ".md")
        elif lowered.startswith("topic:"):
            topic = token[6:].strip().lower()
            if not _TOPIC_RE.match(topic):
                raise ValueError("topic: TOPIC inseguro (requiere ^\\w{1,64}$): " + token[6:])
            indexes.append("store/topics/" + topic + ".md")
        elif lowered.startswith("account:"):
            account = token[8:].strip()
            if not _ACCOUNT_RE.match(account):
                raise ValueError("account: ACCOUNT_ID inseguro (^[A-Za-z0-9_.-]{1,64}$): " + token[8:])
            terms.append(account.casefold())
        elif lowered.startswith("date:"):
            date = token[5:].strip()
            if not _DATE_RE.match(date):
                raise ValueError("date: DATE fuera del formato estricto YYYY-MM-DD: " + token[5:])
            terms.append(date.casefold())
        else:
            terms.append(token.casefold())
    return terms, indexes


def _read_index_entries(index_path: Path):
    try:
        text = index_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        raise ValueError("archivo .md no leible como UTF-8: " + str(index_path))
    return [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]


def _resolve_node(root_path: Path, raw: str):
    candidate = (root_path / raw).resolve()
    if candidate.is_relative_to(root_path) and candidate.suffix.lower() == ".md" and candidate.is_file():
        return candidate.relative_to(root_path).as_posix()
    return None


def _scan_terms(root_path: Path, terms: list) -> set:
    lowered_terms = [term.casefold() for term in terms]
    matches = set()
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        try:
            lowered = path.read_text(encoding="utf-8").casefold()
        except UnicodeDecodeError:
            raise ValueError("archivo .md no leible como UTF-8: " + str(path))
        if all(term in lowered for term in lowered_terms):
            matches.add(path.relative_to(root_path).as_posix())
    return matches


def query_email(root: str, instruction: str) -> list:
    root_path = _validate_root(root)
    terms, indexes = _parse_filters(instruction)
    results = _scan_terms(root_path, terms) if terms else None
    for index_rel in indexes:
        entries = _read_index_entries(root_path / index_rel)
        if entries is None:
            return []
        node_set = {rel for raw in entries if (rel := _resolve_node(root_path, raw)) is not None}
        results = node_set if results is None else results & node_set
    return [] if results is None else sorted(results)