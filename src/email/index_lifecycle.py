# -*- coding: utf-8 -*-
"""Ciclo de vida de rutas en los índices Markdown ya existentes.

Opera sobre los DOS formatos que ya producen ``persist_conversation_index`` y
``persist_topic_index`` (Conversation con ``conversation_key`` de 64 hex, Topic
con ``topic``), sin reinterpretar el frontmatter: lo conservan tal cual y solo
recalculan ``message_count``. Fusionan, deduplican y ordenan las rutas,
escriben de forma atómica y ELIMINAN el nodo cuando ``remove`` deja la lista
vacía. Cualquier desviación del formato (cabecera, cuerpo o
``message_count`` incoherente) falla con ``ValueError`` SIN escribir. Sin red,
sin secretos, sin tocar otros módulos.
"""

import os
import re
from pathlib import Path

_HEAD_RE = re.compile(
    r"\A---\ntype: (?P<kind>Conversation|Topic)\n"
    r"(?P<key>conversation_key: [0-9a-f]{64}\n|topic: [^\n]+\n)"
    r"message_count: (?P<count>\d+)\n---\n"
)


def _normalize_path(message_path) -> str:
    """Valida y normaliza una ruta de mensaje a separadores ``/``."""
    if not isinstance(message_path, str) or not message_path.strip():
        raise ValueError("message_path debe ser un str no vacio")
    if "\x00" in message_path:
        raise ValueError("message_path con byte nulo")
    normalized = message_path.replace("\\", "/")
    if any(part == ".." for part in normalized.split("/")):
        raise ValueError("message_path con path traversal")
    return normalized


def _parse(index_path: Path):
    """(kind, key_line, rutas normalizadas); ValueError si falta o corrupto."""
    try:
        text = index_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ValueError(f"indice inexistente: {index_path}") from error
    match = _HEAD_RE.match(text)
    if match is None:
        raise ValueError(f"indice con formato inesperado: {index_path}")
    lines = text[match.end():].splitlines(keepends=True)
    if not all(line.startswith("- ") and line.endswith("\n") for line in lines):
        raise ValueError(f"indice con cuerpo inesperado: {index_path}")
    paths = set()
    for line in lines:
        paths.add(_normalize_path(line[2:].rstrip("\n")))
    if int(match.group("count")) != len(lines):
        raise ValueError(f"message_count incoherente en el indice: {index_path}")
    return match.group("kind"), match.group("key"), paths


def _render(kind: str, key: str, paths) -> str:
    """Texto determinista del nodo para la lista ya ordenada y deduplicada."""
    head = f"---\ntype: {kind}\n{key}message_count: {len(paths)}\n---\n"
    return head + "".join(f"- {path}\n" for path in paths)


def _atomic_write(index_path: Path, text: str) -> None:
    """Escritura atómica: temporal en el mismo directorio + os.replace."""
    tmp = index_path.with_name(index_path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, index_path)
    finally:
        if tmp.exists():
            os.remove(tmp)


def _mutate(index_path, message_path, add: bool):
    """Aplica add/remove y devuelve (accion, rutas finales)."""
    if isinstance(index_path, str):
        if not index_path.strip():
            raise ValueError("index_path debe ser un str no vacio")
        index_path = Path(index_path)
    if not isinstance(index_path, Path):
        raise ValueError("index_path debe ser str o Path")
    target = _normalize_path(message_path)
    kind, key, paths = _parse(index_path)
    if add:
        if target in paths:
            return "noop", sorted(paths)
        paths.add(target)
        _atomic_write(index_path, _render(kind, key, sorted(paths)))
        return "updated", sorted(paths)
    if target not in paths:
        return "noop", sorted(paths)
    remaining = sorted(paths - {target})
    if remaining:
        _atomic_write(index_path, _render(kind, key, remaining))
        return "updated", remaining
    index_path.unlink()
    return "deleted", []


def add_path_to_markdown_index(index_path, message_path) -> int:
    """Añade ``message_path`` al índice y devuelve el ``message_count`` final.

    Exige un índice EXISTENTE con formato Conversation o Topic válido (sin él
    no hay frontmatter que conservar): ``ValueError`` si falta o está corrupto.
    Union deduplicada y orden lexicográfico; escritura atómica solo si cambia.
    """
    _, paths = _mutate(index_path, message_path, add=True)
    return len(paths)


def remove_path_from_markdown_index(index_path, message_path) -> bool:
    """Elimina ``message_path`` del índice; ``True`` si lo tocó, ``False`` si no.

    Si la ruta no está, el índice no existe o no cambia, no escribe nada. Si la
    eliminación deja la lista vacía, BORRA el archivo del índice.
    """
    if not isinstance(index_path, (str, Path)) or (
        isinstance(index_path, str) and not index_path.strip()
    ):
        raise ValueError("index_path debe ser str o Path no vacio")
    candidate = Path(index_path)
    if not candidate.exists():
        return False
    action, _ = _mutate(candidate, message_path, add=False)
    return action != "noop"