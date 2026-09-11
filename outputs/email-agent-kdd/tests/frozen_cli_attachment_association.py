# frozen_cli_attachment_association.py — Oracle de la asociacion OKF posterior
# a `attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION` sobre
# src/email/cli.py con un IMAP FALSO (fabrica inyectada sobre
# imap_reader.imaplib.IMAP4_SSL) y un store temporal en tmp_path.
# Sin red, sin credenciales reales, sin sockets.
#
# Verifica:
# - tras extraccion y copia exitosas el nodo original se reescribe
#   ATOMICAMENTE marcando `stored: true` SOLO en la entrada del part_index
#   descargado; el resto de metadatos, otras entradas y el cuerpo quedan
#   intactos byte a byte.
# - `attachment list` despues de la descarga informa `status: stored` para el
#   indice descargado y `not-stored` para los demas (y sin tocar blobs).
# - el nodo usa formato legacy de hashes => error claro ANTES de conectar o
#   escribir el DEST: sin blob, sin copia, nodo sin cambios.
# - si la asociacion falla: rollback sin corrupcion (nodo intacto, sin
#   `.tmp` residual y copia en DEST retirada).
# - segunda descarga idempotente: el nodo queda con la marca y no se corrompe.
# - errores sin secretos ni rutas absolutas ni tracebacks.

import hashlib
import json

import pytest

from email.message import EmailMessage

from src.email import cli as cli_mod
from src.email import imap_reader
from src.email.account import create_email_account
from src.email.account_store import save_email_account
from src.email.attachments import blob_path
from src.email.mail_server_store import store_mail_server_config

PHRASE = "CONFIRMAR EXTRACCION"
SECRETO = "SECRETO-ASOCIACION-FKE-NO-REAL"

CONTENT_A = b"contenido del primer adjunto\n" * 3
CONTENT_B = b"segundo adjunto, distinto del primero\n"


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _message_bytes(attachments):
    """RFC822 con adjuntos: lista de (contenido, filename, content_type)."""
    message = EmailMessage()
    message["From"] = "remite@example.test"
    message["To"] = "yo@example.test"
    message["Subject"] = "con adjuntos"
    message.set_content("cuerpo sin adjuntos")
    for content, filename, content_type in attachments:
        main_type, sub_type = content_type.split("/", 1)
        message.add_attachment(
            content, maintype=main_type, subtype=sub_type, filename=filename
        )
    return message.as_bytes()


class _FakeConnection:
    """Conexion IMAP falsa: registra llamadas, nunca abre sockets."""

    def __init__(self, fake, host, port):
        self._fake = fake
        self._host = host
        self._port = port

    def login(self, username, password):
        self._fake.calls.append(("login", username, password))

    def select(self, mailbox, readonly=False):
        self._fake.calls.append(("select", mailbox, readonly))
        return ("OK", [b"1 EXISTS"])

    def fetch(self, message_set, spec):
        self._fake.calls.append(("fetch", message_set, spec))
        return ("OK", [(b"1 (RFC822 {%d}" % len(self._fake.raw), self._fake.raw), b")"])

    def close(self):
        pass

    def logout(self):
        pass


class _FakeIMAPFactory:
    """Fabrica falsa de imaplib.IMAP4_SSL: una sola instancia compartida."""

    def __init__(self):
        self.calls = []
        self.raw = b""

    def __call__(self, host, port):
        self.calls.append(("connect", host, port))
        return _FakeConnection(self, host, port)


def _write_node(root, rel_path, lines):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(lines) + "\n---\n\nCuerpo del mensaje.\n",
        encoding="utf-8",
    )


def _node_lines(attachments, extra_fields=None):
    lines = [
        "type: Email Message",
        "account_id: personal",
        "imap_uid: 7",
        "subject: con adjuntos",
    ]
    if extra_fields:
        lines.extend(extra_fields)
    lines.append("attachments:")
    for index, (content, filename, content_type) in enumerate(attachments):
        lines.extend([
            "  - sha256: " + _sha(content),
            "    filename: " + filename,
            "    content_type: " + content_type,
            "    size: " + str(len(content)),
            "    part_index: " + str(index),
            "    stored: false",
        ])
    return lines


