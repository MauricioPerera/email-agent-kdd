"""Tests congelados end-to-end del Sprint 1: borrado reversible + indices + contactos.

Integra las APIs actuales de ``src.email.deletion`` (``soft_delete``/``restore``),
``src.email.query`` (``query_email``), ``src.email.search``
(``search_email_nodes``) y ``src.email.contact_rebuild``
(``rebuild_contacts_from_store``) sobre un store real construido en tmp_path:
dos nodos OKF bajo ``store/emails`` que comparten conversacion y tema, y sus
indices en ``store/conversations`` y ``store/topics``. Verifica el ciclo
completo de vida: exclusion de query/search al borrar, retiro de SOLO la ruta
del nodo borrado, conservacion de contactos compartidos, reincorporacion al
restaurar, vaciado de indices y de contactos exclusivos al borrar el ultimo,
y recreacion completa al restaurar el final. Ademas: conflicto de destino
(restore nunca sobrescribe) y corrupcion de indice, frontmatter, manifiesto y
``contacts.json`` que abortan SIN destruir datos. Sin red, sin secretos,
sin CLI.
"""

import json
import tempfile
from pathlib import Path

from src.email.contact_rebuild import rebuild_contacts_from_store
from src.email.deletion import list_trash, restore, soft_delete
from src.email.query import query_email
from src.email.search import search_email_nodes

KEY = "a1b2c3d4" * 8  # 64 hex chars, conversation_key valido
TOPIC = "presupuesto"
NODE_A = "store/emails/msg-a.md"
NODE_B = "store/emails/msg-b.md"
TRASH_A = ".trash/" + NODE_A
MANIFEST_A = TRASH_A + ".json"
TRASH_B = ".trash/" + NODE_B
CONV_INDEX = "store/conversations/" + KEY + ".md"
TOPIC_INDEX = "store/topics/" + TOPIC + ".md"

_NODE_A_TEXT = (
    "---\n"
    "type: Email Message\n"
    "from: Ana Rivera <ana@ejemplo.com>\n"
    "to: Beto Lopez <beto@ejemplo.com>\n"
    "cc: Cati Diaz <cati@ejemplo.com>\n"
    "conversation_key: " + KEY + "\n"
    "topic: " + TOPIC + "\n"
    "subject: Presupuesto 2026\n"
    "---\n"
    "Cuerpo del mensaje A con cifras2026.\n"
)
_NODE_B_TEXT = (
    "---\n"
    "type: Email Message\n"
    "from: Zulma Ortiz <zulma@ejemplo.com>\n"
    "to: Beto Lopez <beto@ejemplo.com>\n"
    "conversation_key: " + KEY + "\n"
    "topic: " + TOPIC + "\n"
    "subject: Presupuesto 2026\n"
    "---\n"
    "Cuerpo del mensaje B con cifras2026.\n"
)
ALL_CONTACTS = {"ana@ejemplo.com", "beto@ejemplo.com", "cati@ejemplo.com", "zulma@ejemplo.com"}


def _build_index(kind, key_line, paths):
    head = "---\ntype: " + kind + "\n" + key_line + "message_count: "
    return head + "{0}\n---\n".format(len(paths)) + "".join(
        "- " + path + "\n" for path in sorted(paths)
    )


def _build_store(tmp):
    """Dos nodos OKF con la misma conversacion/tema y contactos compartidos,
    sus indices y la libreta de contactos reconstruida con la API real."""
    for rel_path, text in ((NODE_A, _NODE_A_TEXT), (NODE_B, _NODE_B_TEXT)):
        target = Path(tmp) / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for rel_path, text in (
        (CONV_INDEX, _build_index("Conversation", "conversation_key: " + KEY + "\n", (NODE_A, NODE_B))),
        (TOPIC_INDEX, _build_index("Topic", "topic: " + TOPIC + "\n", (NODE_A, NODE_B))),
    ):
        target = Path(tmp) / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    rebuild_contacts_from_store(tmp)
    return Path(tmp)


