# -*- coding: utf-8 -*-
"""Índice de conversaciones del store: nodo Markdown con las rutas del hilo.

La clave SIEMPRE sale de ``src.email.conversation.conversation_key``; este
módulo solo valida entradas, fusiona rutas y escribe el nodo de forma atómica.
No clasifica temas y no persiste nada del contenido del mensaje.
"""
import os
import re
from pathlib import Path

from src.email.conversation import conversation_key

_HEAD_RE = re.compile(
    r"\A---\ntype: Conversation\nconversation_key: ([0-9a-f]{64})\n"
    r"message_count: (\d+)\n---\n"
)


def _normalize(message_path: str) -> str:
    """Valida y normaliza ``message_path`` a separadores ``/``."""
    if not isinstance(message_path, str) or not message_path.strip():
        raise ValueError("message_path vacío")
    if "\x00" in message_path:
        raise ValueError("message_path con byte nulo")
    normalized = message_path.replace("\\", "/")
    if any(part == ".." for part in normalized.split("/")):
        raise ValueError("message_path con path traversal")
    return normalized


def _existing_paths(node: Path) -> set:
    """Entradas válidas del nodo existente; ValueError si el formato difiere."""
    text = node.read_text(encoding="utf-8")
    match = _HEAD_RE.match(text)
    if match is None:
        raise ValueError(f"nodo de conversación con formato inesperado: {node}")
    lines = text[match.end():].splitlines(keepends=True)
    if not all(line.startswith("- ") and line.endswith("\n") for line in lines):
        raise ValueError(f"nodo de conversación con cuerpo inesperado: {node}")
    if int(match.group(2)) != len(lines):
        raise ValueError(f"message_count incoherente en el nodo: {node}")
    return {line[2:].rstrip("\n") for line in lines}


def _render(key: str, paths: list) -> str:
    """Texto del nodo determinista para la lista ya ordenada y deduplicada."""
    head = (
        f"---\ntype: Conversation\nconversation_key: {key}\n"
        f"message_count: {len(paths)}\n---\n"
    )
    return head + "".join(f"- {path}\n" for path in paths)


def _atomic_write(node: Path, text: str) -> None:
    """Escritura atómica: temporal en el mismo directorio + os.replace."""
    tmp = node.with_name(node.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, node)
    finally:
        if tmp.exists():
            os.remove(tmp)


def persist_conversation_index(root: str, record: dict, message_path: str) -> str:
    """Persiste/actualiza ``root/store/conversations/<key>.md`` y devuelve su ruta absoluta.

    Fusiona el nodo existente sin perder mensajes: unión, deduplicación y
    orden lexicográfico ascendente de las rutas normalizadas.
    """
    if not isinstance(root, str) or not root.strip() or not Path(root).is_dir():
        raise ValueError("root debe ser un directorio existente")
    if not isinstance(record, dict):
        raise ValueError("record debe ser dict")
    normalized = _normalize(message_path)
    key = conversation_key(record)
    node = Path(root) / "store" / "conversations" / f"{key}.md"
    node.parent.mkdir(parents=True, exist_ok=True)
    paths = {normalized}
    if node.exists():
        paths.update(_existing_paths(node))
    _atomic_write(node, _render(key, sorted(paths)))
    return str(node.resolve())