"""Tests congelados del contrato cli_sync.

Oracle independiente: no importa el target ni cli.py ni ningun modulo de
src.email. No abre red real, no usa credenciales reales ni lanza procesos.
Verifica la estructura del contrato (frontmatter, presupuestos, 7 secciones,
frase de parada, delegacion en las nueve dependencias incluidas las dos del
cursor, compatibilidad de search/account) y re-deriva los casos congelados del
bloque frozen-cases con una CLI de referencia propia: store JSON espejo en
<root>/.email-agent/, resolver de credenciales espejo sobre un environ
ficticio, sesion IMAP simulada (con imap_uid int por record y filtro
id > since_uid), store de cursor espejo en <root>/.email-agent/cursors.json,
persistencia de referencia via persist_email_okf_at con rel_path relativo al
root y delegacion de contactos de referencia a store_email_contacts.
"""

import json
from pathlib import Path
import re
import tempfile

CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "contracts"
    / "cli-sync.md"
)

PROVIDER_HOSTS = {"gmail": "imap.gmail.com", "outlook": "outlook.office365.com"}
SUMMARY_KEYS = {
    "account_id",
    "fetched",
    "persisted",
    "persisted_paths",
    "contacts_updated",
}

CASE_NAMES = {
    "help_shows_usage",
    "sync_with_explicit_host",
    "sync_default_host_gmail",
    "sync_default_host_outlook",
    "sync_cursor_advances",
    "sync_cursor_resume",
    "sync_empty_mailbox_keeps_cursor",
    "sync_account_missing",
    "sync_credential_missing",
    "sync_unknown_provider_no_host",
    "sync_fetch_error",
    "sync_corrupt_store",
    "sync_cursor_corrupt",
    "sync_no_args",
    "sync_missing_args",
    "sync_extra_args",
}


def _contract_text():
    return CONTRACT.read_text(encoding="utf-8")


def _fenced_block(text, label):
    match = re.search(
        r"```" + label + r"\n(.*?)\n```", text, re.DOTALL
    )
    assert match is not None, "bloque " + label + " ausente en el contrato"
    return match.group(1)


def _frozen_cases():
    return json.loads(_fenced_block(_contract_text(), "frozen-cases"))


def _case(name):
    return {c["name"]: c for c in _frozen_cases()}[name]


# --------------------------------------------------------------------------
# Modelo de referencia: store espejo, credenciales espejo, IMAP simulado,
# persistencia y contactos de referencia. Nada de esto importa src.email.
# --------------------------------------------------------------------------

class _ReferenceError(Exception):
    """Fallo de operacion traducido al codigo 1."""


