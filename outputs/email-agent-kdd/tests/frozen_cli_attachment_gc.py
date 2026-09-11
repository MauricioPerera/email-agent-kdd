# frozen_cli_attachment_gc.py — Oracle del comando `attachment gc` sobre
# src/email/cli.py con un store FALSO en tmp_path. Sin red, sin IMAP.
#
# Verifica:
# - sintaxis exacta: `attachment gc ROOT` (dry-run JSON, exit 0, cero
#   mutaciones) y `attachment gc ROOT CONFIRMAR BORRADO ADJUNTOS` (ejecucion
#   autorizada). Otra aridad => codigo 2.
# - confirmacion exacta validada ANTES de mutar: frase ausente/incorrecta
#   => codigo 1 y cero borrados.
# - salida JSON estable que lista candidatos y eliminados, con `deleted`,
#   `candidates`, `corrupt`, `failed`, sin rutas absolutas ni tracebacks.
# - preservar referencias, excluir .trash, blobs corruptos nunca borrados,
#   fallo parcial (exit 1, un solo fallo detiene todo) e idempotencia.

import hashlib
import json

import pytest

from src.email import cli as cli_mod


def _sha(content):
    return hashlib.sha256(content).hexdigest()


CONTENT_A = b"referido-por-nodo-activo"
CONTENT_B = b"huerfano-a-borrar"
CONTENT_BAD = b"contenido-corrupto-que-no-coincide"
SHA_A = _sha(CONTENT_A)
SHA_B = _sha(CONTENT_B)
SHA_BAD = "ee" + "4" * 62  # blob corrupto: el nombre NO es el hash del contenido


def _write_node(root, rel_path, sha):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nsubject: prueba\nattachments:\n"
        "  - sha256: " + sha + "\n"
        "    filename: doc.pdf\n"
        "    content_type: application/pdf\n"
        "    size: " + str(24) + "\n"
        "    part_index: 0\n"
        "    stored: true\n"
        "---\n\nCuerpo.\n",
        encoding="utf-8",
    )


def _write_blob(root, sha, content):
    path = root / "attachments" / sha[:2] / sha[2:4] / sha
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    (root / "attachments" / (sha + ".meta")).write_text(
        json.dumps({"sha256": sha}) + "\n", encoding="utf-8"
    )


def _blob_rel(sha):
    return "attachments/" + sha[:2] + "/" + sha[2:4] + "/" + sha


def _store_basico(root):
    root.mkdir(parents=True, exist_ok=True)
    _write_node(root, "store/emails/inbox/m1.md", SHA_A)
    _write_blob(root, SHA_A, CONTENT_A)
    _write_blob(root, SHA_B, CONTENT_B)


def _payload(capsys):
    captured = capsys.readouterr()
    return captured.out, captured.err


def _parse(out):
    return json.loads(out.strip())


def test_aridad_invalida_devuelve_2(tmp_path, capsys):
    root = tmp_path / "root"
    _store_basico(root)
    bad_cases = [
        ["attachment", "gc"],
        ["attachment", "gc", str(root), "CONFIRMAR", "BORRADO"],
        ["attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS", "extra"],
    ]
    for argv in bad_cases:
        code = cli_mod.cli_main(argv)
        assert code == 2, "argv " + repr(argv) + " debe dar 2"
        out, err = capsys.readouterr()
        assert out.strip() == ""
        assert "usage:" in err.lower()
        assert "traceback" not in err.lower()


def test_root_inexistente_devuelve_2(tmp_path, capsys):
    code = cli_mod.cli_main(["attachment", "gc", str(tmp_path / "falta")])
    assert code == 2
    out, err = capsys.readouterr()
    assert out.strip() == ""
    assert "traceback" not in err.lower()


def test_dry_run_lista_candidatos_y_no_borra_nada(tmp_path, capsys):
    root = tmp_path / "root"
    _store_basico(root)
    before = sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())
    code = cli_mod.cli_main(["attachment", "gc", str(root)])
    assert code == 0
    out, err = capsys.readouterr()
    assert err == ""
    payload = _parse(out)
    assert payload["mode"] == "dry-run"
    assert payload["deleted"] == []
    assert payload["failed"] == []
    assert {item["sha256"] for item in payload["candidates"]} == {SHA_B}
    assert payload["referenced_count"] == 1
    assert sorted(
        str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()
    ) == before, "el dry-run no debe borrar ni mover nada"
    assert str(root.resolve()) not in out


def test_confirmacion_incorrecta_devuelve_1_sin_borrar(tmp_path, capsys):
    root = tmp_path / "root"
    _store_basico(root)
    bad_cases = [
        ["attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS "],
        ["attachment", "gc", str(root), "CONFIRMAR", "EXTRACCION", "ADJUNTOS"],
        ["attachment", "gc", str(root), "confirmar", "borrado", "adjuntos"],
    ]
    for argv in bad_cases:
        code = cli_mod.cli_main(argv)
        assert code == 1, "argv " + repr(argv) + " debe dar 1"
        out, err = capsys.readouterr()
        assert out.strip() == ""
        assert "confirmacion" in err.lower()
        assert "traceback" not in err.lower()
    assert (root / "attachments" / (SHA_B + ".meta")).exists()
    assert (root / "attachments" / SHA_B[:2] / SHA_B[2:4] / SHA_B).exists()


