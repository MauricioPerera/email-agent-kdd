"""Oracle congelado e independiente del nucleo de adjuntos (Sprint 3).

Sin red, sin IMAP, con fixtures RFC822 embebidos. Cubre: traversal/filenames
hostiles, colisiones/hash mismatch, limites y tipos prohibidos, idempotencia,
compatibilidad de frontmatter (hashes sueltos vs mapa completo) y sanitizacion
de errores. Los blobs se derivan SOLO del sha256; los bytes nunca se guardan
sin `authorize=True`.
"""

import hashlib
import json
from pathlib import Path

import pytest

from src.email.attachments import (
    MAX_ATTACHMENT_BYTES,
    AttachmentError,
    blob_path,
    blob_rel_path,
    full_entries,
    is_type_allowed,
    list_attachments,
    list_node_attachments,
    meta_path,
    read_attachment_entries,
    render_attachment_front_lines,
    sanitize_display_name,
    store_attachment_bytes,
)
from src.email.parse import parse_raw_email
from src.email.persist import persist_email_okf

PDF_CONTENT = b"%PDF-"
PDF_SHA = hashlib.sha256(PDF_CONTENT).hexdigest()

MULTIPART_RAW = (
    b"From: a@example.com\n"
    b"To: user@example.com\n"
    b"Subject: Adjuntos\n"
    b"MIME-Version: 1.0\n"
    b'Content-Type: multipart/mixed; boundary="BOUND"\n'
    b"\n"
    b"--BOUND\n"
    b"Content-Type: text/plain; charset=utf-8\n"
    b"\n"
    b"Cuerpo.\n"
    b"--BOUND\n"
    b"Content-Type: application/pdf; name=informe.pdf\n"
    b"Content-Disposition: attachment; filename=informe.pdf\n"
    b"Content-Transfer-Encoding: base64\n"
    b"\n"
    b"JVBERi0=\n"
    b"--BOUND\n"
    b"Content-Type: application/pdf; name=informe.pdf\n"
    b"Content-Disposition: attachment; filename=informe.pdf\n"
    b"Content-Transfer-Encoding: base64\n"
    b"\n"
    b"JVBERi0=\n"
    b"--BOUND--\n"
)

HOSTILE_NAMES = [
    "../../evil",
    "..\\..\\evil",
    "C:\\temp\\x.exe",
    "~root/secret",
    "/etc/passwd",
    "..",
    ".",
    "",
    "report\u202eexe.pdf",
    "bad\x01\x1fname.pdf",
    "..hidden",
    "a" * 300 + ".pdf",
]


def _sha_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Parseo: metadatos completos sin bytes.
# ---------------------------------------------------------------------------


def test_parse_keeps_metadata_only_and_full_entries_adds_part_index():
    record = parse_raw_email(MULTIPART_RAW, "personal")
    assert len(record["attachments"]) == 2
    for attachment in record["attachments"]:
        assert set(attachment) == {"filename", "content_type", "size", "sha256"}
        assert "content" not in attachment
        assert attachment["filename"] == "informe.pdf"
        assert attachment["sha256"] == PDF_SHA
    entries = full_entries(record["attachments"])
    assert [entry["part_index"] for entry in entries] == [0, 1]
    assert all(entry["stored"] is False for entry in entries)
    assert all(entry["sha256"] == PDF_SHA for entry in entries)


# ---------------------------------------------------------------------------
# Traversal y filenames hostiles: la ruta SIEMPRE se deriva del sha256.
# ---------------------------------------------------------------------------


def test_blob_path_derives_only_from_sha256_and_stays_under_attachments():
    blob = blob_path("store-root", PDF_SHA)
    text = str(blob).replace("\\", "/")
    assert text.endswith(
        "/attachments/" + PDF_SHA[:2] + "/" + PDF_SHA[2:4] + "/" + PDF_SHA
    )
    for name in HOSTILE_NAMES:
        if not name:
            continue
        assert name not in text