class _SyncWorld:
    """Estado ficticio de una ejecucion: store, environ, IMAP y escrituras."""

    def __init__(self, case, tmp):
        self.case = case
        self.root = Path(tmp)
        self.environ = dict(case.get("environ", {}))
        self.messages = list(case.get("messages", []))
        self.fetch_calls = 0
        self.persist_calls = 0
        self.contacts_calls = 0
        # Mensajes efectivos devueltos por el mundo (tras el filtro
        # since_uid): las aserciones de contactos comparan contra esta
        # lista, no contra los mensajes crudos del caso.
        self.fetched_messages = []
        self.hosts = []
        self.persisted = []
        self.store_calls = 0
        self.stored_contacts = []
        self.cursor_loads = []
        self.cursor_saves = []
        # Estado del store de cursor segun el modelo: lo materializan
        # load_sync_cursor/save_sync_cursor; las aserciones lo leen de aqui,
        # no del archivo en disco.
        self.cursor_values = {}
        self.written = []
        self.last_config = None
        tree = dict(case.get("tree", {}))
        if "store" in case:
            tree[".email-agent/accounts.json"] = json.dumps(case["store"])
        for relpath, content in tree.items():
            target = self.root / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    def load_email_accounts(self, root):
        path = Path(root) / ".email-agent" / "accounts.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _ReferenceError("error: el store de cuentas es ilegible") from exc
        if not isinstance(data, list) or not all(
            isinstance(item, dict) for item in data
        ):
            raise _ReferenceError("error: el store de cuentas es ilegible")
        return data

    def resolve_credential(self, credential_ref):
        if not isinstance(credential_ref, str):
            raise _ReferenceError("error: credencial irresoluble")
        if not credential_ref.startswith("env://"):
            raise _ReferenceError("error: credencial irresoluble")
        variable = credential_ref[len("env://"):]
        if variable not in self.environ:
            raise _ReferenceError("error: credencial irresoluble")
        return self.environ[variable]

    def load_sync_cursor(self, root, account_id):
        """Espejo de load_sync_cursor: 0 si no hay entrada, error si corrupto."""
        self.cursor_loads.append(account_id)
        path = Path(root) / ".email-agent" / "cursors.json"
        if not path.exists():
            return self.cursor_values.get(account_id, 0)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _ReferenceError("error: el store de cursor es ilegible") from exc
        cursors = data.get("cursors") if isinstance(data, dict) else None
        if not isinstance(cursors, dict) or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in cursors.values()
        ):
            raise _ReferenceError("error: el store de cursor es ilegible")
        value = cursors.get(account_id, 0)
        self.cursor_values[account_id] = value
        return value

    def save_sync_cursor(self, root, account_id, uid):
        """Espejo de save_sync_cursor: reemplaza la entrada y escribe el JSON."""
        self.cursor_saves.append([account_id, uid])
        path = Path(root) / ".email-agent" / "cursors.json"
        cursors = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise _ReferenceError("error: el store de cursor es ilegible") from exc
            cursors = data.get("cursors", {}) if isinstance(data, dict) else {}
            if not isinstance(cursors, dict):
                raise _ReferenceError("error: el store de cursor es ilegible")
        cursors = dict(cursors)
        cursors[account_id] = uid
        self.cursor_values[account_id] = uid
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"cursors": cursors}, sort_keys=True), encoding="utf-8"
        )
        return path.as_posix()

    def fetch_imap_messages(self, account, config):
        self.fetch_calls += 1
        self.last_config = dict(config)
        self.hosts.append(config["host"])
        if self.case.get("fetch_error"):
            raise _ReferenceError("error: la lectura IMAP fallo")
        # Cada record garantiza imap_uid int (fetch-imap-messages): si el
        # mensaje del caso no lo trae, se asigna el ordinal de la sesion.
        records = []
        for index, message in enumerate(self.messages, 1):
            record = dict(message)
            record.setdefault("imap_uid", message.get("imap_uid", index))
            records.append(record)
        # Filtro del cursor: id estrictamente mayor que since_uid, ascendente.
        since_uid = config.get("since_uid", 0)
        records = [r for r in records if r["imap_uid"] > since_uid]
        records.sort(key=lambda record: record["imap_uid"])
        self.fetched_messages = records
        return records

    def persist_email_okf_at(self, record, root, rel_path):
        self.persist_calls += 1
        target = Path(root) / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\ntype: Email\n---\n", encoding="utf-8")
        self.persisted.append(target.relative_to(self.root).as_posix())
        # El contrato congela rutas con separador / (ejemplo: .../store/emails/x.md).
        return target.as_posix()

    def extract_contacts(self, record):
        self.contacts_calls += 1
        contacts = []
        seen = set()
        for key in ("from", "to", "cc"):
            raw = record.get(key) or ""
            for chunk in raw.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if "<" in chunk and ">" in chunk:
                    name = chunk[: chunk.index("<")].strip()
                    email = chunk[chunk.index("<") + 1: chunk.index(">")].strip()
                else:
                    name, email = "", chunk
                email_key = email.lower()
                if not email_key or email_key in seen:
                    continue
                seen.add(email_key)
                contacts.append({"email": email_key, "name": name})
        return contacts

    def store_email_contacts(self, root, contacts):
        self.store_calls += 1
        self.stored_contacts.append(list(contacts))

    def snapshot(self):
        self.written = sorted(
            p.relative_to(self.root).as_posix()
            for p in self.root.rglob("*.md")
        )
        return self


