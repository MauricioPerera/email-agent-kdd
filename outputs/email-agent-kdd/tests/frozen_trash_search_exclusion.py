"""Tests congelados de exclusion de .trash en query_email y search_email_nodes.

Verifica que cualquier archivo o indice bajo `root/.trash` (papelera de
soft_delete) quede fuera de los resultados y NUNCA se lea. La prueba fuerte
usa bytes UTF-8 invalidos dentro de .trash: si el target los leyera, romperia
con UnicodeDecodeError en lugar de devolver el resultado esperado.
"""

import pytest

from src.email.query import query_email
from src.email.search import search_email_nodes

_ACTIVE_NODE = (
    "---\ntype: Email Message\n"
    "from: ana@example.com\n"
    "delivered_to: ana@example.com\n"
    "---\nFactura de septiembre con total pendiente\n"
)
_TERM = "factura"
_CONV_KEY = "ab" * 32
# Contenido NO UTF-8: leerlo es un fallo, ignorarlo es obligatorio.
_NOT_UTF8 = b"\xff\xfe- store/emails/msg-0001.md\n"


def _write_tree(root, tree):
    for rel, content in tree.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


def _tree():
    return {
        # Nodo activo.
        "store/emails/msg-0001.md": _ACTIVE_NODE,
        # Copia identica dentro de .trash (misma ruta relativa).
        ".trash/store/emails/msg-0001.md": _ACTIVE_NODE,
        # Otro .md en .trash con bytes invalidos: si se lee, explota.
        ".trash/store/emails/msg-0002.md": _NOT_UTF8,
        # Indice de tema y conversacion dentro de .trash: no debe leerse.
        ".trash/store/topics/factura.md": _NOT_UTF8,
        ".trash/store/conversations/" + _CONV_KEY + ".md": _NOT_UTF8,
        # Indice dentro de .trash que lista el nodo activo: no debe leerse.
        ".trash/store/topics/otro.md": "- store/emails/msg-0001.md\n",
        "store/notes/nota.md": "nota sin el termino buscado",
    }


def test_search_excludes_identical_trash_node(tmp_path):
    _write_tree(tmp_path, _tree())
    assert search_email_nodes(str(tmp_path), _TERM) == ["store/emails/msg-0001.md"]


def test_search_returns_empty_when_only_trash_matches(tmp_path):
    tree = _tree()
    del tree["store/emails/msg-0001.md"]
    del tree["store/notes/nota.md"]
    _write_tree(tmp_path, tree)
    assert search_email_nodes(str(tmp_path), _TERM) == []


def test_query_free_term_excludes_identical_trash_node(tmp_path):
    _write_tree(tmp_path, _tree())
    assert query_email(str(tmp_path), _TERM) == ["store/emails/msg-0001.md"]


def test_query_topic_index_in_trash_is_never_read(tmp_path):
    tree = _tree()
    tree["store/topics/factura.md"] = "- store/emails/msg-0001.md\n"
    _write_tree(tmp_path, tree)
    assert query_email(str(tmp_path), "topic:factura") == [
        "store/emails/msg-0001.md"
    ]


def test_query_topic_only_in_trash_returns_empty_without_reading(tmp_path):
    # Sin indice activo y con el indice SOLO en .trash: no se lee y no revienta.
    _write_tree(tmp_path, _tree())
    assert query_email(str(tmp_path), "topic:factura") == []


def test_query_conversation_index_in_trash_is_never_read(tmp_path):
    _write_tree(tmp_path, _tree())
    assert query_email(str(tmp_path), "conversation:" + _CONV_KEY) == []


def test_query_index_entry_resolving_into_trash_is_excluded(tmp_path):
    tree = _tree()
    tree["store/topics/factura.md"] = (
        "- store/emails/msg-0001.md\n- .trash/store/emails/msg-0002.md\n"
    )
    _write_tree(tmp_path, tree)
    assert query_email(str(tmp_path), "topic:factura") == [
        "store/emails/msg-0001.md"
    ]


def test_query_filters_still_work_without_trash(tmp_path):
    tree = _tree()
    del tree[".trash/store/emails/msg-0001.md"]
    del tree[".trash/store/emails/msg-0002.md"]
    tree["store/topics/factura.md"] = "- store/emails/msg-0001.md\n"
    _write_tree(tmp_path, tree)
    assert query_email(str(tmp_path), "topic:factura") == [
        "store/emails/msg-0001.md"
    ]
    assert query_email(str(tmp_path), "contact:ana@example.com " + _TERM) == [
        "store/emails/msg-0001.md"
    ]
    assert search_email_nodes(str(tmp_path), _TERM) == [
        "store/emails/msg-0001.md"
    ]


def test_search_invalid_root_still_raises(tmp_path):
    with pytest.raises(ValueError):
        search_email_nodes(str(tmp_path / "no-existe"), _TERM)
    with pytest.raises(ValueError):
        search_email_nodes(str(tmp_path), "   ")