def test_hostile_filenames_never_escape_the_attachments_directory(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    for index, name in enumerate(HOSTILE_NAMES):
        store_attachment_bytes(
            root,
            PDF_SHA,
            PDF_CONTENT,
            {"filename": name, "content_type": "application/pdf", "part_index": index},
            authorize=True,
        )
    assert str(blob_path(root, PDF_SHA).resolve()).startswith(str(root.resolve()))
    for path in tmp_path.rglob("*"):
        if path == root or not path.is_file():
            continue
        relative = str(path.relative_to(tmp_path)).replace("\\", "/")
        assert relative.startswith("store/attachments/"), (
            "escritura fuera de attachments: " + relative
        )


def test_sanitize_display_name_neutralizes_hostile_names():
    assert sanitize_display_name("../../evil") == "evil"
    assert sanitize_display_name("C:\\temp\\x") == "x"
    assert sanitize_display_name("a/b\\c.pdf") == "c.pdf"
    assert sanitize_display_name("") == "attachment-0"
    assert sanitize_display_name("", 3) == "attachment-3"
    assert sanitize_display_name("..") == "attachment-0"
    assert sanitize_display_name("bad\x01name.pdf") == "bad?name.pdf"
    assert sanitize_display_name('weird:*?"<>|name.pdf') == "weird_______name.pdf"
    assert len(sanitize_display_name("n" * 500)) == 80
    for name in HOSTILE_NAMES:
        display = sanitize_display_name(name)
        assert "/" not in display and "\\" not in display
        assert ".." not in display
        assert not any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in display)


# ---------------------------------------------------------------------------
# Extraccion/autorizacion: sin authorize=True no se escribe un byte.
# ---------------------------------------------------------------------------


def test_storing_bytes_requires_explicit_authorization(tmp_path):
    root = tmp_path / "store"
    for kwargs in ({"authorize": False}, {}):
        with pytest.raises(AttachmentError) as excinfo:
            store_attachment_bytes(root, PDF_SHA, PDF_CONTENT, {}, **kwargs)
        assert excinfo.value.code == "confirmation-required"
    assert not (root / "attachments").exists()


def test_store_writes_content_addressed_blob_and_meta(tmp_path):
    root = tmp_path / "store"
    result = store_attachment_bytes(
        root,
        PDF_SHA,
        PDF_CONTENT,
        {"filename": "informe.pdf", "content_type": "application/pdf", "part_index": 2},
        authorize=True,
    )
    assert result["stored"] is True
    assert result["path"] == blob_rel_path(PDF_SHA)
    blob = blob_path(root, PDF_SHA)
    assert blob.is_file() and blob.read_bytes() == PDF_CONTENT
    meta = meta_path(root, PDF_SHA)
    data = json.loads(meta.read_text(encoding="utf-8"))
    assert data["sha256"] == PDF_SHA
    assert data["filename_display"] == "informe.pdf"
    assert data["size"] == len(PDF_CONTENT)


def test_content_hash_must_match_declared_sha(tmp_path):
    root = tmp_path / "store"
    with pytest.raises(AttachmentError) as excinfo:
        store_attachment_bytes(root, PDF_SHA, b"otro contenido", {}, authorize=True)
    assert excinfo.value.code == "hash-mismatch"
    assert not (root / "attachments").exists()


# ---------------------------------------------------------------------------
# Colisiones: blob existente distinto -> hash-mismatch, sin sobrescribir.
# ---------------------------------------------------------------------------


def test_collision_with_corrupted_blob_aborts_without_overwriting(tmp_path):
    root = tmp_path / "store"
    store_attachment_bytes(root, PDF_SHA, PDF_CONTENT, {}, authorize=True)
    blob = blob_path(root, PDF_SHA)
    tampered = PDF_CONTENT[:-1] + b"X"
    blob.write_bytes(tampered)
    with pytest.raises(AttachmentError) as excinfo:
        store_attachment_bytes(root, PDF_SHA, PDF_CONTENT, {}, authorize=True)
    assert excinfo.value.code == "hash-mismatch"
    assert blob.read_bytes() == tampered, "el blob existente fue sobrescrito"
    assert list(blob.parent.glob("*.tmp")) == []


