# frozen_cli_attachments_download.py — Oracle del comando
# `attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION` sobre
# src/email/cli.py con un IMAP FALSO (fabrica inyectada por monkeypatch sobre
# imap_reader.imaplib.IMAP4_SSL) y un store temporal en tmp_path.
# Sin red, sin credenciales reales, sin sockets: la fabrica falsa registra
# login/select/fetch en memoria y devuelve un RFC822 embebido.
#
# Verifica:
# - la frase literal CONFIRMAR EXTRACCION se valida ANTES de conectar o
#   escribir: frase ausente/incorrecta => sin conexion, sin blob, sin DEST.
# - exito: descarga SOLO el indice MIME pedido (re-fetch por UID readonly),
#   blob content-addressed dentro de ROOT y copia verificada en DEST.
# - nodo legacy (sin account_id o sin imap_uid) rechazado sin conectar.
# - DEST con traversal/absoluta => codigo 2 sin conectar.
# - tipo bloqueado y limite de tamano => rechazo solo con metadatos.
# - hash mismatch: blob preexistente corrupto NO se sobreescribe; sha
#   declarado distinto del contenido => nada escrito.
# - segunda descarga del mismo adjunto es idempotente (blob intacto,
#   `idempotent: true`, un solo `.meta`).
# - error IMAP: mensaje sin la password, sin rutas absolutas, sin traceback.
# - codigos: 0 exito (una linea JSON), 1 fallo de operacion, 2 error de
#   argumentos. Ningun error imprime secretos ni rutas absolutas de ROOT.

import hashlib
import json

import pytest

from email.message import EmailMessage

from src.email import cli as cli_mod
from src.email import imap_reader
from src.email.account import create_email_account
from src.email.account_store import save_email_account
from src.email.attachments import blob_path, meta_path
from src.email.mail_server_store import store_mail_server_config

PHRASE = "CONFIRMAR EXTRACCION"
SECRETO = "SECRETO-EXTRACCION-FKE-NO-REAL"

CONTENT_A = b"contenido del primer adjunto\n" * 3
CONTENT_B = b"segundo adjunto, distinto del primero\n"
CONTENT_C = b"tercero que nadie debe descargar en este test\n"


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
        if self._fake.error == "login":
            raise OSError("login rejected para " + SECRETO)

    def select(self, mailbox, readonly=False):
        self._fake.calls.append(("select", mailbox, readonly))
        if self._fake.error == "select":
            raise OSError("select rechazado con " + SECRETO)
        return ("OK", [b"1 EXISTS"])

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "UIDVALIDITY", [b"123"]

    def uid(self, command, message_set, spec):
        assert command == "FETCH"
        assert spec == "(BODY.PEEK[])"
        return self.fetch(message_set, spec)

    def fetch(self, message_set, spec):
        self._fake.calls.append(("fetch", message_set, spec))
        if self._fake.error == "fetch":
            raise OSError("fetch fallo con " + SECRETO)
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
        self.error = None

    def __call__(self, host, port, *, ssl_context, timeout):
        assert ssl_context.check_hostname
        assert timeout == 30
        self.calls.append(("connect", host, port))
        connection = _FakeConnection(self, host, port)
        return connection


def _write_node(root, rel_path, lines):
    if not any(line.startswith("uidvalidity:") for line in lines):
        lines = ["uidvalidity: 123", *lines]
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + "\n".join(lines) + "\n---\n\nCuerpo del mensaje.\n",
        encoding="utf-8",
    )


def _attachment_lines(content, filename, content_type, part_index, stored="false"):
    return [
        "  - sha256: " + _sha(content),
        "    filename: " + filename,
        "    content_type: " + content_type,
        "    size: " + str(len(content)),
        "    part_index: " + str(part_index),
        "    stored: " + stored,
    ]


def _setup(tmp_path, monkeypatch, attachments=None, node_fields=None, rel_path="inbox/m1.md"):
    """Store temporal: cuenta guardada + servidores + nodo con adjuntos."""
    root = tmp_path / "store"
    root.mkdir(exist_ok=True)
    account = create_email_account("personal", "gmail", "yo@example.test", "env://TEST_EXTRACT_PW")
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
    monkeypatch.setenv("TEST_EXTRACT_PW", SECRETO)
    if attachments is None:
        attachments = [
            (CONTENT_A, "informe anual.pdf", "application/pdf"),
            (CONTENT_B, "datos.csv", "text/csv"),
        ]
    lines = [
        "type: Email Message",
        "account_id: personal",
        "imap_uid: 7",
        "uidvalidity: 123",
        "subject: con adjuntos",
    ]
    if node_fields:
        lines.extend(node_fields)
    lines.append("attachments:")
    for index, (content, filename, content_type) in enumerate(attachments):
        lines.extend(_attachment_lines(content, filename, content_type, index))
    _write_node(root, rel_path, lines)
    fake = _FakeIMAPFactory()
    fake.raw = _message_bytes(
        [(content, filename, ctype) for content, filename, ctype in attachments]
    )
    monkeypatch.setattr(imap_reader.imaplib, "IMAP4_SSL", fake)
    return root, fake