def _contacts_emails(tmp):
    payload = json.loads((Path(tmp) / "contacts.json").read_text(encoding="utf-8"))
    return sorted(entry["email"] for entry in payload["contacts"])


def _index_paths(tmp, index_rel):
    text = (Path(tmp) / index_rel).read_text(encoding="utf-8")
    paths = sorted(line[2:] for line in text.splitlines() if line.startswith("- "))
    count = int(next(line for line in text.splitlines() if line.startswith("message_count: ")).split(":")[1])
    assert count == len(paths), "message_count incoherente en " + index_rel
    return paths


def test_end_to_end_soft_delete_restore_full_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        _build_store(tmp)
        # --- ANTES: ambos aparecen en query, search y en ambos indices.
        assert query_email(tmp, "conversation:" + KEY) == [NODE_A, NODE_B]
        assert query_email(tmp, "topic:" + TOPIC) == [NODE_A, NODE_B]
        assert query_email(tmp, "contact:beto@ejemplo.com") == [NODE_A, NODE_B]
        assert search_email_nodes(tmp, "cifras2026") == [NODE_A, NODE_B]
        assert _index_paths(tmp, CONV_INDEX) == [NODE_A, NODE_B]
        assert _index_paths(tmp, TOPIC_INDEX) == [NODE_A, NODE_B]
        assert _contacts_emails(tmp) == sorted(ALL_CONTACTS)

        # --- SOFT_DELETE del primero: se mueve, se excluye de query/search,
        # se retira SOLO su ruta de ambos indices y se conservan los
        # contactos que usa el otro nodo.
        manifest = soft_delete(tmp, NODE_A)
        assert not (Path(tmp) / NODE_A).exists()
        assert (Path(tmp) / TRASH_A).is_file()
        assert set(manifest["index_snapshots"]) == {CONV_INDEX, TOPIC_INDEX}
        assert json.loads(manifest["contacts_snapshot"])["contacts"] and sorted(
            entry["email"] for entry in json.loads(manifest["contacts_snapshot"])["contacts"]
        ) == sorted(ALL_CONTACTS)
        assert query_email(tmp, "conversation:" + KEY) == [NODE_B]
        assert query_email(tmp, "topic:" + TOPIC) == [NODE_B]
        assert query_email(tmp, "contact:beto@ejemplo.com") == [NODE_B]
        assert query_email(tmp, "contact:ana@ejemplo.com") == []
        assert search_email_nodes(tmp, "cifras2026") == [NODE_B]
        # Solo su ruta: el indice vive y conserva exactamente la del otro.
        assert _index_paths(tmp, CONV_INDEX) == [NODE_B]
        assert _index_paths(tmp, TOPIC_INDEX) == [NODE_B]
        # Contactos: el compartido (beto) sobrevive; los exclusivos de A no.
        assert _contacts_emails(tmp) == ["beto@ejemplo.com", "zulma@ejemplo.com"]
        assert [item["rel_path"] for item in list_trash(tmp)] == [NODE_A]

        # --- RESTORE: el nodo vuelve, se reincorporan indices y contactos.
        restored = restore(tmp, MANIFEST_A)
        assert restored["rel_path"] == NODE_A
        assert (Path(tmp) / NODE_A).read_text(encoding="utf-8") == _NODE_A_TEXT
        assert not (Path(tmp) / TRASH_A).exists()
        assert list_trash(tmp) == []
        assert query_email(tmp, "conversation:" + KEY) == [NODE_A, NODE_B]
        assert query_email(tmp, "topic:" + TOPIC) == [NODE_A, NODE_B]
        assert query_email(tmp, "contact:ana@ejemplo.com") == [NODE_A]
        assert search_email_nodes(tmp, "cifras2026") == [NODE_A, NODE_B]
        assert _index_paths(tmp, CONV_INDEX) == [NODE_A, NODE_B]
        assert _index_paths(tmp, TOPIC_INDEX) == [NODE_A, NODE_B]
        assert _contacts_emails(tmp) == sorted(ALL_CONTACTS)

        # --- SOFT_DELETE del ultimo: los indices quedan vacios (se eliminan)
        # y los contactos exclusivos desaparecen (libreta vacia).
        soft_delete(tmp, NODE_A)
        soft_delete(tmp, NODE_B)
        assert not (Path(tmp) / CONV_INDEX).exists(), (
            "el indice de conversacion sin rutas se elimina"
        )
        assert not (Path(tmp) / TOPIC_INDEX).exists(), (
            "el indice de tema sin rutas se elimina"
        )
        assert query_email(tmp, "conversation:" + KEY) == []
        assert query_email(tmp, "topic:" + TOPIC) == []
        assert search_email_nodes(tmp, "cifras2026") == []
        assert (Path(tmp) / "contacts.json").is_file()
        assert _contacts_emails(tmp) == []
        assert [item["rel_path"] for item in list_trash(tmp)] == [NODE_A, NODE_B]

        # --- RESTORE final: nodos, indices (con AMBAS rutas y conteo) y
        # contactos se recrean completos.
        restore(tmp, TRASH_A)
        restore(tmp, TRASH_B)
        assert (Path(tmp) / NODE_A).is_file() and (Path(tmp) / NODE_B).is_file()
        assert list_trash(tmp) == []
        assert query_email(tmp, "conversation:" + KEY) == [NODE_A, NODE_B]
        assert query_email(tmp, "topic:" + TOPIC) == [NODE_A, NODE_B]
        assert search_email_nodes(tmp, "cifras2026") == [NODE_A, NODE_B]
        assert _index_paths(tmp, CONV_INDEX) == [NODE_A, NODE_B]
        assert _index_paths(tmp, TOPIC_INDEX) == [NODE_A, NODE_B]
        assert _contacts_emails(tmp) == sorted(ALL_CONTACTS)


