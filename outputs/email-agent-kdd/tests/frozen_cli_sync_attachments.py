# frozen_cli_sync_attachments.py — Oracle de `sync ROOT ACCOUNT_ID
# [--limit N] [--unread] --attachments CONFIRMAR EXTRACCION` (Sprint 4).
#
# Sin red, sin IMAP real, sin credenciales reales: fabrica falsa de
# imaplib.IMAP4_SSL inyectada por monkeypatch que registra login/select/fetch
# en memoria y devuelve RFC822 embebidos.
#
# Verifica:
# - sync por defecto (sin --attachments): jamas persiste bytes, summary con
#   las 5 claves exactas del contrato, frontmatter sin stored, sin blobs.
# - la frase literal CONFIRMAR EXTRACCION se valida ANTES de conectar:
#   frase ausente/incorrecta => sin conexion, sin blobs, sin cursor.
# - exito autorizado: reutiliza el RFC822 ya descargado (UN solo fetch por
#   mensaje), blob content-addressed dentro de ROOT, frontmatter nuevo con
#   stored: true, summary con contadores de adjuntos.
# - presupuesto total (SYNC_ATTACHMENT_BUDGET_MB), tipos bloqueados y limite
#   por adjunto => stored: false con motivo, sin bytes en disco, sin truncar.
# - idempotencia: re-sync con cursor reiniciado re-extrai el mismo adjunto
#   como no-op (blob y .meta intactos, nodo identico).
# - rollback: hash-mismatch (blob corrupto preexistente) degrada a skipped,
#   no deja .tmp, no rompe el cursor ni aborta la sync.
# - env var invalida => error de argumentos antes de conectar.
# - compatibilidad: sin --attachments, nada cambia para sync/watch.

import hashlib
import json

from email.message import EmailMessage

from src.email import attachments as attachments_mod
from src.email import cli as cli_mod
from src.email import imap_reader
from src.email.account import create_email_account
from src.email.account_store import save_email_account
from src.email.attachments import blob_path, meta_path
from src.email.cursor_store import load_sync_cursor, save_sync_cursor

PHRASE = "CONFIRMAR EXTRACCION"
SECRETO = "SECRETO-SYNC-ATT-FKE-NO-REAL"

CONTENT_PDF = b"informe sincronizado con adjuntos\n" * 40
CONTENT_CSV = b"datos,sincronizados,en,csv\n" * 40
CONTENT_BIG = b"X" * (600 * 1024)
CONTENT_EXE = b"binario de tipo bloqueado por defecto\n"

SUMMARY_KEYS = {
    "account_id",
    "fetched",
    "persisted",
    "persisted_paths",
    "contacts_updated",
}


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _message_bytes(attachments):
    """RFC822 con adjuntos: lista de (contenido, filename, content_type)."""
    message = EmailMessage()
    message["From"] = "remite@example.test"
    message["To"] = "yo@example.test"
    message["Subject"] = "sincronizado con adjuntos"
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

    def search(self, charset, criterion):
        self._fake.calls.append(("search", criterion))
        ids = " ".join(str(uid) for uid in sorted(self._fake.raws))
        return ("OK", [ids.encode("ascii")])

    def fetch(self, message_set, spec):
        self._fake.calls.append(("fetch", message_set, spec))
        raw = self._fake.raws[int(message_set)]
        return ("OK", [(b"%s (RFC822 {%d}" % (message_set.encode(), len(raw)), raw), b")"])

    def close(self):
        pass

    def logout(self):
        pass


class _FakeIMAPFactory:
    def __init__(self):
        self.calls = []
        self.raws = {}

    def __call__(self, host, port):
        self.calls.append(("connect", host, port))
        return _FakeConnection(self, host, port)


def _setup(tmp_path, monkeypatch, raws=None):
    root = tmp_path / "store"
    root.mkdir(exist_ok=True)
    account = create_email_account(
        "personal", "gmail", "yo@example.test", "env://TEST_SYNC_ATTACH_PW"
    )
    save_email_account(str(root), account)
    monkeypatch.setenv("TEST_SYNC_ATTACH_PW", SECRETO)
    fake = _FakeIMAPFactory()
    fake.raws = raws or {}
    monkeypatch.setattr(imap_reader.imaplib, "IMAP4_SSL", fake)
    return root, fake