def _output(capsys):
    captured = capsys.readouterr()
    return captured.out, captured.err


def _run_download(root, rel_path, index, dest, phrase=PHRASE):
    argv = ["attachment", "download", str(root), rel_path, str(index), dest]
    if phrase is not None:
        argv.extend(phrase.split())
    return cli_mod.cli_main(argv)


def _argv_download(root, rel_path, index, dest, *tail):
    return ["attachment", "download", str(root), rel_path, str(index), dest, *tail]


def test_frase_incorrecta_no_conecta_ni_escribe(tmp_path, monkeypatch, capsys):
    root, fake = _setup(tmp_path, monkeypatch)
    dest = tmp_path / "fuga" / "informe.pdf"
    for frase in (
        "CONFIRMAR",
        "confirmar extraccion",
        "CONFIRMAR EXTRACCION EXTRA",
        "CONFIRMAR  EXTRACCION",
        "borrar",
    ):
        code = cli_mod.cli_main(
            _argv_download(root, "inbox/m1.md", 0, "salidas/informe.pdf", frase)
        )
        assert code == 1, "frase incorrecta debe dar 1: " + frase
        out, err = _output(capsys)
        assert "confirmacion" in err.lower()
        assert "traceback" not in err.lower()
        assert fake.calls == [], "sin frase exacta NO debe conectarse: " + frase
    # frase entera en un solo argumento tambien se rechaza si no es literal
    code = cli_mod.cli_main(
        _argv_download(root, "inbox/m1.md", 0, "salidas/informe.pdf", "CONFIRMAR  EXTRACCION")
    )
    assert code == 1
    assert fake.calls == []
    assert not (root / "attachments").exists(), "sin autorizacion no se crean blobs"
    assert not dest.exists(), "sin autorizacion no se escribe el DEST"
    # sin la frase (aridad corta): error de argumentos
    code = cli_mod.cli_main(_argv_download(root, "inbox/m1.md", 0, "salidas/informe.pdf"))
    assert code == 2
    assert fake.calls == []


def test_exito_descarga_solo_el_indice_pedido_y_escribe_bajo_root(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch)
    code = _run_download(root, "inbox/m1.md", 1, "salidas/datos.csv")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    receipt = json.loads(out.strip())
    # solo el adjunto 1: ni el contenido ni el hash del adjunto 0
    assert receipt["sha256"] == _sha(CONTENT_B)
    assert receipt["size"] == len(CONTENT_B)
    assert receipt["display"] == "datos.csv"
    assert receipt["idempotent"] is False
    assert receipt["blob"] == "attachments/" + _sha(CONTENT_B)[:2] + "/" + _sha(CONTENT_B)[2:4] + "/" + _sha(CONTENT_B)
    assert receipt["dest"] == "salidas/datos.csv"
    dest = root / "salidas" / "datos.csv"
    assert dest.read_bytes() == CONTENT_B
    assert CONTENT_A not in dest.read_bytes()
    blob = blob_path(root, _sha(CONTENT_B))
    assert blob.is_file() and blob.resolve().is_relative_to(root.resolve())
    assert blob.read_bytes() == CONTENT_B
    assert not blob_path(root, _sha(CONTENT_A)).exists(), "solo el indice pedido"
    assert not blob_path(root, _sha(CONTENT_C)).exists()
    # recorrida real del IMAP falso: readonly, UID como texto, credencial en memoria
    assert ("connect", "imap.saved.test", 1143) in fake.calls
    assert ("login", "yo@example.test", SECRETO) in fake.calls
    assert ("select", "INBOX", True) in fake.calls
    assert ("fetch", "7", "(BODY.PEEK[])") in fake.calls
    assert SECRETO not in out + err
    assert str(root.resolve()) not in out + err


def test_select_mailbox_desde_el_nodo(tmp_path, monkeypatch, capsys):
    root, fake = _setup(tmp_path, monkeypatch, node_fields=["mailbox: INBOX/Sub"])
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 0
    _output(capsys)
    assert ("select", "INBOX/Sub", True) in fake.calls, "el mailbox viene del nodo"
    assert ("fetch", "7", "(BODY.PEEK[])") in fake.calls


