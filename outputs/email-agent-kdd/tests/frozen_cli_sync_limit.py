"""Tests congelados de la opcion --limit del comando sync.

Oracle independiente: NO reimplementa la lectura IMAP ni el cursor; la CLI
bajo prueba (cli_main) se ejecuta con dependencias falsas inyectadas en el
modulo `src.email.cli` (store de cuentas espejo, resolver de credenciales
sobre un environ ficticio, sesion IMAP simulada con filtro `id > since_uid`
y recorte a `limit`, y store de cursor espejo en memoria). Todo offline,
sin red real, sin credenciales y sin secretos en la salida.

Congela: default sin `--limit` (el fetch aplica su DEFAULT_LIMIT), paso
explicito de `--limit N` a la config de fetch, validacion 1..100 con codigo
2 y sin tocar IMAP, soporte combinado con HOST posicional y la continuacion
por cursor UID sin duplicados entre corridas.
"""

import json

import pytest

import src.email.cli as cli

HOST_GMAIL = "imap.gmail.com"
ENV_NAME = "GMAIL_APP_PASSWORD"
SECRET = "app-password-de-prueba"
ACCOUNT = {
    "account_id": "personal",
    "provider": "gmail",
    "email": "user@example.com",
    "credential_ref": "env://" + ENV_NAME,
}


# --------------------------------------------------------------------------
# Dependencias falsas inyectadas en el modulo cli (nada de red ni disco).
# --------------------------------------------------------------------------

class _FakeWorld:
    """Estado ficticio: mailbox, cursor, llamadas y config capturada."""

    def __init__(self, mailbox=None):
        self.mailbox = list(mailbox or [])
        self.environ = {ENV_NAME: SECRET}
        self.cursors = {}
        self.fetch_calls = 0
        self.cursor_saves = []
        self.last_config = None
        self.fetched_uids = []

    def load_email_accounts(self, root):
        return [dict(ACCOUNT)]

    def load_mail_server_config(self, root, account_id):
        return None

    def resolve_credential(self, credential_ref, environ=None):
        if not isinstance(credential_ref, str) or not credential_ref.startswith(
            "env://"
        ):
            raise ValueError("error: credencial irresoluble")
        variable = credential_ref[len("env://"):]
        if variable not in self.environ:
            raise ValueError("error: credencial irresoluble")
        return self.environ[variable]

    def load_sync_cursor(self, root, account_id):
        return self.cursors.get((root, account_id), 0)

    def save_sync_cursor(self, root, account_id, uid):
        self.cursors[(root, account_id)] = uid
        self.cursor_saves.append((account_id, uid))
        return ".email-agent/cursors.json"

    def fetch_imap_messages(self, account, config):
        """Espejo de fetch-imap-messages: filtro since_uid + recorte a limit."""
        self.fetch_calls += 1
        self.last_config = dict(config)
        since_uid = config.get("since_uid", 0)
        limit = config.get("limit", 50)
        selected = sorted(
            uid for (uid, _raw) in self.mailbox if uid > since_uid
        )[:limit]
        records = []
        for uid in selected:
            self.fetched_uids.append(uid)
            records.append(
                {
                    "account_id": account["account_id"],
                    "imap_uid": uid,
                    "raw_sha256": "hash-" + str(uid),
                }
            )
        return records


@pytest.fixture()
def world(monkeypatch):
    """Inyecta las dependencias falsas en src.email.cli y devuelve el mundo."""
    fake = _FakeWorld()
    monkeypatch.setattr(cli, "load_email_accounts", fake.load_email_accounts)
    monkeypatch.setattr(cli, "load_mail_server_config", fake.load_mail_server_config)
    monkeypatch.setattr(cli, "resolve_credential", fake.resolve_credential)
    monkeypatch.setattr(cli, "load_sync_cursor", fake.load_sync_cursor)
    monkeypatch.setattr(cli, "save_sync_cursor", fake.save_sync_cursor)
    monkeypatch.setattr(cli, "fetch_imap_messages", fake.fetch_imap_messages)
    monkeypatch.setattr(
        cli,
        "sync_email_account",
        lambda account, fetch_messages, persist_message, update_contacts=None: (
            _reference_sync(account, fetch_messages, persist_message, update_contacts)
        ),
    )
    monkeypatch.setattr(
        cli,
        "persist_email_okf_at",
        lambda record, root, rel_path: rel_path,
    )
    monkeypatch.setattr(cli, "persist_conversation_index", lambda *args: None)
    monkeypatch.setattr(cli, "persist_topic_index", lambda *args: None)
    monkeypatch.setattr(cli, "extract_contacts", lambda record: [])
    monkeypatch.setattr(
        cli,
        "store_email_contacts",
        lambda root, contacts: len(contacts),
    )
    return fake


def _reference_sync(account, fetch_messages, persist_message, update_contacts):
    """Orquestador de referencia: mismo resumen de 5 claves que sync_email_account."""
    messages = fetch_messages(account)
    persisted = [persist_message(record) for record in messages]
    if update_contacts is not None:
        update_contacts(list(messages))
    return {
        "account_id": account["account_id"],
        "fetched": len(messages),
        "persisted": len(persisted),
        "persisted_paths": persisted,
        "contacts_updated": update_contacts is not None,
    }


# --------------------------------------------------------------------------
# Usage
# --------------------------------------------------------------------------

def test_help_documents_sync_limit(capsys):
    assert cli.cli_main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "sync ROOT ACCOUNT_ID [HOST] [--limit N]" in out, (
        "la ayuda debe documentar la opcion --limit de sync"
    )


