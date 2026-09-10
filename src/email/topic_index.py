"""Índice Markdown de temas: <root>/store/topics/<topic>.md.

Delega la obtención de temas en ``src.email.topics.extract_topics``; este módulo
solo valida, fusiona y escribe nodos atómicamente. No tokeniza ni interpreta
claves del ``record``; sin red, sin mutar la entrada, sin secretos.
"""

import os
import re
from pathlib import Path

from src.email.topics import extract_topics

_TOPIC_RE = re.compile(r"^\w{1,64}$", re.UNICODE)


def _validated(root, record, message_path):
    """Valida los argumentos y devuelve ``root`` como Path; ValueError si falla."""
    if not isinstance(root, str) or not root or not Path(root).is_dir():
        raise ValueError("root debe ser la ruta de un directorio existente")
    if not isinstance(record, dict):
        raise ValueError("record debe ser un dict")
    if (
        not isinstance(message_path, str)
        or not message_path.strip()
        or "\x00" in message_path
    ):
        raise ValueError("message_path debe ser un str no vacio y sin NUL")
    return Path(root)


def _is_safe(topic):
    """True si el tema es un único componente de fichero válido."""
    return (
        bool(_TOPIC_RE.match(topic))
        and "/" not in topic
        and "\\" not in topic
        and ".." not in topic
        and "\x00" not in topic
    )


def _render(topic, paths):
    """Texto determinista del nodo: frontmatter + entradas ordenadas."""
    head = (
        f"---\ntype: Topic\ntopic: {topic}\n"
        f"message_count: {len(paths)}\n---\n"
    )
    return head + "".join(f"- {p}\n" for p in paths)


def _load_entries(node, topic):
    """Entradas válidas del nodo existente; [] si falta; ValueError si no matchea."""
    try:
        text = node.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    head, sep, body = text.partition("\n---\n")
    if not text.startswith("---\n") or not sep:
        raise ValueError(f"nodo sin frontmatter de Topic: {node}")
    if not head.startswith(f"---\ntype: Topic\ntopic: {topic}\nmessage_count: "):
        raise ValueError(f"nodo no coincide con el tema {topic!r}: {node}")
    entries = []
    for line in body.splitlines():
        if not line.startswith("- "):
            raise ValueError(f"nodo sin entradas '- <path>': {node}")
        entries.append(line[2:])
    return entries


def _write_atomic(node, text):
    """Escritura atómica en el mismo directorio con os.replace."""
    tmp = node.with_name(node.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, node)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def persist_topic_index(root: str, record: dict, message_path: str) -> int:
    """Crea o actualiza el nodo Markdown de cada tema seguro del ``record``.

    Fusiona (unión deduplicada y ordenada) las rutas ya registradas con
    ``message_path`` y devuelve el número de temas seguros procesados.
    """
    root_dir = _validated(root, record, message_path)
    safe = [t for t in dict.fromkeys(extract_topics(record)) if _is_safe(t)]
    if not safe:
        return 0
    topics_dir = root_dir / "store" / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    path = message_path.replace("\\", "/")
    for topic in safe:
        node = topics_dir / f"{topic}.md"
        entries = sorted(set(_load_entries(node, topic)) | {path})
        _write_atomic(node, _render(topic, entries))
    return len(safe)