def test_restore_conflict_refuses_to_overwrite_and_no_data_lost():
    with tempfile.TemporaryDirectory() as tmp:
        _build_store(tmp)
        soft_delete(tmp, NODE_A)
        conv_after_delete = _index_paths(tmp, CONV_INDEX)
        # Conflicto: alguien creo un nodo distinto en la ruta original.
        (Path(tmp) / NODE_A).write_text("nodo nuevo que no se pierde\n", encoding="utf-8")
        try:
            restore(tmp, TRASH_A)
        except ValueError:
            pass
        else:
            raise AssertionError("restore no debe sobrescribir un destino existente")
        # El conflicto intacto, el elemento sigue en .trash con su manifiesto.
        assert (Path(tmp) / NODE_A).read_text(encoding="utf-8") == (
            "nodo nuevo que no se pierde\n"
        )
        assert (Path(tmp) / TRASH_A).is_file()
        assert [item["rel_path"] for item in list_trash(tmp)] == [NODE_A]
        assert _index_paths(tmp, CONV_INDEX) == conv_after_delete
        assert _contacts_emails(tmp) == ["beto@ejemplo.com", "zulma@ejemplo.com"]
        # Retirado el conflicto, restore funciona sin perder nada.
        (Path(tmp) / NODE_A).unlink()
        restore(tmp, TRASH_A)
        assert (Path(tmp) / NODE_A).read_text(encoding="utf-8") == _NODE_A_TEXT
        assert _index_paths(tmp, CONV_INDEX) == [NODE_A, NODE_B]
        assert _contacts_emails(tmp) == sorted(ALL_CONTACTS)