def _run_sync(root, *extra):
    return cli_mod.cli_main(["sync", str(root), "personal", *extra])


def _output(capsys):
    captured = capsys.readouterr()
    return captured.out, captured.err


def _node_path(root, raw):
    return root / "store" / "emails" / (_sha(raw) + ".md")


# ---------------------------------------------------------------------------
# Sync por defecto: sin blobs, summary exacto, frontmatter sin stored.
# ---------------------------------------------------------------------------


def test_sync_por_defecto_no_persiste_bytes(tmp_path, monkeypatch, capsys):
    raw = _message_bytes([(CONTENT_PDF, "informe.pdf", "application/pdf")])
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    code = _run_sync(root, "--limit", "10")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    summary = json.loads(out.strip())
    assert set(summary) == SUMMARY_KEYS, "el summary por defecto no cambia"
    assert summary["fetched"] == 1 and summary["persisted"] == 1
    node = _node_path(root, raw)
    assert node.is_file()
    text = node.read_text(encoding="utf-8")
    assert "stored:" not in text, "sin --attachments el frontmatter no cambia"
    assert _sha(CONTENT_PDF) in text, "el hash (metadato) si llega"
    assert not (root / "attachments").exists(), "sync por defecto no escribe blobs"
    assert "raw_message" not in text
    assert load_sync_cursor(str(root), "personal") == 1
    assert ("fetch", "1", "(RFC822)") in fake.calls


# ---------------------------------------------------------------------------
# Confirmacion: se valida ANTES de conectar.
# ---------------------------------------------------------------------------


def test_frase_incorrecta_aborta_antes_de_conectar(tmp_path, monkeypatch, capsys):
    raw = _message_bytes([(CONTENT_PDF, "informe.pdf", "application/pdf")])
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    for extra in (
        ("--attachments", "CONFIRMAR"),
        ("--attachments", "confirmar extraccion"),
        ("--attachments", "CONFIRMAR EXTRACCION EXTRA"),
        ("--attachments",),
        ("--attachments", "EXTRACCION", "CONFIRMAR"),
    ):
        code = _run_sync(root, *extra)
        assert code == 1, "argv " + repr(extra) + " debe dar 1"
        out, err = _output(capsys)
        assert "confirmacion" in err.lower()
        assert "traceback" not in err.lower()
        assert fake.calls == [], "sin frase exacta NO debe conectarse"
        assert not (root / "attachments").exists()
        assert not _node_path(root, raw).exists()
        assert load_sync_cursor(str(root), "personal") == 0


def test_env_var_de_presupuesto_invalida_aborta_antes_de_conectar(
    tmp_path, monkeypatch, capsys
):
    raw = _message_bytes([(CONTENT_PDF, "informe.pdf", "application/pdf")])
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    for value in ("0", "-5", "abc", "1.5"):
        monkeypatch.setenv("SYNC_ATTACHMENT_BUDGET_MB", value)
        code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
        assert code == 2, "presupuesto " + value + " debe dar 2"
        out, err = _output(capsys)
        assert "SYNC_ATTACHMENT_BUDGET_MB" in err
        assert fake.calls == []
        assert not (root / "attachments").exists()


# ---------------------------------------------------------------------------
# Exito autorizado: un solo fetch, blob verificado, stored: true.
# ---------------------------------------------------------------------------


def test_sync_attachments_exitoso_reutiliza_el_rfc822(tmp_path, monkeypatch, capsys):
    raw = _message_bytes(
        [(CONTENT_PDF, "informe anual.pdf", "application/pdf"), (CONTENT_CSV, "datos.csv", "text/csv")]
    )
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    summary = json.loads(out.strip())
    assert summary["attachments_stored"] == 2
    assert summary["attachments_skipped"] == 0
    assert summary["attachments_errors"] == 0
    assert summary["fetched"] == 1
    assert set(summary) == SUMMARY_KEYS | {
        "attachments_stored",
        "attachments_skipped",
        "attachments_errors",
    }
    # un solo fetch por mensaje: el RFC822 se reutiliza, no hay re-fetch
    assert fake.calls.count(("fetch", "1", "(RFC822)")) == 1
    assert ("select", "INBOX", True) in fake.calls
    assert SECRETO not in out + err
    # blobs content-addressed bajo ROOT, bytes exactos
    for content in (CONTENT_PDF, CONTENT_CSV):
        blob = blob_path(str(root), _sha(content))
        assert blob.is_file()
        assert blob.read_bytes() == content
        assert blob.resolve().is_relative_to(root.resolve())
    # frontmatter nuevo: mapa completo con stored: true
    text = _node_path(root, raw).read_text(encoding="utf-8")
    assert "part_index: 0" in text and "part_index: 1" in text
    assert text.count("stored: true") == 2
    assert "stored: false" not in text
    assert "raw_message" not in text
    assert SECRETO not in text
    assert load_sync_cursor(str(root), "personal") == 1
    # el .meta queda escrito junto al blob
    assert meta_path(str(root), _sha(CONTENT_PDF)).is_file()


