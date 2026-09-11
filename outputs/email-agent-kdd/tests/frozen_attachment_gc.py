# frozen_attachment_gc.py — Oracle congelado del GC de blobs de adjuntos
# (API de src/email/attachments.py). Sin red, sin IMAP, sin secretos.
#
# Verifica EXACTAMENTE el alcance pedido:
# - preservar referencias: un blob referenciado por un nodo activo NUNCA se
#   borra (formato nuevo y formato antiguo/legacy de frontmatter).
# - excluir .trash: las referencias que viven SOLO en .trash no protegen un
#   blob (el mensaje ya esta eliminado).
# - dry-run sin mutacion: gc_scan no cambia un solo byte del store.
# - confirmacion exacta: solo la frase literal completa autoriza el borrado.
# - limpieza blob + .meta relacionados.
# - hash invalido/corrupto: blob corrupto y archivo no reconocido se reportan
#   y NUNCA se borran; la corrupcion no se oculta.
# - fallo parcial: ante el primer fallo de E/S no se borra nada mas, sin
#   temporales residuales, reportando lo eliminado y lo fallado.
# - idempotencia: el segundo pase no encuentra candidatos y no borra nada.

import hashlib
import json

import pytest

from src.email.attachments import (
    GC_CONFIRMATION,
    AttachmentError,
    collect_referenced_hashes,
    gc_execute,
    gc_scan,
)


def _sha(content):
    return hashlib.sha256(content).hexdigest()


CONTENT_A = b"blob-referenciado-\x00\xff"
CONTENT_B = b"blob-huerfano-por-borrar"
CONTENT_C = b"blob-solo-en-trash"
SHA_A = _sha(CONTENT_A)
SHA_B = _sha(CONTENT_B)
SHA_C = _sha(CONTENT_C)
BAD_SHA_FILE = "zz" + "9" * 63  # nombre no-hex de 64: nunca se borra


def _write_node(root, rel_path, attachment_lines):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nsubject: prueba\nattachments:\n"
        + "\n".join(attachment_lines)
        + "\n---\n\nCuerpo.\n",
        encoding="utf-8",
    )


def _entries_lines(sha, stored=True):
    return [
        "  - sha256: " + sha,
        "    filename: informe.pdf",
        "    content_type: application/pdf",
        "    size: 10",
        "    part_index: 0",
        "    stored: " + ("true" if stored else "false"),
    ]


def _write_blob(root, sha, content):
    path = root / "attachments" / sha[:2] / sha[2:4] / sha
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    (root / "attachments" / (sha + ".meta")).write_text(
        json.dumps({"sha256": sha, "refs": 0}) + "\n", encoding="utf-8"
    )


def _store_paths(root):
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    )


def _contents(root):
    return {rel: (root / rel).read_bytes() for rel in _store_paths(root)}


def _store_basico(root):
    """Store con: nodo activo referenciando A; blob huerfano B; blob C solo
    referenciado por un nodo dentro de .trash."""
    root.mkdir(parents=True, exist_ok=True)
    _write_node(root, "store/emails/inbox/m1.md", _entries_lines(SHA_A))
    _write_blob(root, SHA_A, CONTENT_A)
    _write_blob(root, SHA_B, CONTENT_B)
    _write_blob(root, SHA_C, CONTENT_C)
    _write_node(root, ".trash/store/emails/viejo.md", _entries_lines(SHA_C))


def test_gc_preserva_blob_referenciado_formato_nuevo(tmp_path):
    root = tmp_path / "root"
    _store_basico(root)
    result = gc_execute(root, GC_CONFIRMATION)
    deleted = set(result["deleted"])
    assert "attachments/" + SHA_A[:2] + "/" + SHA_A[2:4] + "/" + SHA_A not in deleted
    assert (root / "attachments" / (SHA_A + ".meta")).exists()
    assert (root / "attachments" / SHA_A[:2] / SHA_A[2:4] / SHA_A).read_bytes() == CONTENT_A