USAGE_LINES = [
    "usage: email-cli [--help] | email-cli search ROOT QUERY | "
    "email-cli account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF | "
    "email-cli account list ROOT | email-cli sync ROOT ACCOUNT_ID [HOST]",
    "  sync ROOT ACCOUNT_ID [HOST]  sincroniza una cuenta guardada",
]


def _reference_sync(world, root, account_id, host_arg):
    """Semantica de referencia de la rama sync segun el contrato."""
    # La carga del cursor ocurre ANTES del fetch (contrato) y antes de tocar
    # IMAP: queda registrada en cursor_loads incluso cuando falla.
    try:
        cursor = world.load_sync_cursor(root, account_id)
    except _ReferenceError as exc:
        return 1, [], [str(exc)]
    try:
        accounts = world.load_email_accounts(root)
    except _ReferenceError as exc:
        return 1, [], [str(exc)]
    account = next(
        (a for a in accounts if a.get("account_id") == account_id), None
    )
    if account is None:
        return 1, [], ["error: cuenta no encontrada"]
    try:
        secret = world.resolve_credential(account["credential_ref"])
    except _ReferenceError as exc:
        return 1, [], [str(exc)]
    if host_arg is not None:
        host = host_arg
    elif account.get("provider") in PROVIDER_HOSTS:
        host = PROVIDER_HOSTS[account["provider"]]
    else:
        return 1, [], ["error: provider sin host por defecto"]
    config = {
        "host": host,
        "username": account["email"],
        "password": secret,
        "since_uid": cursor,
    }
    try:
        messages = world.fetch_imap_messages(account, config)
    except _ReferenceError as exc:
        return 1, [], [str(exc)]
    persisted_paths = []
    for record in messages:
        rel_path = "store/emails/" + record["raw_sha256"] + ".md"
        persisted_paths.append(
            world.persist_email_okf_at(record, root, rel_path)
        )
    contacts = []
    seen = set()
    for record in messages:
        for contact in world.extract_contacts(record):
            if contact["email"] in seen:
                continue
            seen.add(contact["email"])
            contacts.append(contact)
    # Delegacion UNICA: los contactos deduplicados se entregan una sola vez a
    # store_email_contacts, que reemplaza la escritura de nodos .md.
    world.store_email_contacts(root, contacts)
    # Cursor incremental: solo se avanza si hubo records, con el max imap_uid,
    # despues de un sync exitoso y antes de imprimir el resumen.
    if messages:
        try:
            world.save_sync_cursor(
                root, account_id, max(r["imap_uid"] for r in messages)
            )
        except _ReferenceError as exc:
            return 1, [], [str(exc)]
    summary = {
        "account_id": account_id,
        "fetched": len(messages),
        "persisted": len(persisted_paths),
        "persisted_paths": persisted_paths,
        "contacts_updated": True,
    }
    return 0, [json.dumps(summary, sort_keys=True)], []


def _reference_cli(world, argv):
    if argv and argv[0] in ("-h", "--help"):
        return 0, list(USAGE_LINES), []
    if not argv or argv[0] not in ("sync", "search", "account"):
        return 2, [], ["error: subcomando invalido"] + USAGE_LINES
    if argv[0] != "sync":
        # search/account conservan su semantica ya congelada en cli_search y
        # cli_accounts; este oráculo no la re-deriva, solo exige que exista.
        return 0, [], []
    rest = argv[1:]
    # Aridad congelada por los frozen-cases: ROOT y ACCOUNT_ID siempre, HOST
    # opcional (los casos exitosos tienen 2 o 3 args tras el subcomando; 0, 1
    # o 4 args son error de argumentos con codigo 2).
    if len(rest) not in (2, 3):
        return 2, [], ["error: sync requiere ROOT y ACCOUNT_ID y opcional HOST"] + USAGE_LINES
    root, account_id = rest[0], rest[1]
    host_arg = rest[2] if len(rest) == 3 else None
    return _reference_sync(world, root, account_id, host_arg)


