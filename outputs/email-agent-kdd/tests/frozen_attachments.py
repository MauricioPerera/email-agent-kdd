"""Oracle congelado e independiente del nucleo de almacenamiento de adjuntos.

Cubre EXACTAMENTE el alcance pedido del Sprint 3 (nucleo): traversal,
nombres hostiles, colision/hash mismatch, limite de tamano y tipos
bloqueados por defecto, idempotencia y errores sanitizados. Sin red,
sin IMAP, sin fixtures externos. Los blobs se derivan SOLO del sha256;
los bytes nunca se guardan sin `authorize=True`.
"""

import hashlib
import json
from pathlib import Path

import pytest

from src.email.attachments import (
    AttachmentError,
    blob_path,
    blob_rel_path,
    is_type_allowed,
    list_attachments,
    list_node_attachments,
    meta_path,
    sanitize_display_name,
    store_attachment_bytes,
)

BLOB_CONTENT = b"attachment-payload-\x00\x01\xff"
BLOB_SHA = hashlib.sha256(BLOB_CONTENT).hexdigest()
META_SHA = "ab" + "cd" + "e" * 60

HOSTILE_NAMES = [
    "../../evil",
    "..\\..\\evil",
    "C:\\temp\\x.exe",
    "~root/secret",
    "/etc/passwd",
    "..",
    ".",
    "",
    "trick\u202ereport.pdf",
    "bad\x01\x1f\x7fname.pdf",
    "..hidden",
    "n" * 400,
]


def _store(root, sha, content, metadata=None, **kwargs):
    return store_attachment_bytes(
        root, sha, content, metadata or {}, authorize=True, **kwargs
    )


# ---------------------------------------------------------------------------
# Traversal: la ruta del blob se deriva SOLO del sha256 validado.
# ---------------------------------------------------------------------------


def test_blob_path_is_content_addressed_under_attachments():
    assert blob_rel_path(META_SHA) == "attachments/ab/cd/" + META_SHA
    text = str(blob_path("root", META_SHA)).replace("\\", "/")
    assert text.endswith("/attachments/ab/cd/" + META_SHA)


def test_invalid_sha256_rejected_before_any_write(tmp_path):
    root = tmp_path / "store"
    for bad in ("", "ABC", "g" * 64, BLOB_SHA + "ff", "../../" + BLOB_SHA):
        with pytest.raises(AttachmentError) as excinfo:
            blob_path(root, bad)
        assert excinfo.value.code == "hash-mismatch"
    assert not (root / "attachments").exists()


def test_hostile_filenames_never_escape_the_attachments_directory(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    for index, name in enumerate(HOSTILE_NAMES):
        if not name:
            continue
        _store(
            root,
            BLOB_SHA,
            BLOB_CONTENT,
            {"filename": name, "content_type": "text/plain", "part_index": index},
        )
    resolved = str(blob_path(root, BLOB_SHA).resolve())
    assert resolved.startswith(str(root.resolve()) + "\\") or resolved.startswith(
        str(root.resolve())
    )
    for path in tmp_path.rglob("*"):
        if path == root or not path.is_file():
            continue
        relative = str(path.relative_to(tmp_path)).replace("\\", "/")
        assert relative.startswith("store/attachments/"), (
            "escritura fuera de attachments: " + relative
        )
        for name in HOSTILE_NAMES:
            if name and len(name) > 1:  # "." casaria con ".meta" por accidente
                assert name not in relative


# ---------------------------------------------------------------------------
# Nombres hostiles: el display se sana, nunca compone rutas.
# ---------------------------------------------------------------------------


def test_sanitize_display_name_neutralizes_hostile_names():
    assert sanitize_display_name("../../evil") == "evil"
    assert sanitize_display_name("..\\..\\evil") == "evil"
    assert sanitize_display_name("C:\\temp\\x.exe") == "x.exe"
    assert sanitize_display_name("a/b\\c.pdf") == "c.pdf"
    assert sanitize_display_name("") == "attachment-0"
    assert sanitize_display_name("", 3) == "attachment-3"
    assert sanitize_display_name("..") == "attachment-0"
    assert sanitize_display_name(".") == "attachment-0"
    assert sanitize_display_name("bad\x01name.pdf") == "bad?name.pdf"
    assert len(sanitize_display_name("n" * 400)) == 80
    for name in HOSTILE_NAMES:
        display = sanitize_display_name(name, 7)
        assert "/" not in display and "\\" not in display
        assert ".." not in display
        assert not any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in display)


# ---------------------------------------------------------------------------
# Guarda bytes SOLO con llamada explicita (authorize=True).
# ---------------------------------------------------------------------------