def test_gc_cuenta_referencias_del_formato_antiguo(tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    (root / "store" / "emails" / "legacy.md").write_text(
        "---\nattachments:\n  - " + SHA_A + "\n---\n\nCuerpo.\n", encoding="utf-8"
    )
    _write_blob(root, SHA_A, CONTENT_A)
    assert collect_referenced_hashes(root) == {SHA_A}
    result = gc_execute(root, GC_CONFIRMATION)
    assert result["deleted"] == []
    assert result["candidates"] == []


def test_gc_excluye_trash_del_escaneo_de_referencias(tmp_path):
    root = tmp_path / "root"
    _store_basico(root)
    result = gc_execute(root, GC_CONFIRMATION)
    # C solo lo referenciaba un nodo en .trash: el blob es huerfano y se va.
    assert "attachments/" + SHA_C[:2] + "/" + SHA_C[2:4] + "/" + SHA_C in result["deleted"]
    assert "attachments/" + SHA_C + ".meta" in result["deleted"]
    assert not (root / "attachments" / (SHA_C + ".meta")).exists()


def test_gc_no_sigue_nodos_dentro_de_store_trash(tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / ".trash").mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    _write_node(root, "store/.trash/guardado.md", _entries_lines(SHA_B))
    _write_blob(root, SHA_B, CONTENT_B)
    result = gc_execute(root, GC_CONFIRMATION)
    assert result["deleted"] != []


def test_gc_scan_es_solo_lectura_dry_run_sin_mutacion(tmp_path):
    root = tmp_path / "root"
    _store_basico(root)
    before = _store_paths(root)
    contents = {rel: (root / rel).read_bytes() for rel in before}
    scan = gc_scan(root)
    assert _store_paths(root) == before
    assert {rel: (root / rel).read_bytes() for rel in before} == contents
    shas = {item["sha256"] for item in scan["candidates"]}
    assert shas == {SHA_B, SHA_C}
    assert scan["referenced_count"] == 1  # solo A (C vive en .trash)
    assert scan["nodes_scanned"] == 1
    blob_item = next(item for item in scan["candidates"] if item["sha256"] == SHA_B)
    assert blob_item["blob"] == "attachments/" + SHA_B[:2] + "/" + SHA_B[2:4] + "/" + SHA_B
    assert blob_item["meta"] == "attachments/" + SHA_B + ".meta"
    assert blob_item["size"] == len(CONTENT_B)
    assert blob_item["corrupt"] is False


def test_confirmacion_inexacta_no_borra_nada(tmp_path):
    root = tmp_path / "root"
    _store_basico(root)
    before = _store_paths(root)
    for bad in (
        "confirmar borrado adjuntos",
        "CONFIRMAR BORRADO",
        "CONFIRMAR BORRADO ADJUNTOS ",
        "CONFIRMAR EXTRACCION",
        None,
        "",
    ):
        with pytest.raises(AttachmentError) as excinfo:
            gc_execute(root, bad)
        assert excinfo.value.code == "confirmation-required"
    assert _store_paths(root) == before


def test_limpieza_blob_y_meta_del_huerfano(tmp_path):
    root = tmp_path / "root"
    _store_basico(root)
    result = gc_execute(root, GC_CONFIRMATION)
    assert sorted(result["deleted"]) == sorted(
        [
            "attachments/" + SHA_B[:2] + "/" + SHA_B[2:4] + "/" + SHA_B,
            "attachments/" + SHA_B + ".meta",
            "attachments/" + SHA_C[:2] + "/" + SHA_C[2:4] + "/" + SHA_C,
            "attachments/" + SHA_C + ".meta",
        ]
    )
    assert not (root / "attachments" / (SHA_B + ".meta")).exists()
    assert (root / "attachments" / (SHA_A + ".meta")).exists()


def test_hash_invalido_y_archivos_no_reconocidos_nunca_se_boran(tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    # blob con nombre no-hex, .meta con nombre invalido, blob con anidamiento
    # incorrecto y residual .tmp: todo queda en unrecognized y intacto.
    (root / "attachments" / "ab" / "cd").mkdir(parents=True)
    (root / "attachments" / "ab" / "cd" / BAD_SHA_FILE).write_bytes(b"x")
    (root / "attachments" / "ab" / "cd" / (SHA_B + ".meta")).write_text("x")
    (root / "attachments" / (SHA_B[:12] + ".meta")).write_text("x")
    (root / "attachments" / "ab" / (SHA_B + ".meta")).write_text("x")
    (root / "attachments" / "ab" / "cd" / (SHA_B + ".tmp")).write_bytes(b"x")
    result = gc_execute(root, GC_CONFIRMATION)
    assert result["deleted"] == []
    assert len(result["unrecognized"]) == 5
    assert all(rel.startswith("attachments/") for rel in result["unrecognized"])
    assert (root / "attachments" / "ab" / "cd" / BAD_SHA_FILE).exists()
    assert (root / "attachments" / "ab" / "cd" / (SHA_B + ".tmp")).exists()


def test_blob_corrupto_se_reporta_y_nunca_se_bora(tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    _write_blob(root, SHA_B, b"contenido-que-no-coincide-con-su-hash")
    scan = gc_scan(root)
    assert [item["sha256"] for item in scan["corrupt"]] == [SHA_B]
    assert scan["candidates"] == []
    gc_execute(root, GC_CONFIRMATION)
    assert (root / "attachments" / SHA_B[:2] / SHA_B[2:4] / SHA_B).exists()
    assert (root / "attachments" / (SHA_B + ".meta")).exists()


def test_fallo_parcial_detiene_todo_y_reporta(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    _write_blob(root, SHA_B, CONTENT_B)
    _write_blob(root, SHA_C, CONTENT_C)
    original_unlink = type(root / "x").unlink

    def failing_unlink(self, *args, **kwargs):
        if self.name == SHA_B:
            raise PermissionError("bloqueado")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.unlink", failing_unlink)
    result = gc_execute(root, GC_CONFIRMATION)
    monkeypatch.undo()
    # Un solo fallo detiene TODO: solo se borro lo ANTERIOR al fallo en el
    # orden determinista (nada despues), y el .meta del fallado queda intacto.
    first, second = sorted([SHA_B, SHA_C])
    assert result["failed"] == [
        {"path": "attachments/" + SHA_B[:2] + "/" + SHA_B[2:4] + "/" + SHA_B, "error": "io-error"}
    ]
    assert (root / "attachments" / (SHA_B + ".meta")).exists()
    assert sorted(result["deleted"]) == sorted(
        [
            "attachments/" + first[:2] + "/" + first[2:4] + "/" + first,
            "attachments/" + first + ".meta",
        ]
    )
    assert (root / "attachments" / (second + ".meta")).exists()
    # Sin el monkeypatch, el segundo pase limpia normal (no quedan temporales).
    result2 = gc_execute(root, GC_CONFIRMATION)
    assert result2["failed"] == []
    for sha in (SHA_B, SHA_C):
        assert not (root / "attachments" / (sha + ".meta")).exists()
        assert not (root / "attachments" / sha[:2] / sha[2:4] / sha).exists()


def test_idempotencia_segundo_pase_sin_candidatos(tmp_path):
    root = tmp_path / "root"
    _store_basico(root)
    first = gc_execute(root, GC_CONFIRMATION)
    assert first["deleted"]
    after = _store_paths(root)
    second = gc_execute(root, GC_CONFIRMATION)
    assert second["candidates"] == []
    assert second["deleted"] == []
    assert second["failed"] == []
    assert _store_paths(root) == after


def test_store_ausente_aborta_sin_borrar(tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    _write_blob(root, SHA_B, CONTENT_B)
    before = _store_paths(root)
    with pytest.raises(AttachmentError) as excinfo:
        gc_scan(root)
    assert excinfo.value.code == "store-missing"
    with pytest.raises(AttachmentError):
        gc_execute(root, GC_CONFIRMATION)
    assert _store_paths(root) == before
    assert (root / "attachments" / (SHA_B + ".meta")).exists()


def test_nodo_ilegible_aborta_el_escaneo_fail_closed(tmp_path):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    (root / "store" / "emails" / "roto.md").write_text(
        "---\nattachments:\n  - sha256: " + SHA_A + "\n    size: no-es-numero\n"
        "    part_index: 0\n---\n\nCuerpo.\n",
        encoding="utf-8",
    )
    _write_blob(root, SHA_A, CONTENT_A)
    before = _store_paths(root)
    with pytest.raises(AttachmentError) as excinfo:
        gc_scan(root)
    assert excinfo.value.code == "node-unreadable"
    with pytest.raises(AttachmentError):
        gc_execute(root, GC_CONFIRMATION)
    assert _store_paths(root) == before