def _run_case(case):
    """Sustituye <root> por un arbol temporal y ejecuta la referencia CLI."""
    with tempfile.TemporaryDirectory() as tmp:
        world = _SyncWorld(case, tmp)
        argv = [a.replace("<root>", tmp) for a in case["argv"]]
        code, stdout, stderr = _reference_cli(world, argv)
        return code, stdout, stderr, world.snapshot()


def _assert_case(case, code, stdout, stderr):
    assert code == case["code"], "codigo inesperado en " + case["name"]
    if "stdout" in case:
        assert stdout == case["stdout"], "stdout inesperado en " + case["name"]
    for fragment in case.get("stdout_has", []):
        assert fragment in "\n".join(stdout), (
            "stdout sin " + repr(fragment) + " en " + case["name"]
        )
    for fragment in case.get("stderr_has", []):
        assert fragment in "\n".join(stderr).lower(), (
            "stderr sin " + repr(fragment) + " en " + case["name"]
        )
    if case["code"] != 0:
        assert stderr, "falta mensaje amigable en stderr en " + case["name"]
        assert "Traceback" not in "\n".join(stderr), (
            "traceback expuesto al usuario en " + case["name"]
        )


def _assert_no_secrets(case, stdout, stderr):
    joined = "\n".join(stdout) + "\n" + "\n".join(stderr)
    for secret in case.get("secrets", []):
        assert secret not in joined, (
            "el secreto " + repr(secret) + " aparece en la salida de " + case["name"]
        )


# --------------------------------------------------------------------------
# Estructura del contrato
# --------------------------------------------------------------------------

def test_contract_frontmatter_and_budgets():
    text = _contract_text()
    frontmatter = text.split("---\n", 2)[1]
    assert "task: cli_sync" in frontmatter
    assert "signature: \"def cli_main(argv: list) -> int\"" in frontmatter
    assert "target: src/email/cli.py" in frontmatter
    assert "cyclomatic_max: 20" in frontmatter
    assert "nesting_max: 4" in frontmatter
    assert "lines_max: 80" in frontmatter
    assert "params_max: 5" in frontmatter
    assert "deps_allowed: [argparse, sys, json, pathlib]" in frontmatter
    assert "forbids: [eval, exec, subprocess]" in frontmatter
    assert "tests: tests/frozen_cli_sync.py" in frontmatter
    assert "python -m pytest outputs/email-agent-kdd/tests/frozen_cli_sync.py -q" in text


def test_contract_has_seven_sections_and_stop_phrase():
    text = _contract_text()
    for section in (
        "## Intent",
        "## Interface",
        "## Invariants",
        "## Examples",
        "## Do / Don't",
        "## Tests",
        "## Constraints",
    ):
        assert section in text, "seccion ausente: " + section
    assert "PARAR y reportar si" in text
    assert "no existen con esa firma" in text, (
        "la frase de parada debe cubrir firmas de dependencias ausentes"
    )
    assert "reimplementar" in text, (
        "la frase de parada debe cubrir la reimplementacion de dependencias"
    )