# ---------------------------------------------------------------------------
# Limites y tipos prohibidos por defecto: solo metadatos, nunca bytes.
# ---------------------------------------------------------------------------


def test_size_limit_reports_metadata_only_without_writing(tmp_path):
    root = tmp_path / "store"
    result = store_attachment_bytes(
        root, PDF_SHA, PDF_CONTENT, {}, authorize=True, max_bytes=4
    )
    assert result == {
        "sha256": PDF_SHA,
        "stored": False,
        "skipped": "size-limit-exceeded",
        "path": blob_rel_path(PDF_SHA),
    }
    assert not root.exists() or not any(path.is_file() for path in root.rglob("*"))
    assert MAX_ATTACHMENT_BYTES == 25 * 1024 * 1024


def test_blocked_types_default_to_metadata_only(tmp_path):
    root = tmp_path / "store"
    cases = (
        ("application/x-msdownload", "setup.msi"),
        ("application/pdf", "virus.exe"),
        ("application/x-sh", "script.sh"),
        ("application/pdf", "page.scr"),
        ("application/pdf", "link.lnk"),
        ("application/pdf", "run.bat"),
        ("application/pdf", "run.cmd"),
        ("application/pdf", "code.js"),
    )
    for content_type, filename in cases:
        content = (content_type + filename).encode("utf-8")
        sha = _sha_of(content_type + filename)
        result = store_attachment_bytes(
            root,
            sha,
            content,
            {"filename": filename, "content_type": content_type},
            authorize=True,
        )
        assert result["stored"] is False, (content_type, filename)
        assert result["skipped"] == "type-not-allowed", (content_type, filename)
    assert not any(path.is_file() for path in root.rglob("*"))


def test_explicitly_allowed_type_stores_bytes(tmp_path):
    root = tmp_path / "store"
    result = store_attachment_bytes(
        root,
        PDF_SHA,
        PDF_CONTENT,
        {"filename": "setup.exe", "content_type": "application/x-msdownload"},
        authorize=True,
        allowed_types=["application/x-msdownload"],
    )
    assert result["stored"] is True
    assert blob_path(root, PDF_SHA).read_bytes() == PDF_CONTENT


def test_is_type_allowed_rules():
    assert is_type_allowed("application/pdf", "informe.pdf") is True
    assert is_type_allowed("application/x-msdownload", "a.exe") is False
    assert is_type_allowed("application/x-sh", "a.sh") is False
    assert is_type_allowed("text/plain", "a.exe") is False
    assert is_type_allowed("text/plain", "a.EXE") is False
    assert is_type_allowed("text/plain", "no-ext") is True
    assert is_type_allowed(
        "application/x-msdownload", "a.exe", ["application/x-msdownload"]
    ) is True
    assert is_type_allowed("application/pdf", "a.pdf", ["text/plain"]) is False


# ---------------------------------------------------------------------------
# Idempotencia.
# ---------------------------------------------------------------------------


def test_second_extraction_is_a_no_op(tmp_path):
    root = tmp_path / "store"
    first = store_attachment_bytes(root, PDF_SHA, PDF_CONTENT, {}, authorize=True)
    blob = blob_path(root, PDF_SHA)
    before = (blob.read_bytes(), meta_path(root, PDF_SHA).read_bytes())
    second = store_attachment_bytes(root, PDF_SHA, PDF_CONTENT, {}, authorize=True)
    assert second["stored"] is True and second["idempotent"] is True
    assert second["path"] == first["path"]
    after = (blob.read_bytes(), meta_path(root, PDF_SHA).read_bytes())
    assert before == after
    files = [path for path in (root / "attachments").rglob("*") if path.is_file()]
    assert len(files) == 2  # blob + .meta


def test_persist_enriched_node_twice_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record = parse_raw_email(MULTIPART_RAW, "personal")
    record["attachments"] = full_entries(record["attachments"])
    persist_email_okf(record, "nodo.md")
    first = (tmp_path / "nodo.md").read_text(encoding="utf-8")
    persist_email_okf(record, "nodo.md")
    assert (tmp_path / "nodo.md").read_text(encoding="utf-8") == first