# --------------------------------------------------------------------------
# Default y paso del limite a la config de fetch
# --------------------------------------------------------------------------

def test_sync_without_limit_does_not_set_limit_key(world, tmp_path, capsys):
    world.mailbox = [(index, b"raw") for index in range(1, 61)]
    root = str(tmp_path)
    code = cli.cli_main(["sync", root, "personal"])
    assert code == 0
    assert world.fetch_calls == 1
    assert "limit" not in world.last_config, (
        "sin --limit la config no debe fijar 'limit' (el fetch usa su default 50)"
    )
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["fetched"] == 50, (
        "el default efectivo debe seguir siendo 50 (DEFAULT_LIMIT del fetch)"
    )


def test_sync_passes_limit_to_fetch_config(world, tmp_path, capsys):
    world.mailbox = [(index, b"raw") for index in range(1, 61)]
    root = str(tmp_path)
    code = cli.cli_main(["sync", root, "personal", "--limit", "25"])
    assert code == 0
    assert world.last_config["limit"] == 25, (
        "--limit debe llegar a fetch_imap_messages via config['limit']"
    )
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["fetched"] == 25
    assert world.fetched_uids == list(range(1, 26))


def test_sync_limit_combines_with_positional_host(world, tmp_path, capsys):
    world.mailbox = [(index, b"raw") for index in range(1, 11)]
    root = str(tmp_path)
    code = cli.cli_main(["sync", root, "personal", "imap.custom.test", "--limit", "3"])
    assert code == 0
    assert world.last_config["host"] == "imap.custom.test"
    assert world.last_config["limit"] == 3
    assert world.fetched_uids == [1, 2, 3]
    capsys.readouterr()


def test_sync_limit_before_root_account_is_accepted(world, tmp_path, capsys):
    world.mailbox = [(index, b"raw") for index in range(1, 6)]
    root = str(tmp_path)
    code = cli.cli_main(["sync", "--limit", "2", root, "personal"])
    assert code == 0
    assert world.last_config["limit"] == 2
    assert world.fetched_uids == [1, 2]
    capsys.readouterr()


# --------------------------------------------------------------------------
# Validacion 1..100: codigo 2, sin tocar IMAP ni cursor
# --------------------------------------------------------------------------

def test_sync_invalid_limit_returns_2_without_fetch(world, tmp_path, capsys):
    for argv_tail in (
        ["--limit", "0"],
        ["--limit", "101"],
        ["--limit", "abc"],
        ["--limit", "-1"],
        ["--limit"],
    ):
        code = cli.cli_main(["sync", str(tmp_path), "personal"] + argv_tail)
        assert code == 2, "valor invalido de --limit debe dar codigo 2: " + repr(argv_tail)
        err = capsys.readouterr().err.lower()
        assert "usage:" in err, "el error debe mostrar el usage"
        assert world.fetch_calls == 0, (
            "un --limit invalido no debe abrir sesion IMAP"
        )
        assert world.cursor_saves == [], (
            "un --limit invalido no debe avanzar el cursor"
        )


def test_sync_missing_args_still_returns_2(world, tmp_path, capsys):
    assert cli.cli_main(["sync", str(tmp_path)]) == 2
    assert cli.cli_main(["sync", str(tmp_path), "personal", "h", "extra"]) == 2
    assert cli.cli_main(["sync", "--limit", "10"]) == 2
    assert world.fetch_calls == 0
    capsys.readouterr()


# --------------------------------------------------------------------------
# Continuacion por cursor UID sin duplicados
# --------------------------------------------------------------------------

def test_sync_limit_keeps_uid_cursor_and_avoids_duplicates(world, tmp_path, capsys):
    world.mailbox = [(index, b"raw") for index in range(1, 61)]
    root = str(tmp_path)
    seen = set()

    # Corrida 1: pagina de 25 desde el inicio (cursor 0).
    code = cli.cli_main(["sync", root, "personal", "--limit", "25"])
    assert code == 0
    assert world.fetched_uids == list(range(1, 26))
    assert world.cursor_saves == [("personal", 25)], (
        "el cursor debe avanzar al maximo imap_uid de la pagina"
    )
    seen.update(world.fetched_uids)

    # Corrida 2: pagina de 10; la config debe llevar since_uid del cursor.
    code = cli.cli_main(["sync", root, "personal", "--limit", "10"])
    assert code == 0
    assert world.last_config["since_uid"] == 25, (
        "la segunda corrida debe continuar desde el cursor UID guardado"
    )
    assert world.fetched_uids[25:] == list(range(26, 36))
    seen.update(world.fetched_uids[25:])

    # Corrida 3: default (sin --limit) completa el resto desde el cursor 35.
    code = cli.cli_main(["sync", root, "personal"])
    assert code == 0
    assert world.last_config["since_uid"] == 35
    assert world.fetched_uids[35:] == list(range(36, 61))
    seen.update(world.fetched_uids[35:])

    assert len(seen) == len(world.fetched_uids), (
        "entre corridas no debe haber duplicados (filtro since_uid por UID)"
    )


def test_sync_limit_empty_page_keeps_cursor(world, tmp_path, capsys):
    world.mailbox = [(index, b"raw") for index in range(1, 4)]
    root = str(tmp_path)
    world.cursors[(root, "personal")] = 3
    code = cli.cli_main(["sync", root, "personal", "--limit", "5"])
    assert code == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["fetched"] == 0 and summary["persisted"] == 0
    assert world.cursor_saves == [], (
        "sin mensajes nuevos el cursor no debe reescribirse"
    )
    assert world.cursors[(root, "personal")] == 3, (
        "el cursor debe quedar intacto cuando la pagina es vacia"
    )