def test_storing_requires_explicit_authorization(tmp_path):
    root = tmp_path / "store"
    for kwargs in ({"authorize": False}, {}):
        with pytest.raises(AttachmentError) as excinfo:
            store_attachment_bytes(root, BLOB_SHA, BLOB_CONTENT, {}, **kwargs)
        assert excinfo.value.code == "confirmation-required"
    assert not (root / "attachments").exists()


def test_store_writes_blob_and_meta_content_addressed(tmp_path):
    root = tmp_path / "store"
    result = _store(
        root,
        BLOB_SHA,
        BLOB_CONTENT,
        {"filename": "informe.pdf", "content_type": "application/pdf", "part_index": 2},
    )
    assert result["stored"] is True
    assert result["path"] == blob_rel_path(BLOB_SHA)
    assert result["idempotent"] is False
    blob = blob_path(root, BLOB_SHA)
    assert blob.is_file() and blob.read_bytes() == BLOB_CONTENT
    data = json.loads(meta_path(root, BLOB_SHA).read_text(encoding="utf-8"))
    assert data["sha256"] == BLOB_SHA
    assert data["filename_display"] == "informe.pdf"
    assert data["size"] == len(BLOB_CONTENT)
    assert data["refs"] == 0


# ---------------------------------------------------------------------------
# Colision / hash mismatch: abortar sin sobrescribir.
# ---------------------------------------------------------------------------


def test_content_must_match_declared_sha_before_any_write(tmp_path):
    root = tmp_path / "store"
    with pytest.raises(AttachmentError) as excinfo:
        _store(root, BLOB_SHA, b"otro contenido")
    assert excinfo.value.code == "hash-mismatch"
    assert not (root / "attachments").exists()


def test_corrupted_existing_blob_aborts_without_overwriting(tmp_path):
    root = tmp_path / "store"
    _store(root, BLOB_SHA, BLOB_CONTENT, {})
    blob = blob_path(root, BLOB_SHA)
    tampered = BLOB_CONTENT[:-1] + b"X"
    blob.write_bytes(tampered)
    with pytest.raises(AttachmentError) as excinfo:
        _store(root, BLOB_SHA, BLOB_CONTENT, {})
    assert excinfo.value.code == "hash-mismatch"
    assert blob.read_bytes() == tampered, "el blob existente fue sobrescrito"
    assert list(blob.parent.glob("*.tmp")) == []


# ---------------------------------------------------------------------------
# Limite de tamano y tipos bloqueados por defecto: solo metadatos.
# ---------------------------------------------------------------------------


def test_size_limit_returns_metadata_only_without_writing(tmp_path):
    root = tmp_path / "store"
    result = _store(root, BLOB_SHA, BLOB_CONTENT, {}, max_bytes=4)
    assert result == {
        "sha256": BLOB_SHA,
        "stored": False,
        "skipped": "size-limit-exceeded",
        "path": blob_rel_path(BLOB_SHA),
    }
    assert not (root / "attachments").exists()


def test_blocked_types_default_to_metadata_only(tmp_path):
    root = tmp_path / "store"
    cases = (
        ("application/x-msdownload", "setup.msi"),
        ("application/x-sh", "script.sh"),
        ("application/pdf", "virus.exe"),
        ("application/pdf", "page.scr"),
        ("application/pdf", "link.lnk"),
        ("application/pdf", "run.bat"),
        ("application/pdf", "run.cmd"),
        ("application/pdf", "code.js"),
    )
    for content_type, filename in cases:
        content = (content_type + "|" + filename).encode("utf-8")
        result = _store(
            root,
            hashlib.sha256(content).hexdigest(),
            content,
            {"filename": filename, "content_type": content_type},
        )
        assert result["stored"] is False, (content_type, filename)
        assert result["skipped"] == "type-not-allowed", (content_type, filename)
    assert not (root / "attachments").exists()


def test_explicitly_allowed_type_stores_bytes(tmp_path):
    root = tmp_path / "store"
    result = _store(
        root,
        BLOB_SHA,
        BLOB_CONTENT,
        {"filename": "setup.exe", "content_type": "application/x-msdownload"},
        allowed_types=["application/x-msdownload"],
    )
    assert result["stored"] is True
    assert blob_path(root, BLOB_SHA).read_bytes() == BLOB_CONTENT


def test_is_type_allowed_rules():
    assert is_type_allowed("application/pdf", "informe.pdf") is True
    assert is_type_allowed("application/x-msdownload", "a.exe") is False
    assert is_type_allowed("text/plain", "a.EXE") is False
    assert is_type_allowed("text/plain", "no-ext") is True
    assert is_type_allowed(
        "application/x-sh", "a.sh", ["application/x-sh"]
    ) is True
    assert is_type_allowed("application/pdf", "a.pdf", ["text/plain"]) is False


