# -*- coding: utf-8 -*-
"""Tests congelados: integracion deletion <-> index_lifecycle.

Cubre el ciclo completo sobre indices Conversation/Topic reales:
- dos mensajes en la misma conversacion/tema: borrar uno conserva el indice
  del otro y sus snapshots en el manifiesto;
- borrar el ULTIMO mensaje elimina los archivos de indice y `restore` los
  RECREA desde `index_snapshots`;
- un indice corrupto aborta `soft_delete` ANTES de mover el mensaje;
- manifiestos antiguos sin `index_snapshots` siguen restaurando sin tocar
  indices;
- si la restauracion de un indice falla, el mensaje sigue en .trash y el
  manifiesto sobrevive (reintento posible).

Sin red, sin secretos, sin tocar otros modulos.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.email.deletion import (  # noqa: E402
    INDEX_SNAPSHOT_KEY,
    PURGE_CONFIRMATION,
    restore,
    soft_delete,
)

CONVERSATION_KEY = "a" * 64


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _conversation_index(paths) -> str:
    lines = "".join("- " + p + "\n" for p in sorted(paths))
    return (
        "---\ntype: Conversation\n"
        "conversation_key: " + CONVERSATION_KEY + "\n"
        "message_count: " + str(len(paths)) + "\n---\n" + lines
    )


def _topic_index(paths) -> str:
    lines = "".join("- " + p + "\n" for p in sorted(paths))
    return (
        "---\ntype: Topic\ntopic: facturacion\n"
        "message_count: " + str(len(paths)) + "\n---\n" + lines
    )


def _message(text: str) -> str:
    return "---\ntype: Message\n---\n" + text + "\n"


class FrozenDeletionIndexIntegration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def _build_two_messages(self):
        """root con 2 mensajes que comparten UNA conversacion y UN tema."""
        rel_paths = ("emails/2026/09/msg1.md", "emails/2026/09/msg2.md")
        for number, rel_path in enumerate(rel_paths, start=1):
            _write(self.root / rel_path, _message("Hola " + str(number)))
        original = {
            "store/conversations/conv1.md": _conversation_index(rel_paths),
            "store/topics/t1.md": _topic_index(rel_paths),
        }
        for name, text in original.items():
            _write(self.root / name, text)
        return rel_paths, original

    def _read(self, rel_path) -> str:
        return (self.root / rel_path).read_text(encoding="utf-8")

    def test_soft_delete_one_keeps_the_other_and_restore_recovers(self):
        rel_paths, original = self._build_two_messages()
        first, second = rel_paths

        manifest = soft_delete(str(self.root), first)

        # El mensaje se movio y el manifiesto trae los DOS indices afectados.
        self.assertFalse((self.root / first).exists())
        self.assertTrue((self.root / ".trash" / first).is_file())
        self.assertEqual(set(manifest[INDEX_SNAPSHOT_KEY]), set(original))
        for name, text in original.items():
            self.assertEqual(manifest[INDEX_SNAPSHOT_KEY][name], text)
        # El otro mensaje conserva su indice: sigue existiendo y solo con el.
        for name in original:
            self.assertTrue((self.root / name).is_file())
            self.assertIn("- " + second + "\n", self._read(name))
            self.assertNotIn("- " + first + "\n", self._read(name))

        restored = restore(str(self.root), manifest["manifest_rel_path"])

        self.assertEqual(restored["rel_path"], first)
        self.assertTrue((self.root / first).is_file())
        self.assertFalse((self.root / ".trash" / first).exists())
        self.assertFalse(
            (self.root / ".trash" / (first + ".json")).exists()
        )
        for name, text in original.items():
            self.assertEqual(self._read(name), text)

    def test_deleting_last_removes_indices_and_restore_recreates_them(self):
        rel_paths, original = self._build_two_messages()

        for rel_path in rel_paths:
            soft_delete(str(self.root), rel_path)

        # Sin mensajes, el indice desaparece (remove deja la lista vacia).
        for name in original:
            self.assertFalse((self.root / name).exists())
            self.assertFalse(
                (self.root / (name + ".tmp")).exists()
            )

        for rel_path in reversed(rel_paths):
            restore(str(self.root), ".trash/" + rel_path + ".json")

        # Restaurar los RECREA identicos desde los snapshots.
        for name, text in original.items():
            self.assertEqual(self._read(name), text)
        for rel_path in rel_paths:
            self.assertTrue((self.root / rel_path).is_file())
            self.assertFalse((self.root / ".trash" / rel_path).exists())

    def test_corrupt_index_aborts_before_moving(self):
        rel_paths, original = self._build_two_messages()
        first, _ = rel_paths
        # Corrompe el tema: message_count no coincide con el cuerpo.
        _write(
            self.root / "store/topics/t1.md",
            _topic_index(rel_paths).replace("message_count: 2", "message_count: 5"),
        )

        with self.assertRaises(ValueError):
            soft_delete(str(self.root), first)

        # NADA se movio ni se escribio: mensaje, manifiesto y el otro indice.
        self.assertTrue((self.root / first).is_file())
        self.assertFalse((self.root / ".trash").exists())
        self.assertEqual(
            self._read("store/conversations/conv1.md"), original[
                "store/conversations/conv1.md"
            ]
        )

    def test_old_manifest_without_snapshots_still_restores(self):
        rel_path = "emails/2026/09/solo.md"
        message = _message("solo")
        index_name = "store/topics/t1.md"
        _write(self.root / index_name, _topic_index([rel_path]))
        # Estado de .trash congelado a mano: manifiesto ANTIGUO (5 claves).
        item_rel = ".trash/" + rel_path
        _write(self.root / item_rel, message)
        old_manifest = {
            "rel_path": rel_path,
            "trash_rel_path": item_rel,
            "manifest_rel_path": item_rel + ".json",
            "deleted_at": "2026-01-01T00:00:00Z",
            "size_bytes": len(message.encode("utf-8")),
        }
        _write(
            self.root / (item_rel + ".json"),
            json.dumps(old_manifest, indent=2, ensure_ascii=False) + "\n",
        )

        restored = restore(str(self.root), item_rel + ".json")

        self.assertEqual(restored, old_manifest)
        self.assertTrue((self.root / rel_path).is_file())
        self.assertEqual(self._read(rel_path), message)
        self.assertFalse((self.root / item_rel).exists())
        self.assertFalse((self.root / (item_rel + ".json")).exists())
        # El indice existente NO se toco (los manifiestos antiguos no tocan
        # indices ni necesitan recrearlos).
        self.assertEqual(
            self._read(index_name), _topic_index([rel_path])
        )

    def test_restore_failure_keeps_message_and_manifest(self):
        rel_paths, original = self._build_two_messages()
        first, _ = rel_paths
        manifest = soft_delete(str(self.root), first)
        # Corrompe el indice de conversacion (que sigue existiendo con el otro
        # mensaje) DESPUES del borrado: la restauracion debe abortar entera.
        _write(
            self.root / "store/conversations/conv1.md",
            "---\ntype: Conversation\nno-es-un-formato\n",
        )
        before_item = (self.root / ".trash" / first).read_text(encoding="utf-8")

        with self.assertRaises(ValueError):
            restore(str(self.root), manifest["manifest_rel_path"])

        # El mensaje SIGUE en .trash, el manifiesto sigue intacto y el indice
        # corrupto no fue reescrito: se puede reintentar tras repararlo.
        self.assertEqual(
            (self.root / ".trash" / first).read_text(encoding="utf-8"),
            before_item,
        )
        self.assertTrue((self.root / (".trash/" + first + ".json")).is_file())
        self.assertEqual(
            self._read("store/conversations/conv1.md"),
            "---\ntype: Conversation\nno-es-un-formato\n",
        )
        # Reparado el indice (coherente, solo con el otro mensaje), el
        # reintento completa y restaura todo.
        _write(
            self.root / "store/conversations/conv1.md",
            _conversation_index([rel_paths[1]]),
        )
        restore(str(self.root), manifest["manifest_rel_path"])
        self.assertTrue((self.root / first).is_file())
        self.assertFalse((self.root / ".trash" / first).exists())

    def test_purge_still_removes_trash_item_and_manifest(self):
        rel_paths, _ = self._build_two_messages()
        first, _ = rel_paths
        from src.email.deletion import purge

        manifest = soft_delete(str(self.root), first)
        removed = purge(
            str(self.root), manifest["trash_rel_path"], PURGE_CONFIRMATION
        )
        self.assertEqual(removed["rel_path"], first)
        self.assertFalse((self.root / ".trash" / first).exists())
        self.assertFalse((self.root / ".trash" / (first + ".json")).exists())


if __name__ == "__main__":
    unittest.main()