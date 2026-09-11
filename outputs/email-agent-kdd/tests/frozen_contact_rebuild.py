# -*- coding: utf-8 -*-
"""Tests congelados de rebuild_contacts_from_store (contact_rebuild).

Cubre contactos compartidos (gana el nombre de la primera aparición) y
exclusivos, extracción From/To/Cc del frontmatter OKF sin ejecutar contenido,
exclusión de `.trash`, orden estable e idempotencia, rechazo de nodo corrupto
sin sobrescribir contacts.json existente y escritura atómica (temporal en el
mismo directorio + os.replace, sin residuos).
"""

import os

import pytest

from src.email.contact_rebuild import rebuild_contacts_from_store
from src.email.contact_store import load_email_contacts


def _node(from_value="", to_value="", cc_value="", subject="Hola"):
    lines = [
        "---",
        "type: Email Message",
        "account_id: acc1",
        "subject: " + subject,
    ]
    lines.append("from: " + (from_value or '""'))
    lines.append("to: " + (to_value or '""'))
    if cc_value:
        lines.append("cc: " + cc_value)
    lines.append("date: 2026-09-10T00:00:00Z")
    lines.append("raw_sha256: " + "ab" * 32)
    lines.append("---")
    return "\n".join(lines) + "\ncuerpo del mensaje\n"


def _write_message(root, rel_path, text):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_shared_contact_reuses_first_name_and_exclusives_are_kept(tmp_path):
    _write_message(
        tmp_path,
        "store/emails/msg-0002.md",
        _node(from_value="Copia <copia@ejemplo.com>", to_value="Beto <beto@ejemplo.com>"),
    )
    _write_message(
        tmp_path,
        "store/emails/msg-0001.md",
        _node(
            from_value="Beto Perez <beto@ejemplo.com>",
            cc_value="Carla <carla@ejemplo.com>, Ana <ana@ejemplo.com>",
        ),
    )
    result = rebuild_contacts_from_store(str(tmp_path))
    assert result == [
        {"name": "Ana", "email": "ana@ejemplo.com"},
        {"name": "Beto Perez", "email": "beto@ejemplo.com"},
        {"name": "Carla", "email": "carla@ejemplo.com"},
        {"name": "Copia", "email": "copia@ejemplo.com"},
    ]
    assert load_email_contacts(str(tmp_path)) == result


def test_contacts_are_sorted_by_email_and_rebuild_is_stable(tmp_path):
    _write_message(
        tmp_path,
        "store/emails/z.md",
        _node(to_value="Zoe <zoe@ejemplo.com>, Ana <ana@ejemplo.com>"),
    )
    _write_message(
        tmp_path,
        "store/emails/a.md",
        _node(from_value="Marta <marta@ejemplo.com>"),
    )
    first = rebuild_contacts_from_store(str(tmp_path))
    stored = tmp_path / "contacts.json"
    snapshot = stored.read_text(encoding="utf-8")
    assert [contact["email"] for contact in first] == [
        "ana@ejemplo.com",
        "marta@ejemplo.com",
        "zoe@ejemplo.com",
    ]
    assert snapshot.endswith("\n")
    assert snapshot == (
        '{"contacts": [{"email": "ana@ejemplo.com", "name": "Ana"}, '
        '{"email": "marta@ejemplo.com", "name": "Marta"}, '
        '{"email": "zoe@ejemplo.com", "name": "Zoe"}]}\n'
    )
    assert rebuild_contacts_from_store(str(tmp_path)) == first
    assert stored.read_text(encoding="utf-8") == snapshot


def test_trash_nodes_and_indexes_are_ignored(tmp_path):
    _write_message(
        tmp_path,
        "store/emails/msg-0001.md",
        _node(from_value="Viva <viva@ejemplo.com>"),
    )
    _write_message(
        tmp_path,
        "store/emails/.trash/msg-0001.md",
        _node(from_value="Borrado <borrado@ejemplo.com>"),
    )
    _write_message(
        tmp_path,
        ".trash/store/emails/viejo.md",
        _node(from_value="Viejo <viejo@ejemplo.com>"),
    )
    _write_message(
        tmp_path,
        "store/emails/notas.txt",
        "from: Otro <otro@ejemplo.com>\n",
    )
    _write_message(
        tmp_path,
        "store/conversations/conv.md",
        _node(from_value="Indice <indice@ejemplo.com>"),
    )
    result = rebuild_contacts_from_store(str(tmp_path))
    assert result == [{"name": "Viva", "email": "viva@ejemplo.com"}]


def test_empty_store_writes_empty_contacts(tmp_path):
    assert rebuild_contacts_from_store(str(tmp_path)) == []
    assert (tmp_path / "contacts.json").read_text(encoding="utf-8") == '{"contacts": []}\n'


def test_corrupt_node_is_rejected_without_overwriting_contacts(tmp_path):
    _write_message(
        tmp_path,
        "store/emails/msg-0001.md",
        _node(from_value="Viva <viva@ejemplo.com>"),
    )
    assert rebuild_contacts_from_store(str(tmp_path)) == [
        {"name": "Viva", "email": "viva@ejemplo.com"}
    ]
    for corrupt in (
        "---\nfrom: Sin cierre <x@ejemplo.com>\n",
        "---\nfrom: Linea suelta <x@ejemplo.com>\nlinea suelta\n---\n",
    ):
        _write_message(tmp_path, "store/emails/msg-0002.md", corrupt)
        (tmp_path / "store/emails/msg-0002.md").write_text(corrupt, encoding="utf-8")
        with pytest.raises(ValueError):
            rebuild_contacts_from_store(str(tmp_path))
        assert load_email_contacts(str(tmp_path)) == [
            {"name": "Viva", "email": "viva@ejemplo.com"}
        ]
        assert not list(tmp_path.glob("*.tmp"))


def test_atomic_write_uses_tmp_in_same_dir_and_leaves_no_residue(tmp_path, monkeypatch):
    _write_message(
        tmp_path,
        "store/emails/msg-0001.md",
        _node(from_value="Viva <viva@ejemplo.com>"),
    )
    replaced = []
    real_replace = os.replace

    def spy(src, dst):
        replaced.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    result = rebuild_contacts_from_store(str(tmp_path))
    assert len(replaced) == 1
    src, dst = replaced[0]
    assert dst == str(tmp_path / "contacts.json")
    assert src.startswith(str(tmp_path)) and src.endswith(".tmp")
    assert not list(tmp_path.glob("*.tmp"))
    assert result == [{"name": "Viva", "email": "viva@ejemplo.com"}]
    assert load_email_contacts(str(tmp_path)) == result


def test_invalid_root_is_rejected(tmp_path):
    for bad in ("", "   ", str(tmp_path / "falta")):
        with pytest.raises(ValueError):
            rebuild_contacts_from_store(bad)
    assert not (tmp_path / "contacts.json").exists()