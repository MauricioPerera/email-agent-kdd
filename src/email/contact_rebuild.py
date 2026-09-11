# -*- coding: utf-8 -*-
"""Reconstrucción completa de la libreta de contactos desde el store activo.

Variante TOTAL de ``deletion._rebuild_contacts``: no fusiona con la libreta
previa, la REEMPLAZA a partir de UNICAMENTE los nodos activos de
``store/emails`` (nunca ``.trash``), sin leer índices (``store/conversations``,
``store/topics``) ni ningún otro `.md` fuera de ``store/emails``. Reutiliza la
lógica existente: ``contacts.extract_contacts`` (From, To, Cc, deduplicado por
email en minúsculas), ``contact_store._validate_contact`` (esquema exacto) y el
formato compacto de ``contact_store`` (``{"contacts": [...]}`` ordenado por
email, escritura atómica temporal + ``os.replace``).

El frontmatter OKF se lee como TEXTO (nunca se ejecuta contenido). Un nodo sin
frontmatter o sin cabeceras de contacto simplemente no aporta contactos; un
frontmatter corrupto, un nodo no UTF-8 o un contacto inválido lanza
``ValueError`` ANTES de escribir: ``contacts.json`` conserva su contenido
previo. Si no hay mensajes activos, deja ``contacts.json`` con ``contacts``
vacíos. Sin red, sin secretos.
"""

import tempfile
from pathlib import Path

from src.email.deletion import _contacts_from_node, _write_contacts_atomic
from src.email.node import _check_root

STORE_NAME = "contacts.json"
MESSAGES_DIRNAME = "store/emails"
TRASH_DIRNAME = ".trash"


def _is_active(node_path: Path, root_path: Path) -> bool:
    """True si el nodo no cae bajo ningún directorio `.trash` del store."""
    return TRASH_DIRNAME not in node_path.relative_to(root_path).parts


def _active_message_nodes(root_path: Path) -> list:
    """Nodos `.md` activos bajo `store/emails`, ordenados lexicográficamente.

    Excluye cualquier nodo bajo un directorio `.trash` (el de `root` y
    los anidados como `store/emails/.trash`) y solo acepta archivos
    regulares con extensión final `.md`: los índices viven fuera de
    `store/emails` y por tanto nunca se leen.
    """
    messages_dir = root_path / MESSAGES_DIRNAME
    if not messages_dir.is_dir():
        return []
    nodes = []
    for node_path in sorted(messages_dir.rglob("*.md")):
        if not node_path.is_file() or not _is_active(node_path, root_path):
            continue
        nodes.append(node_path)
    return nodes


def rebuild_contacts_from_store(root: str) -> list:
    """Reconstruye `<root>/contacts.json` desde SOLO los mensajes activos.

    Recorre `store/emails/**/*.md` activo (nunca `.trash`, nunca índices),
    extrae From/To/Cc del frontmatter OKF con la lógica de
    ``src.email.contacts``, deduplica por email (gana la primera aparición,
    es decir el nodo lexicográficamente menor) y escribe la libreta de forma
    atómica con el formato de ``contact_store``. Devuelve la lista final
    ordenada. Ante un nodo corrupto lanza ``ValueError`` SIN tocar
    ``contacts.json``; si no hay mensajes activos la deja con ``contacts``
    vacíos.
    """
    root_path = _check_root(root)
    merged = {}
    for node_path in _active_message_nodes(root_path):
        for contact in _contacts_from_node(node_path):
            merged.setdefault(contact["email"], contact)
    ordered = [merged[email] for email in sorted(merged)]
    _write_contacts_atomic(root_path / STORE_NAME, ordered)
    return ordered