def test_sync_attachments_con_unread_y_limit(tmp_path, monkeypatch, capsys):
    raw1 = _message_bytes([(CONTENT_PDF, "informe.pdf", "application/pdf")])
    raw2 = _message_bytes([(CONTENT_CSV, "datos.csv", "text/csv")])
    root, fake = _setup(tmp_path, monkeypatch, {1: raw1, 2: raw2})
    code = _run_sync(root, "--limit", "1", "--unread", "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    out, _err = _output(capsys)
    summary = json.loads(out.strip())
    assert summary["fetched"] == 1
    assert summary["attachments_stored"] == 1
    assert ("search", "UNSEEN") in fake.calls
    assert blob_path(str(root), _sha(CONTENT_PDF)).is_file() or blob_path(
        str(root), _sha(CONTENT_CSV)
    ).is_file()
    # solo uno de los dos mensajes se sincronizo (limit 1 sobre ids 1,2)
    stored = blob_path(str(root), _sha(CONTENT_PDF)).is_file()
    other = blob_path(str(root), _sha(CONTENT_CSV)).is_file()
    assert stored != other, "limit 1 debe traer un solo mensaje"


# ---------------------------------------------------------------------------
# Presupuesto, tipos bloqueados y limite por adjunto: solo metadatos.
# ---------------------------------------------------------------------------


def test_presupuesto_agotado_deja_metadatos_sin_bytes(
    tmp_path, monkeypatch, capsys
):
    raw = _message_bytes(
        [
            (CONTENT_BIG, "primero.bin", "application/octet-stream"),
            (CONTENT_BIG, "segundo.bin", "application/octet-stream"),
        ]
    )
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    monkeypatch.setenv("SYNC_ATTACHMENT_BUDGET_MB", "1")
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    summary = json.loads(out.strip())
    assert summary["attachments_stored"] == 1
    assert summary["attachments_skipped"] == 1
    text = _node_path(root, raw).read_text(encoding="utf-8")
    assert "stored: true" in text and "stored: false" in text
    assert "skipped: budget-exhausted" in text
    assert len(list((root / "attachments").rglob("*"))) <= 4, (
        "solo blob + .meta del primero (mismo contenido: un unico blob)"
    )


def test_tipos_bloqueados_y_limite_por_adjunto_quedan_como_metadatos(
    tmp_path, monkeypatch, capsys
):
    raw = _message_bytes(
        [(CONTENT_EXE, "programa.exe", "application/x-msdownload")]
    )
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    out, err = _output(capsys)
    summary = json.loads(out.strip())
    assert summary["attachments_stored"] == 0
    assert summary["attachments_skipped"] == 1
    text = _node_path(root, raw).read_text(encoding="utf-8")
    assert "stored: false" in text
    assert "skipped: type-not-allowed" in text
    assert not (root / "attachments").exists(), "tipo bloqueado: nunca bytes"
    # limite por adjunto (MAX_ATTACHMENT_BYTES): sin truncar, solo metadatos
    monkeypatch.setattr(attachments_mod, "MAX_ATTACHMENT_BYTES", 8)
    fake.calls.clear()
    save_sync_cursor(str(root), "personal", 0)
    for stale in (root / "store" / "emails").iterdir():
        stale.unlink()
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    summary = json.loads(_output(capsys)[0].strip())
    assert summary["attachments_stored"] == 0
    assert summary["attachments_skipped"] == 1
    text = _node_path(root, raw).read_text(encoding="utf-8")
    assert "skipped: size-limit-exceeded" in text
    assert "size: " + str(len(CONTENT_EXE)) in text, "el tamano no se trunca"
    assert not (root / "attachments").exists()


# ---------------------------------------------------------------------------
# Idempotencia y rollback.
# ---------------------------------------------------------------------------


def test_re_sync_idempotente_no_duplica_blobs_ni_altera_el_nodo(
    tmp_path, monkeypatch, capsys
):
    raw = _message_bytes([(CONTENT_PDF, "informe.pdf", "application/pdf")])
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    _output(capsys)
    node = _node_path(root, raw)
    blob = blob_path(str(root), _sha(CONTENT_PDF))
    before = (node.read_bytes(), blob.read_bytes(), meta_path(str(root), _sha(CONTENT_PDF)).read_bytes())
    # reinicio del cursor: la sync re-fetch-ea el mismo mensaje
    save_sync_cursor(str(root), "personal", 0)
    fake.calls.clear()
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    out, err = _output(capsys)
    assert err == ""
    summary = json.loads(out.strip())
    assert summary["fetched"] == 1
    assert summary["attachments_stored"] == 1, "la re-extraccion es un no-op valido"
    after = (node.read_bytes(), blob.read_bytes(), meta_path(str(root), _sha(CONTENT_PDF)).read_bytes())
    assert before == after, "segunda sync: nodo, blob y .meta intactos"
    files = [path for path in (root / "attachments").rglob("*") if path.is_file()]
    assert len(files) == 2, "sin blobs ni metas duplicados"


def test_hash_mismatch_degrada_a_skipped_sin_tmp_ni_cursor_roto(
    tmp_path, monkeypatch, capsys
):
    raw = _message_bytes([(CONTENT_PDF, "informe.pdf", "application/pdf")])
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    # blob preexistente corrupto con el hash declarado: colision/corrupcion
    blob = blob_path(str(root), _sha(CONTENT_PDF))
    blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_bytes(b"blob corrupto preexistente")
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0, "un fallo por adjunto no aborta la sync"
    out, err = _output(capsys)
    summary = json.loads(out.strip())
    assert summary["attachments_stored"] == 0
    assert summary["attachments_errors"] == 1
    text = _node_path(root, raw).read_text(encoding="utf-8")
    assert "stored: false" in text
    assert "skipped: hash-mismatch" in text
    assert blob.read_bytes() == b"blob corrupto preexistente", "no se sobreescribe"
    assert list(blob.parent.glob("*.tmp")) == [], "sin blobs temporales residuales"
    assert load_sync_cursor(str(root), "personal") == 1, "el cursor no se rompe"
    assert "traceback" not in err.lower()
    assert SECRETO not in out + err


# ---------------------------------------------------------------------------
# Compatibilidad con sync existente.
# ---------------------------------------------------------------------------


def test_sync_sin_mensajes_no_crea_nada_y_cursor_se_mantiene(
    tmp_path, monkeypatch, capsys
):
    root, fake = _setup(tmp_path, monkeypatch, {})
    save_sync_cursor(str(root), "personal", 7)
    code = _run_sync(root, "--attachments", "CONFIRMAR", "EXTRACCION")
    assert code == 0
    out, _err = _output(capsys)
    summary = json.loads(out.strip())
    assert summary["fetched"] == 0
    assert summary["attachments_stored"] == 0
    assert load_sync_cursor(str(root), "personal") == 7, "sin fetched, cursor intacto"
    assert not (root / "attachments").exists()
    assert fake.calls != [], "si conecta (sesion readonly vacia)"


def test_aridad_de_sync_no_cambia_sin_la_opcion(tmp_path, monkeypatch, capsys):
    raw = _message_bytes([(CONTENT_PDF, "informe.pdf", "application/pdf")])
    root, fake = _setup(tmp_path, monkeypatch, {1: raw})
    # HOST explicito sigue aceptandose y --limit malformado sigue dando 2
    code = _run_sync(root, "imap.fake.test", "--limit", "no-es-numero")
    assert code == 2
    assert fake.calls == []
    code = _run_sync(root, "imap.fake.test")
    assert code == 0
    assert ("connect", "imap.fake.test", 993) in fake.calls
    _output(capsys)
    assert not (root / "attachments").exists()