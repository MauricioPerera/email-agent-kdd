"""Consulta del store Markdown (contrato query_email).

Parser lexico determinista: tokens por espacios; filtros `contact:EMAIL`,
`conversation:KEY`, `topic:TOPIC`, `account:ACCOUNT_ID`, `date:YYYY-MM-DD`,
`para:EMAIL` (via marcador `delivered_to` del frontmatter) y terminos libres,
combinados por AND (substring casefold sobre `.md` y los indices). Sin NLP,
sin red, sin ejecutar contenido: solo lectura. Los nodos e indices bajo
`root/.trash` (papelera de soft_delete) se excluyen de los resultados y nunca
se leen.
"""

import re
from pathlib import Path

TRASH_DIRNAME = ".trash"
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
            terms.append("contact:" + email)
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
        elif lowered.startswith("para:"):
            recipient = token[5:].strip().casefold()
            local, _, domain = recipient.partition("@")
            if not local or not domain:
                raise ValueError("para: EMAIL malformado (sin @ o partes vacias): " + token[5:])
            terms.append("delivered_to")
            terms.append(recipient)
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
        relative = candidate.relative_to(root_path)
        if relative.parts[0] == TRASH_DIRNAME:
            return None
        return relative.as_posix()
    return None


_DELIVERED_RE = re.compile(r"^delivered_to\s*:", re.IGNORECASE)
_CONTACT_HEADER_RE = re.compile(r"^(from|to|cc)\s*:", re.IGNORECASE)


def _delivered_to_match(text: str, value: str) -> bool:
    """Solo lineas `delivered_to:` del frontmatter; nunca cuerpo ni `to:`/`cc:`."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        if _DELIVERED_RE.match(line) and value in line.casefold():
            return True
    return closed


def _contact_header_match(text: str, value: str) -> bool:
    """Busca el email solo en From/To/Cc del frontmatter, nunca en cuerpo."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if _CONTACT_HEADER_RE.match(line) and value in line.casefold():
            return True
    return False


def _scan_terms(root_path: Path, terms: list) -> set:
    plain = [term.casefold() for term in terms if not term.startswith(("para:", "contact:"))]
    paras = [term[len("para:"):] for term in terms if term.startswith("para:")]
    contacts = [term[len("contact:"):] for term in terms if term.startswith("contact:")]
    matches = set()
    for path in sorted(root_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        if path.relative_to(root_path).parts[0] == TRASH_DIRNAME:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ValueError("archivo .md no leible como UTF-8: " + str(path))
        lowered = text.casefold()
        if not all(term in lowered for term in plain):
            continue
        if not all(_delivered_to_match(text, value) for value in paras):
            continue
        if not all(_contact_header_match(text, value) for value in contacts):
            continue
        matches.add(path.relative_to(root_path).as_posix())
    return matches


def query_email(root: str, instruction: str) -> list:
    root_path = _validate_root(root)
    terms, indexes = _parse_filters(instruction)
    results = _scan_terms(root_path, terms) if terms else None
    for index_rel in indexes:
        if index_rel.split("/", 1)[0] == TRASH_DIRNAME:
            return []
        entries = _read_index_entries(root_path / index_rel)
        if entries is None:
            return []
        node_set = {rel for raw in entries if (rel := _resolve_node(root_path, raw)) is not None}
        results = node_set if results is None else results & node_set
    return [] if results is None else sorted(results)