def test_nodo_legacy_sin_imap_uid_o_sin_account_id_rechazado(tmp_path, monkeypatch, capsys):
    # sin imap_uid y sin account_id: nodo heredado, no descargable
    root, fake = _setup(tmp_path, monkeypatch)
    legacy = (root / "inbox" / "legacy.md")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        "---\nsubject: viejo\nattachments:\n  - " + _sha(CONTENT_A) + "\n---\n\nCuerpo.\n",
        encoding="utf-8",
    )
    code = _run_download(root, "inbox/legacy.md", 0, "salidas/x.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert "legacy" in err.lower()
    assert fake.calls == []
    assert not (root / "attachments").exists()
    # con account_id pero sin imap_uid tambien se rechaza
    _write_node(root, "inbox/sin_uid.md", [
        "account_id: personal",
        "subject: sin uid",
        "attachments:",
        *  _attachment_lines(CONTENT_A, "informe anual.pdf", "application/pdf", 0),
    ])
    fake.calls.clear()
    code = _run_download(root, "inbox/sin_uid.md", 0, "salidas/x.pdf")
    assert code == 1
    _output(capsys)
    assert fake.calls == []


def test_dest_con_traversal_o_absoluta_devuelve_2_sin_conectar(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch)
    bad_dests = [
        "../fuga.pdf",
        "salidas/../../fuga.pdf",
        "C:/Windows/fuga.pdf",
        "/tmp/fuga.pdf",
        "~/fuga.pdf",
    ]
    for dest in bad_dests:
        code = _run_download(root, "inbox/m1.md", 0, dest)
        assert code == 2, "DEST " + repr(dest) + " debe dar 2"
        out, err = _output(capsys)
        assert "dest" in err.lower() or "insegura" in err.lower()
        assert fake.calls == [], "DEST insegura no debe conectar: " + repr(dest)
    assert not (root / "attachments").exists()
    assert not (root / "fuga.pdf").exists()
    assert not (root.parent / "fuga.pdf").exists()


def test_tipo_bloqueado_y_tamano_limite_rechazados_sin_conectar(
    tmp_path, monkeypatch, capsys
):
    # tipo prohibido por defecto (mime)
    root, fake = _setup(tmp_path, monkeypatch, attachments=[
        (CONTENT_A, "programa.exe", "application/x-msdownload"),
    ])
    code = _run_download(root, "inbox/m1.md", 0, "salidas/programa.exe")
    assert code == 1
    out, err = _output(capsys)
    assert "tipo" in err.lower()
    assert fake.calls == []
    assert not (root / "attachments").exists()
    # tipo prohibido por extension aunque el mime sea inocente
    root, fake = _setup(tmp_path, monkeypatch, attachments=[
        (CONTENT_B, "script.js", "text/plain"),
    ])
    code = _run_download(root, "inbox/m1.md", 0, "salidas/script.js")
    assert code == 1
    _output(capsys)
    assert fake.calls == []
    # limite de tamano declarado en el frontmatter
    root, fake = _setup(tmp_path, monkeypatch, attachments=[
        (CONTENT_A, "informe anual.pdf", "application/pdf"),
    ])
    _write_node(root, "inbox/grande.md", [
        "account_id: personal",
        "imap_uid: 7",
        "subject: grande",
        "attachments:",
        "  - sha256: " + _sha(CONTENT_A),
        "    filename: informe anual.pdf",
        "    content_type: application/pdf",
        "    size: " + str(26 * 1024 * 1024),
        "    part_index: 0",
        "    stored: false",
    ])
    fake.raw = _message_bytes([(CONTENT_A, "informe anual.pdf", "application/pdf")])
    code = _run_download(root, "inbox/grande.md", 0, "salidas/grande.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert "limite" in err.lower() or "tamano" in err.lower()
    assert fake.calls == [], "el limite se valida ANTES de conectar"
    assert not (root / "attachments").exists()


def test_hash_mismatch_no_sobreescribe_blob_ni_dest(tmp_path, monkeypatch, capsys):
    # blob preexistente corrupto (mismo hash declarado, otro contenido)
    root, fake = _setup(tmp_path, monkeypatch)
    corrupt = blob_path(root, _sha(CONTENT_A))
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    corrupt.write_bytes(b"blob corrupto preexistente")
    before = corrupt.read_bytes()
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert "hash-mismatch" in err
    assert corrupt.read_bytes() == before, "el blob corrupto no debe sobreescribirse"
    assert not (root / "salidas" / "informe.pdf").exists()
    assert not corrupt.with_name(corrupt.name + ".tmp").exists()
    assert SECRETO not in out + err
    assert str(root.resolve()) not in out + err
    # sha declarado distinto del contenido real descargado
    fake.calls.clear()
    _write_node(root, "inbox/mal_hash.md", [
        "account_id: personal",
        "imap_uid: 7",
        "subject: hash falso",
        "attachments:",
        "  - sha256: " + "ab" * 32,
        "    filename: informe anual.pdf",
        "    content_type: application/pdf",
        "    size: " + str(len(CONTENT_A)),
        "    part_index: 0",
        "    stored: false",
    ])
    code = _run_download(root, "inbox/mal_hash.md", 0, "salidas/otro.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert "hash-mismatch" in err
    assert not blob_path(root, "ab" * 32).exists(), "con hash falso no se escribe nada"
    assert not (root / "salidas" / "otro.pdf").exists()
    # el blob corrupto original sigue intacto
    assert corrupt.read_bytes() == before


def test_segunda_descarga_es_idempotente(tmp_path, monkeypatch, capsys):
    root, fake = _setup(tmp_path, monkeypatch)
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 0
    first = json.loads(_output(capsys)[0].strip())
    assert first["idempotent"] is False
    blob = blob_path(root, _sha(CONTENT_A))
    blob_bytes = blob.read_bytes()
    meta = meta_path(root, _sha(CONTENT_A))
    assert meta.is_file()
    meta_count = len(list((root / "attachments").glob(_sha(CONTENT_A) + "*")))
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    second = json.loads(out.strip())
    assert second["idempotent"] is True, "la segunda extraccion es un no-op"
    assert second["sha256"] == first["sha256"]
    assert blob.read_bytes() == blob_bytes
    assert meta.is_file() and meta.read_text(encoding="utf-8").count("sha256") == 1
    assert len(list((root / "attachments").glob(_sha(CONTENT_A) + "*"))) == meta_count
    # y la copia en DEST sigue siendo el mismo contenido verificado
    assert (root / "salidas" / "informe.pdf").read_bytes() == CONTENT_A


def test_error_imap_sin_password_ni_rutas_absolutas(tmp_path, monkeypatch, capsys):
    root, fake = _setup(tmp_path, monkeypatch)
    fake.error = "fetch"
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert out.strip() == ""
    assert "traceback" not in err.lower()
    assert SECRETO not in out + err, "la password jamas debe aparecer"
    assert str(root.resolve()) not in out + err
    assert "imap.saved.test" not in err, "los errores no exponen el host del servidor"
    assert not (root / "attachments").exists(), "sin conexion util no se escribe blob"
    assert not (root / "salidas" / "informe.pdf").exists()
    assert ("login", "yo@example.test", SECRETO) in fake.calls
    # y tambien con fallo de login
    fake.error = "login"
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert SECRETO not in out + err
    assert "traceback" not in err.lower()


def test_cuenta_o_credencial_ausente_devuelve_1_sin_conectar(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch)
    _write_node(root, "inbox/otra.md", [
        "account_id: fantasma",
        "imap_uid: 7",
        "subject: otra cuenta",
        "attachments:",
        *_attachment_lines(CONTENT_A, "informe anual.pdf", "application/pdf", 0),
    ])
    code = _run_download(root, "inbox/otra.md", 0, "salidas/informe.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert "cuenta no encontrada" in err.lower()
    assert fake.calls == []
    # credencial irresoluble: la env var no existe
    monkeypatch.delenv("TEST_EXTRACT_PW")
    fake.calls.clear()
    code = _run_download(root, "inbox/m1.md", 0, "salidas/informe.pdf")
    assert code == 1
    out, err = _output(capsys)
    assert fake.calls == []
    assert "credencial" in err.lower()
    assert "credential_ref" not in (out + err).lower()
    assert SECRETO not in out + err


def test_aridad_e_index_invalidos(tmp_path, monkeypatch, capsys):
    root, fake = _setup(tmp_path, monkeypatch)
    bad_cases = [
        _argv_download(root, "inbox/m1.md", "x", "salidas/a.pdf", PHRASE),
        _argv_download(root, "inbox/m1.md", "-1", "salidas/a.pdf", PHRASE),
        _argv_download(root, "inbox/m1.md", "1.5", "salidas/a.pdf", PHRASE),
        _argv_download(root, "inbox/m1.md", "99", "salidas/a.pdf", PHRASE),
        _argv_download(root, "inbox/falta.md", 0, "salidas/a.pdf", PHRASE),
    ]
    for argv in bad_cases:
        code = cli_mod.cli_main(argv)
        assert code in (1, 2), "argv " + repr(argv) + " debe dar 1 o 2"
        out, err = _output(capsys)
        assert out.strip() == ""
        assert "traceback" not in err.lower()
        assert fake.calls == [], "con INDEX invalido no debe conectar: " + repr(argv)
    assert not (root / "attachments").exists()
