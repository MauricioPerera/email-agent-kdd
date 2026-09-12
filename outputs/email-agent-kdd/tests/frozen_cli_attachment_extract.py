"""Pruebas offline del extractor de texto de adjuntos ya almacenados."""

import hashlib
import importlib
import json
import sys
import pytest


def _pdf_bytes():
    stream = b"BT /F1 12 Tf 72 720 Td (Texto PDF de prueba) Tj ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def test_oversized_blob_is_read_with_bound_before_scanning(tmp_path, monkeypatch):
    from pathlib import Path
    from src.email import attachments
    import pytest
    content = b'x' * 20
    digest = hashlib.sha256(content).hexdigest()
    blob = attachments.blob_path(str(tmp_path), digest)
    blob.parent.mkdir(parents=True)
    blob.write_bytes(content)
    original_open = Path.open
    reads = []
    class Reader:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            reads.append(limit)
            return content[:limit]
    def bounded_open(path, *args, **kwargs):
        return Reader() if path == blob else original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', bounded_open)
    scans = []
    with pytest.raises(attachments.AttachmentError) as exc:
        attachments.extract_text_from_blob(str(tmp_path),
            {'sha256': digest, 'filename': 'test.txt', 'content_type': 'text/plain'},
            max_bytes=10, scanner=lambda data: scans.append(data))
    assert exc.value.code == 'size-limit-exceeded'
    assert reads == [11]
    assert scans == []


def _node(root, content, *, content_type="text/plain", stored=True):
    digest = hashlib.sha256(content).hexdigest()
    node = root / "store" / "mail.md"
    node.parent.mkdir(parents=True)
    node.write_text(
        "---\nattachments:\n  - sha256: %s\n    filename: note.txt\n    content_type: %s\n    size: %d\n    part_index: 0\n    stored: %s\n---\nMensaje\n"
        % (digest, content_type, len(content), str(stored).lower()),
        encoding="utf-8",
    )
    return digest


def _blob(cli, root, content):
    digest = hashlib.sha256(content).hexdigest()
    blob = cli.blob_path(str(root), digest)
    blob.parent.mkdir(parents=True)
    blob.write_bytes(content)


def test_attachment_extracta_texto_local_sin_red(tmp_path, capsys, monkeypatch):
    cli = importlib.import_module("src.email.cli")
    attachments = importlib.import_module("src.email.attachments")
    monkeypatch.setattr(
        cli,
        "extract_text_from_blob",
        lambda root, entry: attachments.extract_text_from_blob(
            root, entry, scanner=lambda _: "clean"
        ),
    )
    content = "Hola, mundo\n".encode("utf-8")
    digest = _node(tmp_path, content)
    _blob(cli, tmp_path, content)

    code = cli.cli_main([
        "attachment", "extract", str(tmp_path), "store/mail.md", "0",
        "out/note.txt", "CONFIRMAR", "EXTRACCION",
    ])

    assert code == 0
    assert (tmp_path / "out/note.txt").read_text(encoding="utf-8") == "Hola, mundo\n"
    assert json.loads(capsys.readouterr().out)["sha256"] == digest


def test_attachment_extract_rechaza_tipo_no_soportado(tmp_path, capsys):
    cli = importlib.import_module("src.email.cli")
    content = b"pdf"
    digest = _node(tmp_path, content, content_type="application/pdf")
    _blob(cli, tmp_path, content)

    code = cli.cli_main([
        "attachment", "extract", str(tmp_path), "store/mail.md", "0",
        "out.txt", "CONFIRMAR", "EXTRACCION",
    ])
    assert code == 1
    assert not (tmp_path / "out.txt").exists()
    assert digest in cli.blob_path(str(tmp_path), digest).name
    assert "traceback" not in capsys.readouterr().err.lower()


def test_attachment_extracta_pdf_despues_del_gate(tmp_path, monkeypatch):
    cli = importlib.import_module("src.email.cli")
    attachments = importlib.import_module("src.email.attachments")
    content = _pdf_bytes()
    digest = _node(tmp_path, content, content_type="application/pdf")
    _blob(cli, tmp_path, content)
    if sys.platform != "linux":
        with pytest.raises(attachments.AttachmentError) as exc:
            attachments.extract_text_from_blob(str(tmp_path),
                {"sha256": digest, "filename": "source.pdf", "content_type": "application/pdf"},
                scanner=lambda _: "clean")
        assert exc.value.code == "pdf-sandbox-unavailable"
        return
    result = attachments.extract_text_from_blob(
        str(tmp_path),
        {"sha256": digest, "filename": "source.pdf", "content_type": "application/pdf"},
        scanner=lambda _: "clean",
    )
    assert "Texto PDF de prueba" in result["text"]


@pytest.mark.parametrize('scan_result', ['infected', 'unavailable', 'error'])
def test_pdf_never_starts_before_antivirus_approval(tmp_path, monkeypatch, scan_result):
    from src.email import attachments, pdf_sandbox
    cli = importlib.import_module('src.email.cli')
    content = _pdf_bytes()
    digest = _node(tmp_path, content, content_type='application/pdf')
    _blob(cli, tmp_path, content)
    def forbidden(*args):
        raise AssertionError('parser started before scan approval')
    monkeypatch.setattr(pdf_sandbox, 'run_pdf', forbidden)
    monkeypatch.setattr(attachments, 'scan_bytes', lambda *args: scan_result)
    with pytest.raises(attachments.AttachmentError) as caught:
        attachments.extract_text_from_blob(str(tmp_path),
            {'sha256': digest, 'filename': 'test.pdf', 'content_type': 'application/pdf'})
    assert caught.value.code == 'antivirus-' + scan_result


def test_attachment_extract_rechaza_pdf_corrupto_despues_del_gate(tmp_path):
    attachments = importlib.import_module("src.email.attachments")
    content = b"%PDF-corrupto"
    digest = _node(tmp_path, content, content_type="application/pdf")
    _blob(importlib.import_module("src.email.cli"), tmp_path, content)
    try:
        attachments.extract_text_from_blob(
            str(tmp_path),
            {"sha256": digest, "filename": "broken.pdf", "content_type": "application/pdf"},
            scanner=lambda _: "clean",
        )
    except attachments.AttachmentError as exc:
        assert exc.code == ("pdf-rejected" if sys.platform == "linux" else "pdf-sandbox-unavailable")
    else:
        raise AssertionError("un PDF corrupto debe rechazarse")