def _setup(tmp_path, monkeypatch, attachments=None, node_lines=None,
           rel_path="inbox/m1.md"):
    """Store temporal: cuenta guardada + servidores + nodo con adjuntos."""
    root = tmp_path / "store"
    root.mkdir(exist_ok=True)
    account = create_email_account(
        "personal", "gmail", "yo@example.test", "env://TEST_ASSOC_PW"
    )
    save_email_account(str(root), account)
    store_mail_server_config(
        str(root),
        "personal",
        {
            "imap_host": "imap.saved.test",
            "imap_port": 1143,
            "smtp_host": "smtp.saved.test",
            "smtp_port": 2587,
        },
    )
    monkeypatch.setenv("TEST_ASSOC_PW", SECRETO)
    if attachments is None:
        attachments = [
            (CONTENT_A, "informe anual.pdf", "application/pdf"),
            (CONTENT_B, "datos.csv", "text/csv"),
        ]
    if node_lines is None:
        node_lines = _node_lines(attachments)
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(node_lines) + "\n---\n\nCuerpo del mensaje.\n",
        encoding="utf-8",
    )
    fake = _FakeIMAPFactory()
    fake.raw = _message_bytes(attachments)
    monkeypatch.setattr(imap_reader.imaplib, "IMAP4_SSL", fake)
    return root, fake


def _output(capsys):
    captured = capsys.readouterr()
    return captured.out, captured.err


def _run_download(root, rel_path, index, dest):
    return cli_mod.cli_main([
        "attachment", "download", str(root), rel_path, str(index), dest,
        *PHRASE.split(),
    ])


def _run_list(root, rel_path):
    return cli_mod.cli_main(["attachment", "list", str(root), rel_path])


def test_descarga_marca_stored_true_solo_en_el_indice_y_list_lo_informa(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch)
    node_path = root / "inbox" / "m1.md"
    before = node_path.read_text(encoding="utf-8")
    code = _run_download(root, "inbox/m1.md", 1, "salidas/datos.csv")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    assert json.loads(out.strip())["sha256"] == _sha(CONTENT_B)
    # el nodo cambio EXACTAMENTE en la linea stored del indice 1
    after = node_path.read_text(encoding="utf-8")
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    assert len(before_lines) == len(after_lines), "solo cambia la linea stored"
    differences = [
        (i, before_lines[i], after_lines[i])
        for i in range(len(before_lines))
        if before_lines[i] != after_lines[i]
    ]
    assert len(differences) == 1, differences
    position, old, new = differences[0]
    assert old.strip() == "stored: false" and new.strip() == "stored: true"
    assert old == new.replace("true", "false"), "solo cambia el valor de stored"
    assert after_lines[position - 1].strip() == "part_index: 1", (
        "la marca cae en la entrada descargada"
    )
    assert "Cuerpo del mensaje." in after
    assert "    part_index: 0\n" in after, "el otro adjunto conserva su entrada"
    assert after.count("stored: false") == 1
    assert not list(root.rglob("*.tmp")), "sin residuos .tmp tras el exito"
    # `attachment list` ahora informa stored=true SOLO para el indice descargado
    code = _run_list(root, "inbox/m1.md")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert [row["status"] for row in rows] == ["not-stored", "stored"]
    assert rows[1]["sha256"] == _sha(CONTENT_B)
    # la copia en DEST y el blob siguen con el contenido verificado
    assert (root / "salidas" / "datos.csv").read_bytes() == CONTENT_B
    assert blob_path(root, _sha(CONTENT_B)).read_bytes() == CONTENT_B


def test_segunda_descarga_idempotente_no_corrompe_el_nodo(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch)
    node_path = root / "inbox" / "m1.md"
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 0
    _output(capsys)
    after_first = node_path.read_text(encoding="utf-8")
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    assert json.loads(out.strip())["idempotent"] is True
    assert node_path.read_text(encoding="utf-8") == after_first, (
        "re-asociar un adjunto ya marcado no reescribe el nodo"
    )
    assert not list(root.rglob("*.tmp"))