def test_ejecucion_autorizada_borra_huerfano_y_preserva_referenciado(tmp_path, capsys):
    root = tmp_path / "root"
    _store_basico(root)
    code = cli_mod.cli_main([
        "attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS",
    ])
    assert code == 0
    out, err = capsys.readouterr()
    assert err == ""
    payload = _parse(out)
    assert payload["mode"] == "executed"
    assert sorted(payload["deleted"]) == sorted([_blob_rel(SHA_B), "attachments/" + SHA_B + ".meta"])
    assert payload["failed"] == []
    assert not (root / "attachments" / (SHA_B + ".meta")).exists()
    assert not (root / "attachments" / SHA_B[:2] / SHA_B[2:4] / SHA_B).exists()
    # El blob referenciado por el nodo activo queda intacto con su .meta.
    assert (root / "attachments" / (SHA_A + ".meta")).exists()
    assert (root / "attachments" / SHA_A[:2] / SHA_A[2:4] / SHA_A).read_bytes() == CONTENT_A
    blob_item = next(item for item in payload["candidates"] if item["sha256"] == SHA_B)
    assert blob_item["blob"] == _blob_rel(SHA_B)
    assert blob_item["meta"] == "attachments/" + SHA_B + ".meta"
    assert str(root.resolve()) not in out and str(root.resolve()) not in err


def test_blob_corrupto_se_lista_y_nunca_se_bora(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    _write_blob(root, SHA_BAD, CONTENT_BAD)
    code = cli_mod.cli_main([
        "attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS",
    ])
    assert code == 0
    payload = _parse(capsys.readouterr().out)
    assert [item["sha256"] for item in payload["corrupt"]] == [SHA_BAD]
    assert payload["candidates"] == []
    assert payload["deleted"] == []
    assert (root / "attachments" / SHA_BAD[:2] / SHA_BAD[2:4] / SHA_BAD).exists()
    assert (root / "attachments" / (SHA_BAD + ".meta")).exists()


def test_store_ausente_devuelve_1_sin_borrar(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    _write_blob(root, SHA_B, CONTENT_B)
    code = cli_mod.cli_main(["attachment", "gc", str(root)])
    assert code == 1
    out, err = capsys.readouterr()
    assert out.strip() == ""
    assert "no se borro nada" in err
    assert "traceback" not in err.lower()
    assert (root / "attachments" / (SHA_B + ".meta")).exists()


def test_fallo_parcial_devuelve_1_y_detiene_todo(tmp_path, capsys, monkeypatch):
    root = tmp_path / "root"
    _store_basico(root)
    original_unlink = type(root / "x").unlink

    def failing_unlink(self, *args, **kwargs):
        if self.name == SHA_B:
            raise PermissionError("bloqueado")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.unlink", failing_unlink)
    code = cli_mod.cli_main([
        "attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS",
    ])
    monkeypatch.undo()
    assert code == 1
    out, err = capsys.readouterr()
    payload = _parse(out)
    assert payload["failed"][0]["error"] == "io-error"
    assert payload["failed"][0]["path"] == _blob_rel(SHA_B)
    assert payload["deleted"] == []
    assert "traceback" not in err.lower()
    assert str(root.resolve()) not in err
    # Nada mas se borro: el .meta y el otro blob siguen intactos.
    assert (root / "attachments" / (SHA_B + ".meta")).exists()
    assert (root / "attachments" / (SHA_A + ".meta")).exists()


def test_idempotencia_segunda_ejecucion_sin_candidatos(tmp_path, capsys):
    root = tmp_path / "root"
    _store_basico(root)
    assert cli_mod.cli_main([
        "attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS",
    ]) == 0
    capsys.readouterr()
    after = sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())
    code = cli_mod.cli_main([
        "attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS",
    ])
    assert code == 0
    payload = _parse(capsys.readouterr().out)
    assert payload["candidates"] == []
    assert payload["deleted"] == []
    assert sorted(
        str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()
    ) == after


def test_exclusion_de_trash_via_cli(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    (root / "store" / "emails").mkdir(parents=True)
    (root / "store" / "emails" / "activo.md").write_text(
        "---\nsubject: sin adjuntos\n---\n\nCuerpo.\n", encoding="utf-8"
    )
    _write_blob(root, SHA_B, CONTENT_B)
    _write_node(root, ".trash/store/emails/viejo.md", SHA_B)
    code = cli_mod.cli_main([
        "attachment", "gc", str(root), "CONFIRMAR", "BORRADO", "ADJUNTOS",
    ])
    assert code == 0
    payload = _parse(capsys.readouterr().out)
    assert _blob_rel(SHA_B) in payload["deleted"]


def test_list_y_download_siguen_intactos(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir(parents=True)
    _write_node(root, "store/emails/inbox/m1.md", SHA_A)
    code = cli_mod.cli_main(["attachment", "list", str(root), "store/emails/inbox/m1.md"])
    assert code == 0
    row = _parse(capsys.readouterr().out)
    assert row["sha256"] == SHA_A
    code = cli_mod.cli_main(["attachment", "bogus", str(root)])
    assert code == 2
    _, err = capsys.readouterr()
    assert "list" in err and "download" in err and "gc" in err


def test_help_documenta_attachment_gc(capsys):
    assert cli_mod.cli_main(["--help"]) == 0
    out, _ = capsys.readouterr()
    assert "attachment gc ROOT" in out