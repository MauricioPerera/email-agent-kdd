"""Pruebas offline del extractor de texto de adjuntos ya almacenados."""

import hashlib
import importlib
import json


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