def test_nodo_legacy_de_hashes_rechazado_antes_de_conectar_o_escribir(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch)
    legacy_path = root / "inbox" / "legacy.md"
    legacy_text = (
        "---\n"
        "account_id: personal\n"
        "imap_uid: 7\n"
        "subject: viejo\n"
        "attachments:\n"
        "  - " + _sha(CONTENT_A) + "\n"
        "  - " + _sha(CONTENT_B) + "\n"
        "---\n\nCuerpo.\n"
    )
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_text(legacy_text, encoding="utf-8")
    code = _run_download(root, "inbox/legacy.md", 0, "salidas/informe.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert "formato antiguo" in err.lower() or "legacy" in err.lower()
    assert "traceback" not in err.lower()
    assert fake.calls == [], "un nodo legacy no debe conectarse"
    assert not (root / "attachments").exists(), "sin blob para un nodo legacy"
    assert not (root / "salidas" / "informe.pdf").exists(), "sin copia en DEST"
    assert legacy_path.read_text(encoding="utf-8") == legacy_text, (
        "el nodo legacy no se reescribe silenciosamente"
    )
    assert SECRETO not in out + err
    assert str(root.resolve()) not in out + err


def test_fallo_de_asociacion_rollback_nodo_intacto_y_dest_retirado(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch)
    node_path = root / "inbox" / "m1.md"
    before = node_path.read_text(encoding="utf-8")

    def _failing_write(root_arg, rel_path_arg, node_text):
        raise OSError("escritura simulada fallida")

    monkeypatch.setattr(cli_mod, "write_node_text_atomic", _failing_write)
    code = _run_download(root, "inbox/m1.md", 1, "salidas/datos.csv")
    assert code == 1
    out, err = _output(capsys)
    assert out.strip() == "", "sin asociacion no hay recibo de exito"
    assert "asociacion" in err.lower()
    assert "traceback" not in err.lower()
    assert SECRETO not in out + err
    assert str(root.resolve()) not in out + err
    # rollback: el nodo intacto byte a byte, sin .tmp y sin copia en DEST
    assert node_path.read_text(encoding="utf-8") == before
    assert not list(root.rglob("*.tmp")), "ningun .tmp residual tras el fallo"
    assert not (root / "salidas" / "datos.csv").exists(), "copia retirada"
    # el blob es content-addressed y queda verificado (no es corrupcion)
    blob = blob_path(root, _sha(CONTENT_B))
    assert blob.read_bytes() == CONTENT_B
    # y el nodo sigue listaando el adjunto como not-stored
    code = _run_list(root, "inbox/m1.md")
    assert code == 0
    out, err = _output(capsys)
    rows = [json.loads(line) for line in out.strip().splitlines()]
    assert [row["status"] for row in rows] == ["not-stored", "not-stored"]


def test_asociacion_preserva_frontmatter_ajeno_y_cuerpo_con_separadores(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(
        tmp_path,
        monkeypatch,
        node_lines=_node_lines(
            [(CONTENT_A, "informe anual.pdf", "application/pdf")],
            extra_fields=["mailbox: INBOX/Sub", "raw_sha256: " + "ff" * 32],
        ),
    )
    node_path = root / "inbox" / "m1.md"
    before = node_path.read_text(encoding="utf-8")
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 0
    _output(capsys)
    after = node_path.read_text(encoding="utf-8")
    for fragment in (
        "raw_sha256: " + "ff" * 32,
        "mailbox: INBOX/Sub",
        "imap_uid: 7",
        "Cuerpo del mensaje.",
        "  - sha256: " + _sha(CONTENT_A),
    ):
        assert fragment in after, "se conserva: " + fragment
    assert "stored: true" in after
    assert before != after
    # el nodo reescrito sigue siendo legible por la misma primitiva de lectura
    code = _run_list(root, "inbox/m1.md")
    assert code == 0
    out, _ = _output(capsys)
    assert json.loads(out.strip())["status"] == "stored"