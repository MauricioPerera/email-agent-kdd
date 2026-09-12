"""Prueba offline del vinculo sync -> attachment download.

Un record de `fetch_imap_messages` (con `imap_uid`) sincronizado por la CLI
debe terminar en un nodo cuyo frontmatter lleva `account_id`, `imap_uid` y
`mailbox`, de modo que `read_download_target` recupere la identidad de
re-descarga. Sin red: la fabrica falsa de imaplib registra las llamadas en
memoria. Compatibilidad: un record legacy sin esas claves persiste igual que
antes y su nodo sigue sin ser descargable (diseno).
"""

import hashlib
from email.message import EmailMessage
from pathlib import Path

from src.email import cli as cli_mod
from src.email import imap_reader
from src.email.account import create_email_account
from src.email.account_store import save_email_account
from src.email.attachments import read_attachment_entries, read_download_target
from src.email.persist_at import persist_email_okf_at

SECRETO = "SECRETO-SYNC-LINK-FKE-NO-REAL"
CONTENT = b"contenido del adjunto sincronizado\n"

LEGACY_RECORD = {
    "account_id": "personal",
    "subject": "viejo",
    "from": "Ana <ana@example.com>",
    "to": "user@example.com",
    "date": "",
    "body": "cuerpo.\n",
    "attachments": [],
    "raw_sha256": "33399744d24298f2a37e46f7a04758ee47549ecf83f36310278583703d483337",
}


class _FakeConnection:
    def __init__(self, fake, host, port):
        self._fake = fake
        self._host = host
        self._port = port

    def login(self, username, password):
        self._fake.calls.append(("login", username, password))

    def select(self, mailbox, readonly=False):
        self._fake.calls.append(("select", mailbox, readonly))
        return ("OK", [b"1 EXISTS"])

    def response(self, name):
        assert name == "UIDVALIDITY"
        return "UIDVALIDITY", [b"123"]

    def uid(self, command, *args):
        if command == "SEARCH":
            return self.search(*args)
        assert command == "FETCH" and args[1] == "(BODY.PEEK[])"
        return self.fetch(*args)

    def search(self, charset, criterion):
        self._fake.calls.append(("search", criterion))
        return ("OK", [b"1"])

    def fetch(self, message_set, spec):
        self._fake.calls.append(("fetch", message_set, spec))
        return ("OK", [(b"1 (RFC822 {%d}" % len(self._fake.raw), self._fake.raw), b")"])

    def close(self):
        pass

    def logout(self):
        pass


class _FakeIMAPFactory:
    def __init__(self):
        self.calls = []
        self.raw = b""

    def __call__(self, host, port, *, ssl_context, timeout):
        assert ssl_context.check_hostname
        assert timeout == 30
        self.calls.append(("connect", host, port))
        return _FakeConnection(self, host, port)


def _raw_message():
    message = EmailMessage()
    message["From"] = "remite@example.test"
    message["To"] = "yo@example.test"
    message["Subject"] = "sincronizado"
    message.set_content("cuerpo sin adjuntos")
    message.add_attachment(
        CONTENT, maintype="application", subtype="pdf", filename="informe.pdf"
    )
    return message.as_bytes()


def _setup(tmp_path, monkeypatch):
    root = tmp_path / "store"
    root.mkdir(exist_ok=True)
    account = create_email_account(
        "personal", "gmail", "yo@example.test", "env://TEST_SYNC_LINK_PW"
    )
    save_email_account(str(root), account)
    monkeypatch.setenv("TEST_SYNC_LINK_PW", SECRETO)
    fake = _FakeIMAPFactory()
    fake.raw = _raw_message()
    monkeypatch.setattr(imap_reader.imaplib, "IMAP4_SSL", fake)
    return root, fake


def test_sync_record_con_imap_uid_termina_en_nodo_descargable(tmp_path, monkeypatch):
    root, fake = _setup(tmp_path, monkeypatch)
    code = cli_mod.cli_main(["sync", str(root), "personal"])
    assert code == 0
    node = (
        root / "store" / "emails" / (hashlib.sha256(fake.raw).hexdigest() + ".md")
    )
    assert node.is_file(), "el sync debe persistir el nodo del mensaje"
    text = node.read_text(encoding="utf-8")
    # el frontmatter trae la identidad completa de re-descarga
    assert "account_id: personal" in text
    assert "imap_uid: 1" in text
    assert "mailbox: INBOX" in text
    # read_download_target recupera la identidad: nodo descargable
    account_id, imap_uid, mailbox = read_download_target(text)
    assert account_id == "personal"
    assert imap_uid == 1
    assert mailbox == "INBOX"
    # y el adjunto queda declarado en el frontmatter (listable sin blobs)
    entries = read_attachment_entries(text)
    assert len(entries) == 1
    assert entries[0]["sha256"] == hashlib.sha256(CONTENT).hexdigest()
    # sesion real de sync: select del mailbox efectivo, readonly
    assert ("select", "INBOX", True) in fake.calls
    assert ("fetch", "1", "(BODY.PEEK[])") in fake.calls
    assert SECRETO not in text


def test_record_legacy_sin_identidad_persiste_igual_y_no_es_descargable(
    tmp_path, monkeypatch
):
    root, _fake = _setup(tmp_path, monkeypatch)
    path = persist_email_okf_at(LEGACY_RECORD, str(root), "store/emails/legacy.md")
    text = Path(path).read_text(encoding="utf-8")
    assert "imap_uid" not in text, "sin imap_uid el nodo se renderiza igual que antes"
    assert "mailbox" not in text, "sin mailbox el nodo se renderiza igual que antes"
    account_id, imap_uid, mailbox = read_download_target(text)
    assert imap_uid is None, "nodo legacy no descargable por diseno"