# ---------------------------------------------------------------------------
# Compatibilidad de frontmatter: formato antiguo (hashes) y nuevo (mapas).
# ---------------------------------------------------------------------------


def test_render_keeps_legacy_hash_only_lines_for_parse_records():
    assert render_attachment_front_lines(PDF_SHA) == ["  - " + PDF_SHA]
    legacy = {
        "sha256": PDF_SHA,
        "filename": "informe.pdf",
        "content_type": "application/pdf",
        "size": 5,
    }
    assert render_attachment_front_lines(legacy) == ["  - " + PDF_SHA]


def test_render_writes_full_metadata_map_without_bytes():
    entry = {
        "sha256": PDF_SHA,
        "filename": "informe.pdf",
        "content_type": "application/pdf",
        "size": len(PDF_CONTENT),
        "part_index": 2,
        "stored": True,
    }
    assert render_attachment_front_lines(entry) == [
        "  - sha256: " + PDF_SHA,
        "    filename: informe.pdf",
        "    content_type: application/pdf",
        "    size: " + str(len(PDF_CONTENT)),
        "    part_index: 2",
        "    stored: true",
    ]


def test_render_neutralizes_control_chars_in_filename(tmp_path):
    entry = {"sha256": PDF_SHA, "filename": "bad\x0a\x1fname.pdf",
             "content_type": "application/pdf", "size": 1,
             "part_index": 0, "stored": False}
    lines = render_attachment_front_lines(entry)
    assert lines[1] == "    filename: bad??name.pdf"


def test_persist_legacy_hash_frontmatter_still_round_trips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record = parse_raw_email(MULTIPART_RAW, "personal")
    persist_email_okf(record, "legacy.md")
    text = (tmp_path / "legacy.md").read_text(encoding="utf-8")
    assert "  - " + PDF_SHA in text
    entries = read_attachment_entries(text)
    assert [entry["sha256"] for entry in entries] == [PDF_SHA, PDF_SHA]
    assert all(entry["stored"] is False for entry in entries)
    # Un nodo persistido antes del cambio (hashes sueltos) se lee igual.
    legacy_node = (
        "---\ntype: Email Message\nattachments:\n  - " + PDF_SHA + "\n---\ncuerpo\n"
    )
    assert read_attachment_entries(legacy_node)[0]["sha256"] == PDF_SHA


def test_persist_full_metadata_and_read_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record = parse_raw_email(MULTIPART_RAW, "personal")
    record["attachments"] = full_entries(record["attachments"])
    persist_email_okf(record, "full.md")
    text = (tmp_path / "full.md").read_text(encoding="utf-8")
    entries = read_attachment_entries(text)
    assert len(entries) == 2
    for index, entry in enumerate(entries):
        assert entry["sha256"] == PDF_SHA
        assert entry["filename"] == "informe.pdf"
        assert entry["content_type"] == "application/pdf"
        assert entry["size"] == len(PDF_CONTENT)
        assert entry["part_index"] == index
        assert entry["stored"] is False


def test_read_accepts_mixed_and_attachments_stored_flag():
    node = (
        "---\n"
        "attachments_stored: true\n"
        "attachments:\n"
        "  - " + PDF_SHA + "\n"
        "  - sha256: " + PDF_SHA + "\n"
        "    filename: informe.pdf\n"
        "    content_type: application/pdf\n"
        "    size: 5\n"
        "    part_index: 1\n"
        "    stored: false\n"
        "    skipped: size-limit-exceeded\n"
        "---\n"
        "cuerpo\n"
    )
    entries = read_attachment_entries(node)
    assert entries[0]["stored"] is True  # hereda attachments_stored
    assert entries[0]["filename"] == ""
    assert entries[1]["stored"] is False
    assert entries[1]["skipped"] == "size-limit-exceeded"
    assert entries[1]["part_index"] == 1


