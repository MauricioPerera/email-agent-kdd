# -*- coding: utf-8 -*-
"""Tests congelados del ciclo de vida de indices Markdown (index_lifecycle).

Cubre Conversation y Topic con dos rutas: remove/add, indice vacio, corrupcion
(sin escribir) y escritura atomica (temporal en el mismo directorio +
os.replace, sin residuos .tmp).
"""

import os

import pytest

from src.email.index_lifecycle import (
    add_path_to_markdown_index,
    remove_path_from_markdown_index,
)

_KEY = "ab" * 32


def _conversation(count):
    return (
        f"---\ntype: Conversation\nconversation_key: {_KEY}\n"
        f"message_count: {count}\n---\n"
    )


def _topic(topic, count):
    return f"---\ntype: Topic\ntopic: {topic}\nmessage_count: {count}\n---\n"


def _entries(*paths):
    return "".join(f"- {p}\n" for p in paths)


def test_remove_from_conversation_with_two_paths(tmp_path):
    node = tmp_path / "conversations.md"
    node.write_text(
        _conversation(2) + _entries("store/emails/msg-0001.md", "store/emails/msg-0002.md"),
        encoding="utf-8",
    )
    assert remove_path_from_markdown_index(str(node), "store/emails/msg-0001.md") is True
    assert node.read_text(encoding="utf-8") == _conversation(1) + "- store/emails/msg-0002.md\n"


def test_remove_from_topic_with_two_paths(tmp_path):
    node = tmp_path / "factura.md"
    node.write_text(
        _topic("factura", 2) + _entries("store/emails/msg-0002.md", "store/emails/msg-0001.md"),
        encoding="utf-8",
    )
    assert remove_path_from_markdown_index(str(node), "store\\emails\\msg-0002.md") is True
    # Conserva el frontmatter, reordena y recalcula el conteo.
    assert node.read_text(encoding="utf-8") == _topic("factura", 1) + "- store/emails/msg-0001.md\n"


def test_add_to_conversation_deduplicates_and_sorts(tmp_path):
    node = tmp_path / "conversations.md"
    node.write_text(_conversation(1) + "- store/emails/msg-0002.md\n", encoding="utf-8")
    assert add_path_to_markdown_index(str(node), "store/emails/msg-0001.md") == 2
    assert add_path_to_markdown_index(str(node), "store/emails/msg-0001.md") == 2
    assert (
        node.read_text(encoding="utf-8")
        == _conversation(2) + _entries("store/emails/msg-0001.md", "store/emails/msg-0002.md")
    )


def test_add_to_topic_deduplicates_and_sorts(tmp_path):
    node = tmp_path / "factura.md"
    node.write_text(_topic("factura", 1) + "- store/emails/msg-0001.md\n", encoding="utf-8")
    assert add_path_to_markdown_index(str(node), "store/emails/msg-0002.md") == 2
    assert add_path_to_markdown_index(str(node), "store\\emails\\msg-0002.md") == 2
    assert (
        node.read_text(encoding="utf-8")
        == _topic("factura", 2) + _entries("store/emails/msg-0001.md", "store/emails/msg-0002.md")
    )


def test_remove_last_path_deletes_the_index_file(tmp_path):
    for text in (_conversation(1) + "- store/emails/msg-0001.md\n",
                 _topic("factura", 1) + "- store/emails/msg-0001.md\n"):
        node = tmp_path / f"{len(list(tmp_path.iterdir()))}.md"
        node.write_text(text, encoding="utf-8")
        assert remove_path_from_markdown_index(node, "store/emails/msg-0001.md") is True
        assert not node.exists()


def test_add_to_empty_index_and_remove_missing(tmp_path):
    for text in (_conversation(0), _topic("factura", 0)):
        node = tmp_path / f"{len(list(tmp_path.iterdir()))}.md"
        node.write_text(text, encoding="utf-8")
        assert add_path_to_markdown_index(str(node), "store/emails/msg-0001.md") == 1
        assert node.read_text(encoding="utf-8") == (
            text[: text.index("message_count:")] + "message_count: 1\n---\n"
            "- store/emails/msg-0001.md\n"
        )
        # La ruta no esta: no escribe nada.
        assert remove_path_from_markdown_index(node, "store/emails/msg-0002.md") is False
        assert node.read_text(encoding="utf-8").count("message_count: 1") == 1


@pytest.mark.parametrize(
    "corrupt",
    [
        "sin frontmatter\n- store/emails/msg-0001.md\n",
        "---\ntype: Conversation\nconversation_key: NO-HEX\nmessage_count: 1\n---\n"
        "- store/emails/msg-0001.md\n",
        "---\ntype: Topic\ntopic: factura\nmessage_count: 2\n---\n"
        "- store/emails/msg-0001.md\n",
        "---\ntype: Conversation\nconversation_key: " + _KEY + "\nmessage_count: 1\n---\n"
        "linea suelta\n",
        "---\ntype: Conversation\nconversation_key: " + _KEY + "\nmessage_count: 1\n---\n"
        "- ../etc/passwd\n",
        "---\ntype: Topic\ntopic: factura\nmessage_count: 1\n---\n",
    ],
)
def test_corrupt_index_fails_without_writing(tmp_path, corrupt):
    node = tmp_path / "nodo.md"
    node.write_text(corrupt, encoding="utf-8")
    before = node.read_text(encoding="utf-8")
    for call in (
        lambda: add_path_to_markdown_index(str(node), "store/emails/msg-0001.md"),
        lambda: remove_path_from_markdown_index(str(node), "store/emails/msg-0001.md"),
    ):
        with pytest.raises(ValueError):
            call()
    assert node.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("*.tmp"))


def test_missing_index_add_fails_and_remove_is_noop(tmp_path):
    node = tmp_path / "falta.md"
    with pytest.raises(ValueError):
        add_path_to_markdown_index(str(node), "store/emails/msg-0001.md")
    assert not node.exists()
    assert remove_path_from_markdown_index(str(node), "store/emails/msg-0001.md") is False


def test_path_traversal_and_empty_path_are_rejected(tmp_path):
    node = tmp_path / "nodo.md"
    node.write_text(
        _topic("factura", 1) + "- store/emails/msg-0001.md\n", encoding="utf-8"
    )
    for bad in ("../fuera.md", "..\\fuera.md", "", "store/emails/\x00.md"):
        with pytest.raises(ValueError):
            add_path_to_markdown_index(str(node), bad)
        with pytest.raises(ValueError):
            remove_path_from_markdown_index(str(node), bad)
    assert node.read_text(encoding="utf-8") == _topic("factura", 1) + "- store/emails/msg-0001.md\n"


def test_atomic_write_uses_tmp_in_same_dir_and_leaves_no_residue(tmp_path, monkeypatch):
    node = tmp_path / "nodo.md"
    node.write_text(
        _topic("factura", 2) + _entries("store/emails/msg-0001.md", "store/emails/msg-0002.md"),
        encoding="utf-8",
    )
    replaced = []
    real_replace = os.replace

    def spy(src, dst):
        replaced.append((src, dst))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    remove_path_from_markdown_index(str(node), "store/emails/msg-0001.md")
    assert len(replaced) == 1
    src, dst = replaced[0]
    assert str(src).endswith("nodo.md.tmp") and str(src).startswith(str(tmp_path))
    assert str(dst) == str(node)
    assert not list(tmp_path.glob("*.tmp"))
    assert node.read_text(encoding="utf-8") == _topic("factura", 1) + "- store/emails/msg-0002.md\n"