def test_contract_delegates_to_nine_dependencies():
    text = _contract_text()
    delegates = {
        "src.email.account_store.load_email_accounts":
            "def load_email_accounts(root: str) -> list",
        "src.email.credentials.resolve_credential":
            "def resolve_credential(credential_ref: str, environ=None) -> str",
        "src.email.imap_reader.fetch_imap_messages":
            "def fetch_imap_messages(account: dict, config: dict, connection_factory=None) -> list",
        "src.email.sync.sync_email_account":
            "def sync_email_account(account: dict, fetch_messages, persist_message, update_contacts=None) -> dict",
        "src.email.persist_at.persist_email_okf_at":
            "def persist_email_okf_at(record: dict, root: str, rel_path: str) -> str",
        "src.email.contacts.extract_contacts":
            "def extract_contacts(record: dict) -> list",
        "src.email.contact_store.store_email_contacts":
            "def store_email_contacts(root: str, contacts: list) -> int",
        "src.email.cursor_store.load_sync_cursor":
            "def load_sync_cursor(root: str, account_id: str) -> int",
        "src.email.cursor_store.save_sync_cursor":
            "def save_sync_cursor(root: str, account_id: str, uid: int) -> str",
    }
    for module, signature in delegates.items():
        assert module in text, "la CLI debe delegar en " + module
        assert signature in text, "firma congelada ausente: " + signature
    assert "jamas reimplementadas" in text, (
        "el contrato debe prohibir reimplementar las nueve dependencias"
    )
    assert "store/emails/<raw_sha256>.md" in text, (
        "el contrato debe congelar el rel_path relativo de persistencia"
    )
    assert "UNA sola vez" in text, (
        "el contrato debe congelar la delegacion unica de contactos"
    )
    assert "imap.gmail.com" in text and "outlook.office365.com" in text, (
        "el contrato debe congelar los hosts por defecto de gmail y outlook"
    )
    assert "since_uid" in text and "imap_uid" in text, (
        "el contrato debe congelar since_uid en la config y imap_uid por record"
    )
    assert "ANTES del fetch" in text, (
        "el contrato debe congelar la carga del cursor antes del fetch"
    )


def test_contract_freezes_search_and_account_compatibility():
    text = _contract_text()
    assert "cli_search" in text and "cli_accounts" in text, (
        "el contrato debe declarar la compatibilidad con cli_search y cli_accounts"
    )
    assert "search ROOT QUERY" in text
    assert "account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF" in text
    assert "account list ROOT" in text
    assert "sync ROOT ACCOUNT_ID [HOST]" in text
    assert "no cambia en nada" in text, (
        "la semantica de search y account debe quedar intacta por contrato"
    )


# --------------------------------------------------------------------------
# Forma de los frozen-cases
# --------------------------------------------------------------------------

def test_frozen_cases_shape_and_determinism():
    cases = _frozen_cases()
    names = {case["name"] for case in cases}
    assert len(cases) >= 10, "el contrato debe congelar al menos 10 casos"
    assert CASE_NAMES <= names, (
        "faltan casos congelados: " + repr(CASE_NAMES - names)
    )
    for case in cases:
        assert isinstance(case["argv"], list), "argv debe ser lista"
        assert case["code"] in (0, 1, 2), "codigo de salida no previsto"
        if case["code"] == 0 and case["argv"][0] == "sync":
            assert "stdout_json" in case, "caso sync exitoso debe congelar resumen"
            assert "expected_host" in case, "caso sync exitoso debe congelar host"
            assert "expected_since_uid" in case, (
                "caso sync exitoso debe congelar since_uid de la config de fetch"
            )
            assert "cursor_saves" in case, (
                "caso sync exitoso debe congelar el guardado del cursor"
            )
            assert "persist_paths" in case, "caso sync exitoso debe congelar rutas"
            assert "contacts" in case, "caso sync exitoso debe congelar contactos"
        if case["code"] != 0:
            assert case.get("stderr_has"), "falta mensaje amigable congelado"
            if case["argv"][0] == "sync" and case["code"] == 1:
                assert "fetch_calls" in case, "caso de error debe congelar llamadas"
    codes = {case["name"]: case["code"] for case in cases}
    assert codes["help_shows_usage"] == 0
    assert codes["sync_with_explicit_host"] == 0
    assert codes["sync_default_host_gmail"] == 0
    assert codes["sync_default_host_outlook"] == 0
    assert codes["sync_cursor_advances"] == 0
    assert codes["sync_cursor_resume"] == 0
    assert codes["sync_empty_mailbox_keeps_cursor"] == 0
    assert codes["sync_account_missing"] == 1
    assert codes["sync_credential_missing"] == 1
    assert codes["sync_unknown_provider_no_host"] == 1
    assert codes["sync_fetch_error"] == 1
    assert codes["sync_corrupt_store"] == 1
    assert codes["sync_cursor_corrupt"] == 1
    assert codes["sync_no_args"] == 2
    assert codes["sync_missing_args"] == 2
    assert codes["sync_extra_args"] == 2