# ---------------------------------------------------------------------------
# Listado: metadatos sin abrir ni leer blobs.
# ---------------------------------------------------------------------------


def test_list_attachments_uses_frontmatter_only_and_sanitizes_display():
    entries = [
        {"sha256": PDF_SHA, "filename": "informe.pdf", "content_type": "application/pdf",
         "size": len(PDF_CONTENT), "part_index": 0, "stored": True},
        {"sha256": PDF_SHA, "filename": "../../evil", "content_type": "application/pdf",
         "size": 3, "part_index": 1, "stored": False, "skipped": "type-not-allowed"},
        {"sha256": PDF_SHA, "filename": "", "part_index": 2},
    ]
    rows = list_attachments(entries)
    assert rows[0]["display"] == "informe.pdf"
    assert rows[0]["sha256_short"] == PDF_SHA[:12]
    assert rows[0]["status"] == "stored"
    assert rows[1]["display"] == "evil"
    assert rows[1]["status"] == "not-stored"
    assert rows[1]["skipped"] == "type-not-allowed"
    assert rows[2]["display"] == "attachment-2"


def test_list_node_attachments_reads_node_never_blobs(tmp_path):
    from src.email.persist_at import persist_email_okf_at

    root = str(tmp_path / "store")
    record = parse_raw_email(MULTIPART_RAW, "personal")
    record["attachments"] = full_entries(record["attachments"])
    target = persist_email_okf_at(record, root, "nodos/msg.md")
    rows = list_node_attachments(root, "nodos/msg.md")
    assert Path(target).exists()
    assert not (tmp_path / "store" / "attachments").exists(), (
        "el listado materializo blobs que no existian"
    )
    assert rows[0]["status"] == "not-stored"
    assert rows[0]["sha256_short"] == PDF_SHA[:12]
    assert rows[0]["display"] == "informe.pdf"


# ---------------------------------------------------------------------------
# Errores sanitizados: sin rutas absolutas ni secretos.
# ---------------------------------------------------------------------------


def test_errors_are_sanitized_no_absolute_paths(tmp_path):
    root = tmp_path / "store"
    cases = (
        {"sha256": "no-es-hex", "content": b"x", "metadata": {}, "authorize": True},
        {"sha256": PDF_SHA, "content": PDF_CONTENT, "metadata": {}, "authorize": False},
    )
    for kwargs in cases:
        with pytest.raises(AttachmentError) as excinfo:
            store_attachment_bytes(root, **kwargs)
        message = excinfo.value.message
        assert str(tmp_path) not in message
        assert str(root) not in message
        assert "C:\\" not in message


def test_hash_mismatch_message_uses_relative_path_only(tmp_path):
    root = tmp_path / "store"
    store_attachment_bytes(root, PDF_SHA, PDF_CONTENT, {}, authorize=True)
    blob_path(root, PDF_SHA).write_bytes(b"corrupto")
    with pytest.raises(AttachmentError) as excinfo:
        store_attachment_bytes(root, PDF_SHA, PDF_CONTENT, {}, authorize=True)
    assert excinfo.value.code == "hash-mismatch"
    message = excinfo.value.message
    assert str(root) not in message
    assert str(tmp_path) not in message
    assert blob_rel_path(PDF_SHA) in message


def test_invalid_sha256_is_rejected_before_any_write(tmp_path):
    root = tmp_path / "store"
    for bad in ("", "ABC", "g" * 64, PDF_SHA + "ff"):
        with pytest.raises(AttachmentError) as excinfo:
            blob_path(root, bad)
        assert excinfo.value.code == "hash-mismatch"
    assert not (root / "attachments").exists()


# ---------------------------------------------------------------------------
# Layout: dos niveles de sharding y meta junto al blob.
# ---------------------------------------------------------------------------


def test_layout_uses_two_sharding_levels():
    sha = "ab" + "cd" + "e" * 60
    assert blob_rel_path(sha) == "attachments/ab/cd/" + sha
    assert meta_path("root", sha) == Path("root") / "attachments" / (sha + ".meta")