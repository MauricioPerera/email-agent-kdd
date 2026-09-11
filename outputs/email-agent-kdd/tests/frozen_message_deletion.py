"""Tests congelados de la pieza 1 del borrado reversible: src/email/deletion.py.

Sin red, sin secretos, sin CLI. Cubre: soft_delete mueve UN .md a
root/.trash preservando ruta y escribe un manifiesto JSON atomico; restore
lo devuelve; list_trash lista manifiestos; purge solo elimina algo YA en
.trash y SOLO con la frase exacta CONFIRMAR BORRADO PERMANENTE. Ninguna
operacion acepta path traversal y soft_delete jamas elimina contenido.
"""

import json
import re
import tempfile
from pathlib import Path

from src.email.deletion import (
    list_trash,
    purge,
    restore,
    soft_delete,
)

PURGE_PHRASE = "CONFIRMAR BORRADO PERMANENTE"
_DRIVE_RE = re.compile(r"^[A-Za-z]:")

_TREE = {
    "store/emails/msg-0001.md": "---\ntype: Email Message\nsubject: Hola\n---\ncuerpo del mensaje\n",
    "store/emails/anidado/msg-0002.md": "mensaje anidado\n",
    "store/notas.txt": "no es un nodo markdown\n",
}


def _build_tree(tmp, tree):
    for relpath, content in tree.items():
        target = Path(tmp) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_soft_delete_moves_file_and_writes_manifest():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        manifest = soft_delete(tmp, "store/emails/msg-0001.md")
        trash = Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md"
        assert trash.is_file(), "el nodo debe quedar dentro de .trash"
        assert not (Path(tmp) / "store" / "emails" / "msg-0001.md").exists(), (
            "soft_delete mueve, no copia"
        )
        assert (Path(tmp) / "store" / "notas.txt").is_file(), (
            "los demas archivos quedan intactos"
        )
        assert manifest["rel_path"] == "store/emails/msg-0001.md"
        assert manifest["trash_rel_path"] == ".trash/store/emails/msg-0001.md"
        assert manifest["manifest_rel_path"] == (
            ".trash/store/emails/msg-0001.md.json"
        )
        assert manifest["size_bytes"] == trash.stat().st_size
        assert manifest["deleted_at"].endswith("Z")
        on_disk = json.loads(
            (Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md.json")
            .read_text(encoding="utf-8")
        )
        assert on_disk == manifest, "el manifiesto en disco coincide"


def test_soft_delete_preserves_nested_route_and_content():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/anidado/msg-0002.md")
        trash = Path(tmp) / ".trash" / "store" / "emails" / "anidado" / "msg-0002.md"
        assert trash.read_text(encoding="utf-8") == "mensaje anidado\n", (
            "el contenido viaja intacto"
        )
        assert not (Path(tmp) / "store" / "emails" / "anidado" / "msg-0002.md").exists()


def test_soft_delete_rejects_traversal_without_touching_disk():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        outside = Path(tempfile.mkdtemp()) / "fuera.md"
        outside.write_text("secreto\n", encoding="utf-8")
        try:
            for rel_path in (
                "../fuera.md",
                "store/emails/../../fuera.md",
                "/etc/passwd",
                "C:/Windows/win.ini",
                "~/secretos.md",
                "store\\emails\\msg-0001.md",
                "store//emails/msg-0001.md",
                "store/emails/./msg-0001.md",
                "store/notas.txt",
                "",
            ):
                try:
                    soft_delete(tmp, rel_path)
                except ValueError:
                    continue
                raise AssertionError(
                    "la ruta insegura debe dar ValueError: " + repr(rel_path)
                )
            assert outside.read_text(encoding="utf-8") == "secreto\n", (
                "ningun archivo externo fue tocado"
            )
            assert not (Path(tmp) / ".trash").exists(), (
                ".trash no debe crearse cuando la ruta se rechaza"
            )
        finally:
            if outside.exists():
                outside.unlink()
            outside.parent.rmdir()


def test_soft_delete_missing_node_raises_file_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        try:
            soft_delete(tmp, "store/emails/inexistente.md")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("nodo inexistente debe dar FileNotFoundError")
        assert not (Path(tmp) / ".trash").exists()


def test_soft_delete_twice_fails_and_never_destroys():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/msg-0001.md")
        first = json.loads(
            (Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md.json")
            .read_text(encoding="utf-8")
        )
        try:
            soft_delete(tmp, "store/emails/msg-0001.md")
        except (ValueError, FileNotFoundError):
            pass
        else:
            raise AssertionError("borrar dos veces debe fallar")
        assert (Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md").is_file()
        assert first["rel_path"] == "store/emails/msg-0001.md"


def test_list_trash_lists_manifests_sorted():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        assert list_trash(tmp) == [], "sin borrados la papelera esta vacia"
        soft_delete(tmp, "store/emails/msg-0001.md")
        soft_delete(tmp, "store/emails/anidado/msg-0002.md")
        manifests = list_trash(tmp)
        rels = [item["rel_path"] for item in manifests]
        assert rels == sorted(rels), "ordenado por trash_rel_path"
        assert set(rels) == {
            "store/emails/msg-0001.md",
            "store/emails/anidado/msg-0002.md",
        }
        for item in manifests:
            assert "deleted_at" in item and "size_bytes" in item


def test_restore_returns_file_to_original_place():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/msg-0001.md")
        manifest = restore(tmp, ".trash/store/emails/msg-0001.md")
        original = Path(tmp) / "store" / "emails" / "msg-0001.md"
        assert original.is_file(), "el nodo vuelve a su ubicacion original"
        assert (
            original.read_text(encoding="utf-8")
            == "---\ntype: Email Message\nsubject: Hola\n---\ncuerpo del mensaje\n"
        ), "el contenido viaja intacto"
        assert not (Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md").exists()
        assert not (
            Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md.json"
        ).exists(), "el manifiesto se retira al restaurar"
        assert manifest["rel_path"] == "store/emails/msg-0001.md"
        assert list_trash(tmp) == []


def test_restore_refuses_to_overwrite_existing_file():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/msg-0001.md")
        (Path(tmp) / "store" / "emails" / "msg-0001.md").write_text(
            "otro contenido\n", encoding="utf-8"
        )
        try:
            restore(tmp, ".trash/store/emails/msg-0001.md")
        except ValueError:
            pass
        else:
            raise AssertionError("restaurar sobre existente debe dar ValueError")
        assert (
            Path(tmp) / "store" / "emails" / "msg-0001.md"
        ).read_text(encoding="utf-8") == "otro contenido\n", (
            "el destino no se sobrescribe"
        )
        assert (Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md").is_file(), (
            "el elemento sigue en .trash"
        )


def test_restore_rejects_paths_outside_trash():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        for rel_path in (
            "store/emails/msg-0001.md",
            "../fuera.md",
            ".trash/../store/emails/msg-0001.md",
            "/etc/passwd",
        ):
            try:
                restore(tmp, rel_path)
            except ValueError:
                continue
            raise AssertionError(
                "restore solo acepta rutas dentro de .trash: " + repr(rel_path)
            )


def test_purge_requires_exact_confirmation_phrase():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/msg-0001.md")
        for bad in (
            "",
            "confirmar borrado permanente",
            "CONFIRMAR BORRADO PERMANENTE ",
            " CONFIRMAR BORRADO PERMANENTE",
            "CONFIRMAR  BORRADO PERMANENTE",
            "CONFIRMAR ENVIO",
            "borrar ya",
        ):
            try:
                purge(tmp, ".trash/store/emails/msg-0001.md", bad)
            except ValueError:
                pass
            else:
                raise AssertionError(
                    "frase inexacta debe abortar: " + repr(bad)
                )
        assert (Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md").is_file(), (
            "nada se elimina con confirmacion inexacta"
        )


def test_purge_removes_item_and_manifest_with_exact_phrase():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/anidado/msg-0002.md")
        result = purge(tmp, ".trash/store/emails/anidado/msg-0002.md", PURGE_PHRASE)
        assert result["purged"] == ".trash/store/emails/anidado/msg-0002.md"
        assert not (
            Path(tmp) / ".trash" / "store" / "emails" / "anidado" / "msg-0002.md"
        ).exists(), "el elemento desaparece"
        assert not (
            Path(tmp) / ".trash" / "store" / "emails" / "anidado" / "msg-0002.md.json"
        ).exists(), "el manifiesto desaparece"
        assert list_trash(tmp) == []
        assert not (Path(tmp) / "store" / "emails" / "anidado" / "msg-0002.md").exists()


def test_purge_accepts_manifest_path_and_only_trash_entries():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/msg-0001.md")
        purge(
            tmp,
            ".trash/store/emails/msg-0001.md.json",
            PURGE_PHRASE,
        )
        assert not (Path(tmp) / ".trash" / "store" / "emails" / "msg-0001.md").exists()
        try:
            purge(tmp, "store/emails/msg-0002.md", PURGE_PHRASE)
        except ValueError:
            pass
        else:
            raise AssertionError(
                "purge nunca opera fuera de .trash, aunque la frase sea exacta"
            )
        assert (Path(tmp) / "store" / "emails" / "anidado" / "msg-0002.md").is_file(), (
            "los nodos fuera de .trash quedan intactos"
        )


def test_purge_rejects_traversal():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        outside = Path(tempfile.mkdtemp()) / "fuera.md"
        outside.write_text("secreto\n", encoding="utf-8")
        try:
            for rel_path in ("../fuera.md", "/etc/passwd", "..\\fuera.md"):
                try:
                    purge(tmp, rel_path, PURGE_PHRASE)
                except ValueError:
                    continue
                raise AssertionError(
                    "purge debe rechazar rutas inseguras: " + repr(rel_path)
                )
            assert outside.read_text(encoding="utf-8") == "secreto\n"
        finally:
            if outside.exists():
                outside.unlink()
            outside.parent.rmdir()


def test_full_cycle_soft_delete_restore_purge():
    with tempfile.TemporaryDirectory() as tmp:
        _build_tree(tmp, _TREE)
        soft_delete(tmp, "store/emails/msg-0001.md")
        assert list_trash(tmp)
        restore(tmp, ".trash/store/emails/msg-0001.md")
        assert list_trash(tmp) == []
        soft_delete(tmp, "store/emails/msg-0001.md")
        purge(tmp, ".trash/store/emails/msg-0001.md", PURGE_PHRASE)
        assert list_trash(tmp) == []
        assert not (Path(tmp) / "store" / "emails" / "msg-0001.md").exists(), (
            "tras purge el nodo ya no existe en ninguna parte"
        )