# --------------------------------------------------------------------------
# frozen-cases: ayuda
# --------------------------------------------------------------------------

def test_frozen_cases_help_shows_sync_usage():
    case = _case("help_shows_usage")
    code, stdout, stderr, _world = _run_case(case)
    _assert_case(case, code, stdout, stderr)
    assert code == 0
    assert stderr == [], "la ayuda no debe escribir en stderr"
    joined = "\n".join(stdout)
    assert "usage:" in joined, "la ayuda debe imprimir el usage en stdout"
    for fragment in ("search ROOT QUERY", "account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF",
                     "account list ROOT", "sync ROOT ACCOUNT_ID [HOST]"):
        assert fragment in joined, "la ayuda debe documentar " + fragment


# --------------------------------------------------------------------------
# frozen-cases: sync exitoso
# --------------------------------------------------------------------------

def test_frozen_cases_sync_success_prints_summary_json():
    for name in (
        "sync_with_explicit_host",
        "sync_default_host_gmail",
        "sync_default_host_outlook",
        "sync_cursor_advances",
        "sync_cursor_resume",
        "sync_empty_mailbox_keeps_cursor",
    ):
        case = _case(name)
        assert case["code"] == 0, "sync exitoso debe retornar 0"
        code, stdout, stderr, world = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        _assert_no_secrets(case, stdout, stderr)
        assert stderr == [], "sync exitoso no debe escribir en stderr"
        assert len(stdout) == 1, "el resumen debe ser exactamente una linea"
        summary = json.loads(stdout[0])
        assert set(summary) == SUMMARY_KEYS, (
            "el resumen debe tener exactamente las 5 claves congeladas"
        )
        for key, value in case["stdout_json"].items():
            assert summary[key] == value, (
                "resumen con " + key + " inesperado en " + name
            )
        assert summary["contacts_updated"] is True
        assert world.hosts == [case["expected_host"]], (
            "host elegido inesperado en " + name
        )
        assert world.last_config["host"] == case["expected_host"]
        assert world.last_config["password"] in case["environ"].values()
        assert "password" not in stdout[0] and "credential_ref" not in stdout[0], (
            "el resumen no debe exponer password ni credential_ref en " + name
        )
        expected_rel = [
            str(Path(world.root / rel).relative_to(world.root).as_posix())
            for rel in case["persist_paths"]
        ]
        assert world.persisted == expected_rel, (
            "persisted_paths fuera de orden en " + name
        )
        assert summary["persisted_paths"] == [
            str(world.root / rel).replace("\\", "/")
            for rel in case["persist_paths"]
        ], "rutas persistidas en el resumen inesperadas en " + name
        assert world.store_calls == 1, (
            "los contactos deben delegarse UNA sola vez a store_email_contacts en "
            + name
        )
        assert world.stored_contacts == [case["contacts"]], (
            "contactos deduplicados delegados inesperados en " + name
        )
        assert world.contacts_calls == len(world.fetched_messages), (
            "extract_contacts debe aplicarse a cada mensaje devuelto por el "
            "mundo (tras el filtro since_uid) en " + name
        )
        assert world.fetch_calls == 1, (
            "debe haber exactamente una sesion de fetch en " + name
        )
        # Cursor: carga ANTES del fetch, since_uid en la config y guardado
        # UNA vez (solo si hubo records) con el maximo imap_uid.
        assert world.cursor_loads == [case["argv"][2]], (
            "el cursor debe cargarse exactamente una vez antes del fetch en " + name
        )
        assert world.last_config["since_uid"] == case["expected_since_uid"], (
            "since_uid de la config de fetch inesperado en " + name
        )
        assert world.cursor_saves == case["cursor_saves"], (
            "guardado del cursor inesperado en " + name
        )
        for rel in case["persist_paths"]:
            assert rel in world.written, (
                "falta nodo del mensaje " + rel + " en " + name
            )
        assert not any(
            rel.startswith("store/conversations/") or rel.startswith("store/topics/")
            for rel in summary["persisted_paths"]
        ), "persisted_paths no debe incluir indices en " + name