def test_corrupt_index_aborts_soft_delete_without_destroying_data():
    with tempfile.TemporaryDirectory() as tmp:
        _build_store(tmp)
        (Path(tmp) / TOPIC_INDEX).write_text("no es un indice\n", encoding="utf-8")
        try:
            soft_delete(tmp, NODE_A)
        except ValueError:
            pass
        else:
            raise AssertionError("un indice corrupto debe abortar soft_delete")
        assert (Path(tmp) / NODE_A).is_file(), "el mensaje no se mueve"
        assert not (Path(tmp) / ".trash").exists(), "no se crea papelera"
        assert _index_paths(tmp, CONV_INDEX) == [NODE_A, NODE_B], (
            "el indice sano queda intacto"
        )
        assert _contacts_emails(tmp) == sorted(ALL_CONTACTS)


def test_corrupt_frontmatter_aborts_soft_delete_without_destroying_data():
    with tempfile.TemporaryDirectory() as tmp:
        _build_store(tmp)
        contacts_before = (Path(tmp) / "contacts.json").read_text(encoding="utf-8")
        (Path(tmp) / NODE_B).write_text(
            "---\nfrom: Zulma <zulma@ejemplo.com>\nlinea sin dos puntos\n",
            encoding="utf-8",
        )
        try:
            soft_delete(tmp, NODE_A)
        except ValueError:
            pass
        else:
            raise AssertionError(
                "frontmatter corrupto en otro nodo activo debe abortar soft_delete"
            )
        assert (Path(tmp) / NODE_A).is_file(), "el mensaje objetivo no se mueve"
        assert not (Path(tmp) / ".trash").exists(), "no se crea papelera"
        assert (Path(tmp) / "contacts.json").read_text(encoding="utf-8") == (
            contacts_before
        ), "contacts.json queda intacto"
        assert _index_paths(tmp, TOPIC_INDEX) == [NODE_A, NODE_B]


def test_corrupt_contacts_aborts_soft_delete_without_destroying_data():
    with tempfile.TemporaryDirectory() as tmp:
        _build_store(tmp)
        (Path(tmp) / "contacts.json").write_bytes(b"\xff\xfe-no-utf8")
        try:
            soft_delete(tmp, NODE_A)
        except ValueError:
            pass
        else:
            raise AssertionError("contacts.json no UTF-8 debe abortar soft_delete")
        assert (Path(tmp) / NODE_A).is_file()
        assert not (Path(tmp) / ".trash").exists()
        assert _index_paths(tmp, CONV_INDEX) == [NODE_A, NODE_B]


def test_corrupt_manifest_aborts_restore_without_destroying_data():
    with tempfile.TemporaryDirectory() as tmp:
        _build_store(tmp)
        soft_delete(tmp, NODE_A)
        manifest_text = (Path(tmp) / MANIFEST_A).read_text(encoding="utf-8")
        conv_after_delete = _index_paths(tmp, CONV_INDEX)
        contacts_after_delete = (Path(tmp) / "contacts.json").read_text(encoding="utf-8")
        (Path(tmp) / MANIFEST_A).write_text("{ manifiesto roto", encoding="utf-8")
        try:
            restore(tmp, TRASH_A)
        except ValueError:
            pass
        else:
            raise AssertionError("un manifiesto ilegible debe abortar restore")
        assert (Path(tmp) / TRASH_A).is_file(), "el elemento sigue en .trash"
        assert not (Path(tmp) / NODE_A).exists(), "no aparece en el original"
        assert _index_paths(tmp, CONV_INDEX) == conv_after_delete
        assert (Path(tmp) / "contacts.json").read_text(encoding="utf-8") == (
            contacts_after_delete
        )
        # Reparado el manifiesto (texto original), restore vuelve a funcionar.
        (Path(tmp) / MANIFEST_A).write_text(manifest_text, encoding="utf-8")
        restore(tmp, TRASH_A)
        assert (Path(tmp) / NODE_A).read_text(encoding="utf-8") == _NODE_A_TEXT
        assert _index_paths(tmp, CONV_INDEX) == [NODE_A, NODE_B]