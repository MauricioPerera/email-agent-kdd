# frozen_cli_attachments_list.py — Oracle del comando `attachment list ROOT REL_PATH`
# sobre src/email/cli.py con un store FALSO en tmp_path (nodos .md escritos a mano).
# Sin red, sin IMAP, sin abrir blobs: el store ni siquiera tiene directorio
# `attachments/`, y el comando igualmente funciona (solo lee el nodo).
#
# Verifica:
# - dispatch y sintaxis exacta `attachment list ROOT REL_PATH` (una accion: list).
# - salida JSON estable: una linea por adjunto con las claves exactas
#   (index, display, content_type, size, sha256, sha256_short, status, skipped)
#   y status stored|not-stored derivado SOLO del frontmatter (nunca del disco).
# - compatibilidad: formato nuevo (mapas) y formato antiguo (solo hashes),
#   nodo sin adjuntos (exit 0, stdout vacio).
# - resolucion segura de REL_PATH: traversal/absoluta/\\ => codigo 2.
# - codigos: 0 exito, 1 fallo de operacion (nodo inexistente), 2 error de
#   argumentos (aridad, accion invalida, rel_path insegura).
# - errores sanitizados: sin rutas absolutas de ROOT, sin tracebacks.

import json

import pytest

from src.email import cli as cli_mod

ROW_KEYS = {
    "index", "display", "content_type", "size",
    "sha256", "sha256_short", "status", "skipped",
}

SHA_A = "ab" + "c" * 62
SHA_B = "de" + "f" * 62


def _write_node(root, rel_path, body_lines):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(body_lines) + "\n---\n\nCuerpo.\n", encoding="utf-8")


def _store_with_node(tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    return root


def _output(capsys):
    captured = capsys.readouterr()
    return captured.out, captured.err


def test_list_nodo_formato_nuevo_devuelve_json_estable(tmp_path, capsys):
    root = _store_with_node(tmp_path)
    _write_node(root, "inbox/2026/m1.md", [
        "attachments:",
        "  - sha256: " + SHA_A,
        "    filename: informe anual.pdf",
        "    content_type: application/pdf",
        "    size: 1234",
        "    part_index: 0",
        "    stored: false",
        "  - sha256: " + SHA_B,
        "    filename: datos.csv",
        "    content_type: text/csv",
        "    size: 42",
        "    part_index: 1",
        "    stored: true",
    ])
    code = cli_mod.cli_main(["attachment", "list", str(root), "inbox/2026/m1.md"])
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert [row["index"] for row in rows] == [0, 1]
    for row in rows:
        assert set(row) == ROW_KEYS
    assert rows[0]["status"] == "not-stored"
    assert rows[0]["display"] == "informe anual.pdf"
    assert rows[0]["content_type"] == "application/pdf"
    assert rows[0]["size"] == 1234
    assert rows[0]["sha256"] == SHA_A
    assert rows[0]["sha256_short"] == SHA_A[:12]
    assert rows[0]["skipped"] is None
    assert rows[1]["status"] == "stored"
    assert rows[1]["sha256_short"] == SHA_B[:12]


def test_list_formato_antiguo_solo_hashes(tmp_path, capsys):
    root = _store_with_node(tmp_path)
    _write_node(root, "inbox/m2.md", [
        "attachments:",
        "  - " + SHA_A,
        "  - " + SHA_B,
    ])
    code = cli_mod.cli_main(["attachment", "list", str(root), "inbox/m2.md"])
    assert code == 0
    out, _ = _output(capsys)
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert [row["sha256"] for row in rows] == [SHA_A, SHA_B]
    for index, row in enumerate(rows):
        assert row["status"] == "not-stored"
        assert row["display"] == "attachment-" + str(index)
        assert set(row) == ROW_KEYS


def test_list_nodo_sin_adjuntos_stdout_vacio(tmp_path, capsys):
    root = _store_with_node(tmp_path)
    _write_node(root, "inbox/m3.md", ["subject: hola"])
    code = cli_mod.cli_main(["attachment", "list", str(root), "inbox/m3.md"])
    assert code == 0
    out, err = _output(capsys)
    assert out == "" and err == ""


def test_list_no_abre_blobs_ni_conecta(tmp_path, capsys):
    root = _store_with_node(tmp_path)
    _write_node(root, "inbox/m4.md", [
        "attachments:",
        "  - sha256: " + SHA_A,
        "    filename: solo-metadatos.pdf",
        "    content_type: application/pdf",
        "    size: 7",
        "    part_index: 0",
        "    stored: true",
    ])
    assert not (root / "attachments").exists()
    code = cli_mod.cli_main(["attachment", "list", str(root), "inbox/m4.md"])
    assert code == 0, "listar metadatos no debe requerir blobs en disco"
    out, _ = _output(capsys)
    # El estado viene SOLO del frontmatter (stored: true): el comando nunca
    # comprueba blobs en disco ni toca la red.
    assert json.loads(out.strip())["status"] == "stored"


def test_aridad_y_accion_invalidas_devuelven_2(tmp_path, capsys):
    root = _store_with_node(tmp_path)
    bad_cases = [
        ["attachment"],
        ["attachment", "download"],
        ["attachment", "list"],
        ["attachment", "list", str(root)],
        ["attachment", "list", str(root), "inbox/x.md", "extra"],
        ["attachment", "LIST", str(root), "inbox/x.md"],
    ]
    for argv in bad_cases:
        code = cli_mod.cli_main(argv)
        assert code == 2, "argv " + repr(argv) + " debe dar 2"
        out, err = _output(capsys)
        assert out.strip() == ""
        assert "usage:" in err.lower()
        assert "traceback" not in err.lower()


def test_rel_path_insegura_devuelve_2(tmp_path, capsys):
    root = _store_with_node(tmp_path)
    _write_node(root, "inbox/ok.md", ["subject: x"])
    unsafe = [
        "../inbox/ok.md",
        "inbox/../ok.md",
        "inbox/ok.md/",
        "inbox\\ok.md",
        "C:inbox/ok.md",
        "~/inbox/ok.md",
        "/etc/passwd.md",
        "",
    ]
    for rel in unsafe:
        code = cli_mod.cli_main(["attachment", "list", str(root), rel])
        assert code == 2, "rel_path " + repr(rel) + " debe dar 2"
        out, err = _output(capsys)
        assert out.strip() == ""
        assert "traceback" not in err.lower()


def test_nodo_inexistente_devuelve_1_sin_ruta_absoluta(tmp_path, capsys):
    root = _store_with_node(tmp_path)
    code = cli_mod.cli_main(["attachment", "list", str(root), "inbox/falta.md"])
    assert code == 1
    out, err = _output(capsys)
    assert out.strip() == ""
    assert "fallo" in err.lower() or "error" in err.lower()
    assert str(root.resolve()) not in err
    assert "traceback" not in err.lower()


def test_help_documenta_attachment_list(capsys):
    code = cli_mod.cli_main(["--help"])
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    assert "attachment list ROOT REL_PATH" in out