# ---------------------------------------------------------------------------
# Idempotencia: extraer dos veces -> no-op con hash verificado.
# ---------------------------------------------------------------------------


def test_second_extraction_is_a_no_op(tmp_path):
    root = tmp_path / "store"
    first = _store(root, BLOB_SHA, BLOB_CONTENT, {"filename": "a.pdf"})
    blob = blob_path(root, BLOB_SHA)
    before = (blob.read_bytes(), meta_path(root, BLOB_SHA).read_bytes())
    second = _store(
        root, BLOB_SHA, BLOB_CONTENT, {"filename": "a.pdf"}
    )
    assert second["stored"] is True
    assert second["idempotent"] is True
    assert second["path"] == first["path"]
    assert (blob.read_bytes(), meta_path(root, BLOB_SHA).read_bytes()) == before
    files = [path for path in (root / "attachments").rglob("*") if path.is_file()]
    assert len(files) == 2  # blob + .meta


def test_idempotent_recheck_detects_corruption(tmp_path):
    root = tmp_path / "store"
    _store(root, BLOB_SHA, BLOB_CONTENT, {})
    blob = blob_path(root, BLOB_SHA)
    blob.write_bytes(b"corrupto")
    with pytest.raises(AttachmentError) as excinfo:
        _store(root, BLOB_SHA, BLOB_CONTENT, {})
    assert excinfo.value.code == "hash-mismatch"
    assert blob.read_bytes() == b"corrupto"


# ---------------------------------------------------------------------------
# Listado: metadatos del frontmatter, sin abrir blobs.
# ---------------------------------------------------------------------------


def test_list_attachments_uses_frontmatter_only_and_sanitizes_display():
    entries = [
        {"sha256": BLOB_SHA, "filename": "informe.pdf",
         "content_type": "application/pdf", "size": len(BLOB_CONTENT),
         "part_index": 0, "stored": True},
        {"sha256": BLOB_SHA, "filename": "../../evil",
         "content_type": "application/pdf", "size": 3, "part_index": 1,
         "stored": False, "skipped": "type-not-allowed"},
        {"sha256": BLOB_SHA, "filename": "", "part_index": 2},
    ]
    rows = list_attachments(entries)
    assert rows[0]["display"] == "informe.pdf"
    assert rows[0]["sha256_short"] == BLOB_SHA[:12]
    assert rows[0]["status"] == "stored"
    assert rows[1]["display"] == "evil"
    assert rows[1]["status"] == "not-stored"
    assert rows[1]["skipped"] == "type-not-allowed"
    assert rows[2]["display"] == "attachment-2"


def test_list_node_attachments_never_materializes_blobs(tmp_path, monkeypatch):
    root = tmp_path / "store"
    (root / "nodos").mkdir(parents=True)
    sha = BLOB_SHA
    (root / "nodos" / "msg.md").write_text(
        "---\n"
        "type: Email Message\n"
        "attachments:\n"
        "  - sha256: " + sha + "\n"
        "    filename: informe.pdf\n"
        "    content_type: application/pdf\n"
        "    size: " + str(len(BLOB_CONTENT)) + "\n"
        "    part_index: 0\n"
        "    stored: false\n"
        "---\ncuerpo\n",
        encoding="utf-8",
    )
    rows = list_node_attachments(str(root), "nodos/msg.md")
    assert rows[0]["status"] == "not-stored"
    assert rows[0]["display"] == "informe.pdf"
    assert not (root / "attachments").exists(), "el listado abrio/materializo blobs"


# ---------------------------------------------------------------------------
# Errores sanitizados: sin rutas absolutas ni secretos.
# ---------------------------------------------------------------------------


def test_errors_are_sanitized_no_absolute_paths(tmp_path):
    root = tmp_path / "store"
    cases = (
        {"sha256": "no-es-hex", "content": b"x", "authorize": True},
        {"sha256": BLOB_SHA, "content": BLOB_CONTENT, "authorize": False},
    )
    for kwargs in cases:
        with pytest.raises(AttachmentError) as excinfo:
            store_attachment_bytes(root, **kwargs)
        message = excinfo.value.message
        assert str(tmp_path) not in message
        assert str(root) not in message
        assert "C:\\" not in message
        assert "password" not in message.lower()


def test_hash_mismatch_message_uses_relative_path_only(tmp_path):
    root = tmp_path / "store"
    _store(root, BLOB_SHA, BLOB_CONTENT, {})
    blob_path(root, BLOB_SHA).write_bytes(b"corrupto")
    with pytest.raises(AttachmentError) as excinfo:
        _store(root, BLOB_SHA, BLOB_CONTENT, {})
    message = excinfo.value.message
    assert str(root) not in message
    assert str(tmp_path) not in message
    assert blob_rel_path(BLOB_SHA) in message