def test_frozen_cases_cursor_advances_to_max_imap_uid():
    for name in ("sync_cursor_advances", "sync_cursor_resume"):
        case = _case(name)
        code, stdout, stderr, world = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        _assert_no_secrets(case, stdout, stderr)
        assert world.cursor_loads == [case["argv"][2]], (
            "el cursor debe leerse una vez antes del fetch en " + name
        )
        assert world.last_config["since_uid"] == case["expected_since_uid"], (
            "since_uid con el cursor cargado inesperado en " + name
        )
        assert world.cursor_saves == case["cursor_saves"], (
            "el cursor debe guardarse una vez con el maximo imap_uid en " + name
        )
        account_id_value, uid_value = case["cursor_saves"][0]
        assert world.cursor_values.get(account_id_value) == uid_value, (
            "valor del cursor tras el guardado inesperado en " + name
        )


def test_frozen_cases_empty_mailbox_keeps_cursor():
    case = _case("sync_empty_mailbox_keeps_cursor")
    code, stdout, stderr, world = _run_case(case)
    _assert_case(case, code, stdout, stderr)
    _assert_no_secrets(case, stdout, stderr)
    assert len(stdout) == 1, "el resumen debe ser exactamente una linea"
    summary = json.loads(stdout[0])
    assert set(summary) == SUMMARY_KEYS, (
        "el resumen de bandeja vacia conserva las 5 claves"
    )
    assert summary["fetched"] == 0 and summary["persisted"] == 0, (
        "bandeja vacia: fetched y persisted deben ser 0"
    )
    assert summary["persisted_paths"] == [], (
        "bandeja vacia: persisted_paths vacia"
    )
    assert world.last_config["since_uid"] == case["expected_since_uid"], (
        "since_uid debe ser el cursor cargado incluso con bandeja vacia"
    )
    assert world.persist_calls == 0, "nada persistido con bandeja vacia"
    assert world.store_calls == 1, (
        "store_email_contacts sigue llamandose una vez con bandeja vacia"
    )
    assert world.cursor_saves == [], (
        "bandeja vacia: el cursor no debe escribirse ni avanzarse"
    )
    assert world.cursor_loads == ["personal"], (
        "bandeja vacia: el cursor debe cargarse exactamente una vez"
    )
    assert world.cursor_values.get("personal") == 30, (
        "el cursor debe quedar intacto con bandeja vacia"
    )


def test_frozen_cases_host_map_and_override():
    assert _case("sync_with_explicit_host")["expected_host"] == "imap.custom.test", (
        "HOST en argv debe usarse verbatim"
    )
    assert _case("sync_default_host_gmail")["expected_host"] == PROVIDER_HOSTS["gmail"]
    assert _case("sync_default_host_outlook")["expected_host"] == PROVIDER_HOSTS["outlook"]


# --------------------------------------------------------------------------
# frozen-cases: errores de operacion (codigo 1)
# --------------------------------------------------------------------------

def test_frozen_cases_sync_operation_errors_return_1():
    for name in (
        "sync_account_missing",
        "sync_credential_missing",
        "sync_unknown_provider_no_host",
        "sync_fetch_error",
        "sync_corrupt_store",
        "sync_cursor_corrupt",
    ):
        case = _case(name)
        assert case["code"] == 1, "fallo de operacion debe retornar 1"
        code, stdout, stderr, world = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        _assert_no_secrets(case, stdout, stderr)
        assert stdout == [], "nada en stdout en fallo de operacion"
        assert world.fetch_calls == case.get("fetch_calls", 0), (
            "llamadas a fetch inesperadas en " + name
        )
        assert world.persist_calls == 0, (
            "nada persistido en fallo de operacion en " + name
        )
        assert world.store_calls == 0, (
            "ninguna delegacion a store_email_contacts en fallo de operacion en "
            + name
        )
        assert world.stored_contacts == case.get("contacts", []), (
            "contactos inesperados en fallo de operacion en " + name
        )
        assert world.written == [], (
            "ningun nodo debe escribirse en fallo de operacion en " + name
        )
        assert world.cursor_saves == [], (
            "ningun guardado de cursor en fallo de operacion en " + name
        )
        assert "error" in "\n".join(stderr).lower(), (
            "el fallo debe dar mensaje generico amigable en " + name
        )


def test_frozen_cases_error_call_counts():
    assert _case("sync_account_missing")["fetch_calls"] == 0, (
        "cuenta ausente no debe tocar IMAP"
    )
    assert _case("sync_credential_missing")["fetch_calls"] == 0, (
        "credencial ausente no debe tocar IMAP"
    )
    assert _case("sync_unknown_provider_no_host")["fetch_calls"] == 0, (
        "provider sin host no debe abrir conexion"
    )
    assert _case("sync_fetch_error")["fetch_calls"] == 1, (
        "el fallo de fetch ocurre dentro de la unica sesion IMAP"
    )
    assert _case("sync_corrupt_store")["fetch_calls"] == 0, (
        "store corrupto no debe tocar IMAP"
    )
    assert _case("sync_cursor_corrupt")["fetch_calls"] == 0, (
        "cursor corrupto no debe tocar IMAP: la carga falla antes del fetch"
    )


def test_frozen_cases_missing_credential_is_generic():
    case = _case("sync_credential_missing")
    _, stdout, stderr, _world = _run_case(case)
    joined = ("\n".join(stdout) + "\n" + "\n".join(stderr)).lower()
    for fragment in ("credential_ref", "variable_ausente", "password", "marcador"):
        assert fragment not in joined, (
            "el error de credencial debe ser generico, sin " + repr(fragment)
        )


def test_frozen_cases_cursor_corrupt_is_operational_error():
    case = _case("sync_cursor_corrupt")
    code, stdout, stderr, world = _run_case(case)
    _assert_case(case, code, stdout, stderr)
    _assert_no_secrets(case, stdout, stderr)
    assert stdout == [], "nada en stdout con cursor corrupto"
    assert world.cursor_loads == ["personal"], (
        "el cursor se intenta leer una vez antes del fetch"
    )
    assert world.fetch_calls == 0 and world.persist_calls == 0, (
        "cursor corrupto: nada de fetch ni persistencia"
    )
    assert world.store_calls == 0 and world.cursor_saves == [], (
        "cursor corrupto: nada de contactos ni guardado de cursor"
    )
    assert "error" in "\n".join(stderr).lower(), (
        "el fallo de cursor debe dar mensaje generico amigable"
    )


# --------------------------------------------------------------------------
# frozen-cases: errores de argumentos (codigo 2)
# --------------------------------------------------------------------------

def test_frozen_cases_arg_errors_are_friendly():
    for name in ("sync_no_args", "sync_missing_args", "sync_extra_args"):
        case = _case(name)
        assert case["code"] == 2, "error de argumentos debe retornar 2"
        code, stdout, stderr, _world = _run_case(case)
        _assert_case(case, code, stdout, stderr)
        assert stdout == [], "nada en stdout en error de argumentos"
        assert "usage:" in "\n".join(stderr).lower(), (
            "el error de argumentos debe mostrar el usage en " + name
        )
        assert "sync ROOT ACCOUNT_ID [HOST]" in "\n".join(stderr), (
            "el usage debe documentar sync ROOT ACCOUNT_ID [HOST] en " + name
        )


# --------------------------------------------------------------------------
# frozen-cases: ausencia de secretos en toda la salida
# --------------------------------------------------------------------------

def test_frozen_cases_secrets_never_leak():
    for case in _frozen_cases():
        code, stdout, stderr, _world = _run_case(case)
        assert code == case["code"], "codigo inesperado en " + case["name"]
        _assert_no_secrets(case, stdout, stderr)
        assert "traceback" not in "\n".join(stderr).lower()