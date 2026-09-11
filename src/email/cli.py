"""CLI local de correo: capa fina de presentacion sobre search, cuentas y sync.

Interpreta `argv` (sin el nombre del programa): `--help`/`-h`, el subcomando
`query ROOT INSTRUCTION`, el subcomando `search ROOT QUERY`, el subcomando
`account` (`setup ROOT` guiado, `add ROOT ACCOUNT_ID PROVIDER EMAIL
CREDENTIAL_REF` y `list ROOT`), el subcomando `sync ROOT ACCOUNT_ID [HOST]
[--limit N] [--unread] [--attachments CONFIRMAR EXTRACCION]` (con
`--attachments` guarda los blobs de adjuntos permitidos reutilizando el
RFC822 ya descargado, con presupuesto por sync; sin la frase literal aborta
antes de conectar, y sin la opcion jamas se persiste un byte) o el subcomando
`message` (`delete ROOT REL_PATH`, `restore ROOT TRASH_REL_PATH`,
`trash ROOT`, `purge ROOT TRASH_REL_PATH CONFIRMAR BORRADO PERMANENTE`
que delega el borrado reversible en deletion, y los comandos remotos
`remote-delete`, `remote-restore` y `remote-purge` que delegan en
imap_deletion) y el subcomando `attachment` (`list ROOT REL_PATH`, solo
metadatos, y `download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION` que
re-fetchea el mensaje por UID readonly, guarda el blob content-addressed con
`authorize=True` y copia bajo ROOT, delegando en attachments e imap_reader). Los datos van a stdout; usage
y errores a stderr, siempre genericos
(sin `credential_ref` ni secretos ni tracebacks). Codigos: 0 exito/ayuda,
1 fallo de operacion, 2 error de argumentos. La lectura de cuentas, la
resolucion de credenciales, la carga de servidores guardados, el fetch IMAP,
la orquestacion, la persistencia OKF y la extraccion/almacen de contactos no
se reimplementan: se delega en account, account_store, attachments, search, credentials,
mail_server_store, imap_reader, imap_deletion, sync, persist_at, contacts,
contact_store, outgoing_contacts y cursor_store.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from builtins import input
from pathlib import Path

from src.email.account import create_email_account
from src.email.account_store import load_email_accounts, save_email_account
from src.email.attachments import (
    AttachmentError,
    GC_CONFIRMATION,
    MAX_ATTACHMENT_BYTES,
    blob_path,
    extract_attachment_bytes,
    gc_execute,
    gc_scan,
    is_type_allowed,
    legacy_attachment_block,
    list_node_attachments,
    mark_attachment_stored,
    read_attachment_entries,
    read_download_target,
    sanitize_display_name,
    store_attachment_bytes,
    store_record_attachments,
    write_node_text_atomic,
)
from src.email.confirm import confirm_email_draft
from src.email.contacts import extract_contacts
from src.email.contact_store import load_email_contacts, store_email_contacts
from src.email.cursor_store import load_sync_cursor, save_sync_cursor
from src.email.deletion import (
    list_trash,
    purge,
    restore,
    soft_delete,
)
from src.email.draft import create_email_draft
from src.email.smtp_send import send_smtp_message
from src.email.conversation_index import persist_conversation_index
from src.email.credentials import resolve_credential
from src.email.mail_server_store import load_mail_server_config
from src.email.imap_reader import (
    DEFAULT_MAILBOX,
    fetch_imap_messages,
    fetch_raw_message_by_uid,
)
from src.email.imap_deletion import ImapDeletionProvider
from src.email.node import read_email_node
from src.email.outgoing_contacts import extract_outgoing_contacts
from src.email.persist_at import persist_email_okf_at
from src.email.topic_index import persist_topic_index
from src.email.query import query_email
from src.email.search import search_email_nodes
from src.email.sync import sync_email_account
from src.email.notifications import notify_new_records
from src.email.notifications import delete_notification_rule, list_notification_rules, save_notification_rule, set_notification_rule_enabled
from src.email.autostart import install_startup, remove_startup, startup_status
from src.email.unlink import unlink_email_account
from src.email.diagnostics import run_diagnostics, write_diagnostic_report, _write_diagnostic_report
from src.email.language import load_language, save_language, normalize_language

USAGE = (
    "usage: email-agent [--help] | email-agent query ROOT INSTRUCTION | "
    "email-agent search ROOT QUERY | "
    "email-agent read ROOT REL_PATH | "
    "email-agent account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF | "
    "email-agent account setup ROOT [--lang es|en|pt] | "
    "email-agent account setup-gui ROOT | "
    "email-agent account remove ROOT ACCOUNT_ID CONFIRMAR DESVINCULAR | "
    "email-agent account list ROOT | email-agent contact list ROOT | "
    "email-agent sync ROOT ACCOUNT_ID [HOST] [--limit N] [--unread] "
    "[--attachments CONFIRMAR EXTRACCION] | "
    "email-agent watch ROOT ACCOUNT_ID [--every N] [--limit N] [--unread] | "
    "email-agent notification add|list|show|delete ROOT ... | "
    "email-agent startup install|status|remove ROOT ACCOUNT_ID ... | "
    "email-agent doctor [ROOT] [--fix] [--lang es|en|pt] [--format json|text] [--report FILE] | "
    "email-agent language set|get ROOT [es|en|pt] | "
    "email-agent onboard ROOT [--gui|--terminal] [--lang es|en|pt] | "
    "email-agent message delete ROOT REL_PATH | "
    "email-agent message restore ROOT TRASH_REL_PATH | "
    "email-agent message trash ROOT | "
    "email-agent message purge ROOT TRASH_REL_PATH CONFIRMAR BORRADO PERMANENTE | "
    "email-agent message remote-delete ROOT ACCOUNT_ID UID TRASH_MAILBOX | "
    "email-agent message remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX "
    "ORIGINAL_MAILBOX | "
    "email-agent message remote-purge ROOT ACCOUNT_ID UID MAILBOX "
    "CONFIRMAR BORRADO PERMANENTE | "
    "email-agent attachment list ROOT REL_PATH | "
    "email-agent attachment download ROOT REL_PATH INDEX DEST "
    "CONFIRMAR EXTRACCION | "
    "email-agent attachment gc ROOT [CONFIRMAR BORRADO ADJUNTOS] | "
    "email-agent draft ROOT ACCOUNT_ID TO SUBJECT BODY | "
    "email-agent send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR ENVIO"
)
SYNC_USAGE = (
    "  sync ROOT ACCOUNT_ID [HOST] [--limit N] [--unread] "
    "[--attachments CONFIRMAR EXTRACCION]  "
    "sincroniza una cuenta guardada (paginacion, default 50); con "
    "--attachments (frase literal) guarda los blobs de adjuntos permitidos "
    "reutilizando el RFC822 ya descargado, con presupuesto total por sync de "
    "SYNC_ATTACHMENT_BUDGET_MB (default 100 MB)"
)
WATCH_USAGE = (
    "  watch ROOT ACCOUNT_ID [--every N] [--limit N] [--unread]  "
    "sincroniza cada N segundos (default 300, minimo 30)"
)
LIMIT_MIN = 1
LIMIT_MAX = 100
_PROVIDER_HOSTS = {"gmail": "imap.gmail.com", "outlook": "outlook.office365.com"}
_PUBLIC_KEYS = ("account_id", "provider", "email", "status")
_SMTP_PROVIDER_HOSTS = {"gmail": "smtp.gmail.com", "outlook": "smtp.office365.com"}
_DEFAULT_SMTP_PORT = 587
_CONFIRMATION_PHRASE = "CONFIRMAR ENVIO"
_PURGE_CONFIRMATION = "CONFIRMAR BORRADO PERMANENTE"
_UNLINK_CONFIRMATION = "CONFIRMAR DESVINCULAR"
_EXTRACTION_CONFIRMATION = "CONFIRMAR EXTRACCION"
_NOTIFICATION_DELETE_CONFIRMATION = "CONFIRMAR REGLA"
# Presupuesto total por sync --attachments, en MB (default 100 MB). Un valor
# invalido de la env var aborta con error de argumentos antes de conectar.
_SYNC_ATTACHMENT_BUDGET_ENV = "SYNC_ATTACHMENT_BUDGET_MB"
_SYNC_ATTACHMENT_BUDGET_MB_DEFAULT = 100
_ATTACHMENT_KEYS = ("attachments", "adjuntos", "attachment")
_SETUP_INTRO = (
    "Configuracion guiada de cuenta "
    "(escribe 'cancelar' en cualquier paso para abortar):"
)
_SETUP_PROMPTS = (
    "1) Identificador de la cuenta (ej. personal): ",
    "2) Proveedor (gmail u outlook): ",
    "3) Correo electronico: ",
    "4) Nombre de la variable de entorno que guarda tu clave de aplicacion "
    "(ej. GMAIL_APP_PASSWORD; nunca la clave en si): ",
)
_SETUP_TEXT = {
    "es": {"intro": _SETUP_INTRO, "prompts": _SETUP_PROMPTS, "cancel_eof": "error: configuracion cancelada (entrada terminada)", "cancel_user": "error: configuracion cancelada por el usuario", "empty": "error: la respuesta no puede estar vacia", "provider": "error: proveedor no admitido (solo se admiten gmail u outlook)", "env": "error: nombre de variable de entorno invalido", "save": "error: no se pudo guardar la cuenta (datos o almacenamiento invalidos)"},
    "en": {"intro": "Guided account setup (type 'cancel' at any step to abort):", "prompts": ("1) Account identifier (e.g. personal): ", "2) Provider (gmail or outlook): ", "3) Email address: ", "4) Name of the environment variable holding your app password (e.g. GMAIL_APP_PASSWORD; never the password itself): "), "cancel_eof": "error: setup cancelled (input ended)", "cancel_user": "error: setup cancelled by the user", "empty": "error: the answer cannot be empty", "provider": "error: unsupported provider (only gmail or outlook are supported)", "env": "error: invalid environment variable name", "save": "error: account could not be saved (invalid data or storage)"},
    "pt": {"intro": "Configuracao guiada da conta (digite 'cancelar' em qualquer etapa para abortar):", "prompts": ("1) Identificador da conta (ex. pessoal): ", "2) Provedor (gmail ou outlook): ", "3) Endereco de email: ", "4) Nome da variavel de ambiente que guarda sua senha de aplicativo (ex. GMAIL_APP_PASSWORD; nunca a senha): "), "cancel_eof": "erro: configuracao cancelada (entrada encerrada)", "cancel_user": "erro: configuracao cancelada pelo usuario", "empty": "erro: a resposta nao pode ficar vazia", "provider": "erro: provedor nao suportado (somente gmail ou outlook)", "env": "erro: nome de variavel de ambiente invalido", "save": "erro: nao foi possivel salvar a conta (dados ou armazenamento invalidos)"},
}
_SETUP_ENV_NAME_HEAD = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_SETUP_ENV_NAME_TAIL = _SETUP_ENV_NAME_HEAD + "0123456789"


def _print_stderr(lines):
    for line in lines:
        print(line, file=sys.stderr)


def _fail(lines):
    _print_stderr(lines)
    return 2


def _write_stdout(text):
    """Escribe `text` a stdout como UTF-8 en Windows (evita UnicodeEncodeError
    bajo cp1252) y con el write normal en el resto de plataformas."""
    if sys.platform == "win32":
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            buffer.write(text.encode("utf-8"))
            buffer.flush()
            return
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
    sys.stdout.write(text)


def _account_add(argv):
    if len(argv) != 7:
        return _fail([
            "error: account add requiere ROOT, ACCOUNT_ID, PROVIDER, "
            "EMAIL y CREDENTIAL_REF",
            USAGE,
        ])
    try:
        account = create_email_account(argv[3], argv[4], argv[5], argv[6])
        save_email_account(argv[2], account)
    except (ValueError, RuntimeError):
        _print_stderr([
            "error: no se pudo guardar la cuenta "
            "(datos o almacenamiento invalidos)",
        ])
        return 1
    print("account saved: " + account["account_id"])
    return 0


def _account_list(argv):
    if len(argv) != 3:
        return _fail([
            "error: account list requiere exactamente ROOT",
            USAGE,
        ])
    try:
        records = load_email_accounts(argv[2])
    except (ValueError, RuntimeError):
        _print_stderr([
            "error: no se pudieron leer las cuentas (almacenamiento invalido)",
        ])
        return 1
    for record in records:
        print(json.dumps(
            {key: record[key] for key in _PUBLIC_KEYS},
            sort_keys=True,
        ))
    return 0


def _setup_cancel(message):
    _print_stderr([message])
    return 1


def _account_setup(argv):
    if len(argv) not in (3, 5) or (len(argv) == 5 and argv[3] != "--lang"):
        return _fail([
            "error: account setup requiere exactamente ROOT",
            USAGE,
        ])
    language = "es"
    if len(argv) == 5:
        try:
            language = normalize_language(argv[4])
        except ValueError:
            return _fail(["error: account setup acepta --lang es|en|pt", USAGE])
    text = _SETUP_TEXT[language]
    print(text["intro"])
    answers = []
    for prompt in text["prompts"]:
        print(prompt, end="")
        try:
            answer = input().strip()
        except (EOFError, KeyboardInterrupt):
            return _setup_cancel(text["cancel_eof"])
        if answer.lower() in ("cancelar", "cancel"):
            return _setup_cancel(text["cancel_user"])
        if not answer:
            return _setup_cancel(text["empty"])
        answers.append(answer)
    account_id, provider, email, env_name = answers
    if provider.lower() not in ("gmail", "outlook"):
        _print_stderr([text["provider"]])
        return 1
    if env_name[0] not in _SETUP_ENV_NAME_HEAD or any(
        char not in _SETUP_ENV_NAME_TAIL for char in env_name[1:]
    ):
        _print_stderr([text["env"]])
        return 1
    try:
        account = create_email_account(
            account_id, provider, email, "env://" + env_name
        )
        save_email_account(argv[2], account)
    except (ValueError, RuntimeError):
        _print_stderr([text["save"]])
        return 1
    print("account saved: " + account["account_id"])
    return 0


def _account_setup_gui(argv):
    if len(argv) != 3:
        return _fail([
            "error: account setup-gui requiere exactamente ROOT",
            USAGE,
        ])
    from src.email.gui_setup import run_account_setup_gui
    return run_account_setup_gui(argv[2])


def _run_account(argv):
    if len(argv) < 2 or argv[1] not in ("add", "setup", "setup-gui", "list", "remove"):
        return _fail([
            "error: account requiere 'add', 'setup', 'setup-gui', 'list' o 'remove'",
            USAGE,
            "  account setup ROOT  alta guiada interactiva",
            "  account setup ROOT --lang es|en|pt  asistente localizado",
            "  account setup-gui ROOT  formulario local seguro",
            "  account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF",
            "  account list ROOT",
            "  account remove ROOT ACCOUNT_ID CONFIRMAR DESVINCULAR",
        ])
    if argv[1] == "add":
        return _account_add(argv)
    if argv[1] == "setup":
        return _account_setup(argv)
    if argv[1] == "setup-gui":
        return _account_setup_gui(argv)
    if argv[1] == "remove":
        return _account_remove(argv)
    return _account_list(argv)


def _run_query(argv):
    if len(argv) not in (3, 5, 7):
        return _fail([
            "error: query requiere ROOT, INSTRUCTION y opciones --offset/--limit",
            USAGE,
        ])
    root, instruction = argv[1], argv[2]
    offset, limit = 0, None
    options = argv[3:]
    if len(options) % 2:
        return _fail(["error: query requiere pares --offset N y --limit N", USAGE])
    for index in range(0, len(options), 2):
        flag, raw = options[index:index + 2]
        if flag not in ("--offset", "--limit"):
            return _fail(["error: query solo acepta --offset N y --limit N", USAGE])
        try:
            value = int(raw)
        except ValueError:
            return _fail(["error: --offset/--limit requiere un entero", USAGE])
        if flag == "--offset":
            if value < 0:
                return _fail(["error: --offset debe ser >= 0", USAGE])
            offset = value
        else:
            if not 1 <= value <= LIMIT_MAX:
                return _fail(["error: --limit debe estar entre 1 y 100", USAGE])
            limit = value
    try:
        matches = query_email(root, instruction)
    except ValueError:
        _print_stderr([
            "error: la consulta es invalida (raiz inexistente o "
            "instruccion sin criterios validos)",
        ])
        return 2
    except Exception:
        _print_stderr(["error: la consulta fallo"])
        return 1
    for path in matches[offset:offset + limit if limit is not None else None]:
        print(path)
    return 0


def _run_search(argv):
    if len(argv) != 3:
        return _fail([
            "error: search requiere exactamente ROOT y QUERY",
            USAGE,
        ])
    try:
        matches = search_email_nodes(argv[1], argv[2])
    except Exception:
        _print_stderr([
            "error: la busqueda fallo (raiz invalida o query sin terminos)",
        ])
        return 1
    for path in matches:
        print(path)
    return 0


def _run_read(argv):
    if len(argv) != 3:
        return _fail([
            "error: read requiere exactamente ROOT y REL_PATH",
            USAGE,
        ])
    try:
        text = read_email_node(argv[1], argv[2])
    except ValueError:
        _print_stderr([
            "error: la lectura es invalida (raiz o ruta relativa insegura)",
        ])
        return 2
    except Exception:
        _print_stderr([
            "error: la lectura fallo (nodo inexistente o fallo de E/S)",
        ])
        return 1
    _write_stdout(text)
    return 0


def _run_draft(argv):
    if len(argv) != 6:
        return _fail([
            "error: draft requiere ROOT, ACCOUNT_ID, TO, SUBJECT y BODY",
            USAGE,
        ])
    root, account_id, to, subject, body = argv[1], argv[2], argv[3], argv[4], argv[5]
    try:
        draft = create_email_draft(account_id, to.split(","), subject, body)
        drafts_dir = os.path.join(root, "drafts")
        os.makedirs(drafts_dir, exist_ok=True)
        path = os.path.join(drafts_dir, draft["id"] + ".json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(draft, handle, sort_keys=True, indent=2, ensure_ascii=False)
            handle.write("\n")
    except (ValueError, OSError):
        _print_stderr(["error: no se pudo crear el borrador"])
        return 1
    print(json.dumps({"id": draft["id"], "path": path}, sort_keys=True))
    return 0


def _run_send(argv):
    if len(argv) != 5:
        return _fail([
            "error: send requiere ROOT, ACCOUNT_ID, DRAFT_ID y confirmacion",
            USAGE,
        ])
    root, account_id, draft_id = argv[1], argv[2], argv[3]
    if argv[4] != _CONFIRMATION_PHRASE:
        _print_stderr(["error: confirmacion explicita requerida para enviar"])
        return 1
    try:
        with open(
            os.path.join(root, "drafts", draft_id + ".json"),
            encoding="utf-8",
        ) as handle:
            draft = json.load(handle)
    except (OSError, ValueError):
        _print_stderr(["error: el borrador no se pudo leer"])
        return 1
    if not isinstance(draft, dict) or draft.get("account_id") != account_id:
        _print_stderr(["error: el borrador no corresponde a la cuenta"])
        return 1
    if any(draft.get(key) for key in _ATTACHMENT_KEYS):
        return _fail(["error: el borrador no es valido para el envio"])
    try:
        confirmed = confirm_email_draft(draft, argv[4])
    except Exception:
        _print_stderr(["error: la confirmacion del borrador fallo"])
        return 1
    # Puente status -> confirmed: confirm_email_draft marca status "confirmed"
    # pero no añade la clave booleana que smtp_send exige. Se construye una
    # copia nueva (sin mutar el draft ni el retorno original) con los mismos
    # campos y confirmed=True para el envio y el registro de contactos.
    deliverable = dict(confirmed)
    deliverable["confirmed"] = True
    try:
        accounts = load_email_accounts(root)
    except Exception:
        _print_stderr(["error: el store de cuentas es ilegible"])
        return 1
    account = next(
        (item for item in accounts if item.get("account_id") == account_id),
        None,
    )
    if account is None:
        _print_stderr(["error: cuenta no encontrada"])
        return 1
    try:
        servers = load_mail_server_config(root, account_id)
    except Exception:
        _print_stderr(["error: la configuracion de servidores es ilegible"])
        return 1
    try:
        secret = resolve_credential(account["credential_ref"])
    except Exception:
        _print_stderr(["error: credencial irresoluble"])
        return 1
    if servers is not None:
        host = servers["smtp_host"]
    else:
        host = account.get("smtp_host") or _SMTP_PROVIDER_HOSTS.get(account.get("provider"))
    if not host:
        _print_stderr(["error: provider sin host smtp por defecto"])
        return 1
    config = {
        "host": host,
        "port": servers["smtp_port"] if servers is not None else _DEFAULT_SMTP_PORT,
        "username": account["email"],
        "password": secret,
    }
    try:
        send_smtp_message(account, config, deliverable)
    except Exception:
        _print_stderr(["error: el envio fallo"])
        return 1
    # Post-envio: registro de contactos salientes. El SMTP ya pudo entregar el
    # mensaje; si el registro falla NO se reintentara el envio automaticamente
    # (reenviar duplicaria el correo; la libreta puede actualizarse por otra via).
    try:
        contacts = extract_outgoing_contacts(deliverable)
        store_email_contacts(root, contacts)
    except Exception:
        _print_stderr([
            "error: el registro de contactos post-envio fallo (el mensaje "
            "pudo haber sido enviado; no reintentar el envio automaticamente)",
        ])
        return 1
    print(json.dumps({"id": draft_id, "status": "sent"}, sort_keys=True))
    return 0


def _make_update_contacts(root):
    """Devuelve update_contacts(messages): fusiona, deduplica y almacena UNA vez."""
    seen = set()
    contacts = []

    def update_contacts(messages):
        for record in messages:
            for contact in extract_contacts(record):
                email = contact["email"].lower()
                if email in seen:
                    continue
                seen.add(email)
                contacts.append(contact)
        store_email_contacts(root, contacts)

    return update_contacts


def _run_contact(argv):
    if len(argv) < 2 or argv[1] not in ("list", "show", "find"):
        return _fail([
            "error: contact requiere el subcomando 'list', 'show' o 'find'",
            USAGE,
            "  contact list ROOT  lista la libreta de contactos",
        ])
    if argv[1] == "list" and len(argv) != 3:
        return _fail(["error: contact list requiere exactamente ROOT", USAGE])
    if argv[1] == "show" and len(argv) != 4:
        return _fail(["error: contact show requiere ROOT y EMAIL", USAGE])
    if argv[1] == "find" and len(argv) != 4:
        return _fail(["error: contact find requiere ROOT y TEXT", USAGE])
    try:
        contacts = load_email_contacts(argv[2])
    except (ValueError, RuntimeError):
        _print_stderr([
            "error: no se pudieron leer los contactos (almacenamiento invalido)",
        ])
        return 1
    if argv[1] == "show":
        email = argv[3].strip().lower()
        contact = next((item for item in contacts if item["email"] == email), None)
        if contact is None:
            _print_stderr(["error: contacto no encontrado"])
            return 1
        print(json.dumps(contact, sort_keys=True))
        return 0
    if argv[1] == "find":
        query = argv[3].strip().casefold()
        if not query:
            return _fail(["error: contact find requiere TEXT no vacio", USAGE])
        for contact in contacts:
            if query in contact["name"].casefold() or query in contact["email"]:
                print(json.dumps(contact, sort_keys=True))
        return 0
    for record in contacts:
        print(json.dumps(
            {"name": record["name"], "email": record["email"]},
            sort_keys=True,
        ))
    return 0


def _sync_limit(raw):
    """Devuelve el limite como int 1..100, o None si no es valido."""
    try:
        limit = int(raw)
    except ValueError:
        return None
    if not LIMIT_MIN <= limit <= LIMIT_MAX:
        return None
    return limit


def _pop_sync_limit(argv):
    """Extrae los pares `--limit N` de argv; devuelve (resto, limit o None).

    Con `--limit` sin valor o con un valor fuera de 1..100 devuelve
    (None, None) para que el llamador responda con error de argumentos.
    """
    rest = list(argv)
    limit = None
    while "--limit" in rest:
        index = rest.index("--limit")
        if index + 1 >= len(rest):
            return None, None
        value = _sync_limit(rest[index + 1])
        if value is None:
            return None, None
        limit = value
        del rest[index:index + 2]
    return rest, limit


def _pop_sync_attachments(argv):
    """Extrae `--attachments CONFIRMAR EXTRACCION` de argv.

    Devuelve (resto, True) si la frase literal es exacta, (resto, False) si la
    opcion no aparece y (None, None) si `--attachments` no va seguida de la
    frase exacta, para que el llamador aborte ANTES de conectar.
    """
    rest = list(argv)
    authorized = False
    while "--attachments" in rest:
        index = rest.index("--attachments")
        if " ".join(rest[index + 1:index + 3]) != _EXTRACTION_CONFIRMATION:
            return None, None
        del rest[index:index + 3]
        authorized = True
    return rest, authorized


def _sync_attachment_budget():
    """Presupuesto total en bytes para `sync --attachments` (default 100 MB).

    Configurable con la env var `SYNC_ATTACHMENT_BUDGET_MB` (entero >= 1);
    un valor invalido devuelve None para que el llamador falle antes de conectar.
    """
    raw = os.environ.get(_SYNC_ATTACHMENT_BUDGET_ENV)
    if raw is None:
        return _SYNC_ATTACHMENT_BUDGET_MB_DEFAULT * 1024 * 1024
    try:
        megabytes = int(raw)
    except ValueError:
        return None
    if megabytes < 1:
        return None
    return megabytes * 1024 * 1024


def _run_sync(argv):
    rest, limit = _pop_sync_limit(argv)
    if rest is None:
        return _fail([
            "error: sync requiere un valor entero para --limit entre 1 y 100",
            USAGE,
            SYNC_USAGE,
        ])
    rest, attachments_mode = _pop_sync_attachments(rest)
    if rest is None:
        _print_stderr([
            "error: confirmacion explicita requerida para extraer adjuntos "
            "(frase literal CONFIRMAR EXTRACCION)",
        ])
        return 1
    budget = None
    if attachments_mode:
        budget = _sync_attachment_budget()
        if budget is None:
            return _fail([
                "error: la env var SYNC_ATTACHMENT_BUDGET_MB debe ser un "
                "entero >= 1",
                USAGE,
                SYNC_USAGE,
            ])
    unread = "--unread" in rest
    rest = [item for item in rest if item != "--unread"]
    if len(rest) not in (3, 4):
        return _fail([
            "error: sync requiere ROOT y ACCOUNT_ID y HOST opcional "
            "(--limit N opcional)",
            USAGE,
            SYNC_USAGE,
        ])
    root, account_id = rest[1], rest[2]
    try:
        accounts = load_email_accounts(root)
    except Exception:
        _print_stderr(["error: el store de cuentas es ilegible"])
        return 1
    account = next(
        (item for item in accounts if item.get("account_id") == account_id),
        None,
    )
    if account is None:
        _print_stderr(["error: cuenta no encontrada"])
        return 1
    try:
        servers = load_mail_server_config(root, account_id)
    except Exception:
        _print_stderr(["error: la configuracion de servidores es ilegible"])
        return 1
    try:
        secret = resolve_credential(account["credential_ref"])
    except Exception:
        _print_stderr(["error: credencial irresoluble"])
        return 1
    if len(rest) == 4:
        host = rest[3]
    elif servers is not None:
        host = servers["imap_host"]
    else:
        host = _PROVIDER_HOSTS.get(account.get("provider"))
    if not host:
        _print_stderr(["error: provider sin host por defecto"])
        return 1
    try:
        cursor = load_sync_cursor(root, account_id)
    except (ValueError, RuntimeError):
        _print_stderr(["error: el cursor de sincronizacion es ilegible"])
        return 1
    config = {
        "host": host,
        "username": account["email"],
        "password": secret,
        "since_uid": cursor,
    }
    if limit is not None:
        config["limit"] = limit
    if unread:
        config["unread"] = True
    if servers is not None:
        config["port"] = servers["imap_port"]
    fetched = []

    # Mailbox efectivo de la sesion de sync: config["mailbox"] si existiera,
    # o INBOX; se estampa en cada record antes de persistir para que el nodo
    # quede re-descargable por UID (sin credenciales).
    mailbox = config.get("mailbox") or DEFAULT_MAILBOX

    def fetch(_account):
        nonlocal fetched
        if attachments_mode:
            # Opt-in: el RFC822 ya descargado viaja en el record para extraer
            # adjuntos sin re-fetch. La ruta por defecto no cambia la firma.
            fetched = fetch_imap_messages(_account, config, include_raw=True)
        else:
            fetched = fetch_imap_messages(_account, config)
        for record in fetched:
            record["mailbox"] = mailbox
        return fetched

    attachment_stats = {"stored": 0, "skipped": 0, "errors": 0}

    def persist(record):
        rel_path = "store/emails/" + record["raw_sha256"] + ".md"
        if attachments_mode:
            # Extraccion autorizada: reutiliza el RFC822 ya descargado en esta
            # sync (sin re-fetch). Cada fallo por adjunto se degrada a
            # `skipped` en el frontmatter: nunca aborta ni rompe el cursor.
            entries, stats = store_record_attachments(root, record, budget)
            attachment_stats["stored"] += stats["stored"]
            attachment_stats["skipped"] += stats["skipped"]
            attachment_stats["errors"] += stats["errors"]
            prepared = dict(record)
            prepared["attachments"] = entries
            prepared.pop("raw_message", None)
            record = prepared
        path = persist_email_okf_at(record, root, rel_path)
        persist_conversation_index(root, record, rel_path)
        persist_topic_index(root, record, rel_path)
        return path

    try:
        summary = sync_email_account(account, fetch, persist, _make_update_contacts(root))
    except Exception:
        _print_stderr(["error: la sincronizacion fallo (cuenta o almacen invalido)"])
        return 1
    if attachments_mode:
        summary["attachments_stored"] = attachment_stats["stored"]
        summary["attachments_skipped"] = attachment_stats["skipped"]
        summary["attachments_errors"] = attachment_stats["errors"]
    if fetched:
        try:
            save_sync_cursor(
                root, account_id, max(record["imap_uid"] for record in fetched)
            )
        except (ValueError, RuntimeError):
            _print_stderr(["error: el cursor de sincronizacion no se pudo guardar"])
            return 1
        try:
            notify_new_records(root, fetched)
        except Exception:
            _print_stderr(["error: no se pudieron emitir notificaciones"])
            return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


def _account_remove(argv):
    """Desvincular una cuenta tras la confirmacion literal CONFIRMAR DESVINCULAR."""
    if len(argv) < 5:
        return _fail(["error: account remove requiere ROOT, ACCOUNT_ID y confirmacion", USAGE])
    if " ".join(argv[4:]) != _UNLINK_CONFIRMATION:
        _print_stderr(["error: confirmacion explicita requerida para desvincular"])
        return 1
    try:
        removed = unlink_email_account(argv[2], argv[3])
    except LookupError:
        _print_stderr(["error: cuenta no encontrada"])
        return 1
    except (ValueError, RuntimeError, OSError):
        _print_stderr(["error: no se pudo desvincular la cuenta"])
        return 1
    print(json.dumps({"account_id": removed["account_id"], "status": "unlinked"}, sort_keys=True))
    return 0


def _pop_watch_option(argv, name, default=None, minimum=None):
    rest = list(argv)
    value = default
    while name in rest:
        index = rest.index(name)
        if index + 1 >= len(rest):
            return None, None
        try:
            candidate = int(rest[index + 1])
        except ValueError:
            return None, None
        if minimum is not None and candidate < minimum:
            return None, None
        value = candidate
        del rest[index:index + 2]
    return rest, value


def _run_watch(argv):
    rest, every = _pop_watch_option(argv, "--every", 300, 30)
    if rest is None:
        return _fail(["error: watch requiere --every entero >= 30", USAGE, WATCH_USAGE])
    rest, limit = _pop_watch_option(rest, "--limit", None, 1)
    if rest is None or (limit is not None and limit > LIMIT_MAX):
        return _fail(["error: watch requiere --limit entre 1 y 100", USAGE, WATCH_USAGE])
    unread = "--unread" in rest
    rest = [item for item in rest if item != "--unread"]
    if len(rest) != 3:
        return _fail(["error: watch requiere ROOT y ACCOUNT_ID", USAGE, WATCH_USAGE])
    sync_args = ["sync", rest[1], rest[2]]
    if limit is not None:
        sync_args.extend(["--limit", str(limit)])
    if unread:
        sync_args.append("--unread")
    try:
        while True:
            result = _run_sync(sync_args)
            if result != 0:
                return result
            time.sleep(every)
    except KeyboardInterrupt:
        print("watch stopped")
        return 0


def _run_notification(argv):
    if len(argv) < 2 or argv[1] not in ("add", "list", "show", "enable", "disable", "delete"):
        return _fail(["error: notification requiere add, list, show, enable, disable o delete", USAGE])
    action = argv[1]
    try:
        if action == "list":
            if len(argv) != 3:
                return _fail(["error: notification list requiere ROOT", USAGE])
            for rule in list_notification_rules(argv[2]):
                print(json.dumps(rule, sort_keys=True))
            return 0
        if action == "show":
            if len(argv) != 4:
                return _fail(["error: notification show requiere ROOT y NAME", USAGE])
            rule = next(
                (item for item in list_notification_rules(argv[2]) if item.get("name") == argv[3]),
                None,
            )
            if rule is None:
                _print_stderr(["error: regla de notificacion no encontrada"])
                return 1
            print(json.dumps(rule, sort_keys=True))
            return 0
        if action == "delete":
            if len(argv) != 6 or " ".join(argv[4:]) != _NOTIFICATION_DELETE_CONFIRMATION:
                return _fail([
                    "error: notification delete requiere ROOT, NAME y CONFIRMAR REGLA",
                    USAGE,
                ])
            print(json.dumps({"deleted": delete_notification_rule(argv[2], argv[3])}))
            return 0
        if action in ("enable", "disable"):
            if len(argv) != 6 or " ".join(argv[4:]) != _NOTIFICATION_DELETE_CONFIRMATION:
                return _fail([
                    f"error: notification {action} requiere ROOT, NAME y CONFIRMAR REGLA",
                    USAGE,
                ])
            set_notification_rule_enabled(argv[2], argv[3], action == "enable")
            print(json.dumps({"enabled": action == "enable", "name": argv[3]}, sort_keys=True))
            return 0
        if len(argv) not in (5, 7):
            return _fail([
                "error: notification add requiere ROOT NAME QUERY y, al "
                "reemplazar, CONFIRMAR REGLA",
                USAGE,
            ])
        confirmation = " ".join(argv[5:]) if len(argv) == 7 else None
        existing = next(
            (rule for rule in list_notification_rules(argv[2]) if rule.get("name") == argv[3]),
            None,
        )
        if existing is not None and confirmation != _NOTIFICATION_DELETE_CONFIRMATION:
            return _fail([
                "error: la regla ya existe; muestra su consulta y solicita "
                "CONFIRMAR REGLA antes de reemplazarla",
                USAGE,
            ])
        if len(argv) == 7 and confirmation != _NOTIFICATION_DELETE_CONFIRMATION:
            return _fail(["error: confirmacion requerida: CONFIRMAR REGLA", USAGE])
        save_notification_rule(argv[2], argv[3], argv[4])
        print(json.dumps({"saved": argv[3]}, sort_keys=True))
        return 0
    except (LookupError, ValueError, RuntimeError, OSError):
        _print_stderr(["error: no se pudo modificar la regla de notificacion"])
        return 1


def _run_startup(argv):
    if len(argv) < 4 or argv[1] not in ("install", "status", "remove"):
        return _fail(["error: startup requiere install, status o remove y ROOT ACCOUNT_ID", USAGE])
    action, root, account_id = argv[1], argv[2], argv[3]
    try:
        if action == "status":
            print(json.dumps({"enabled": startup_status(account_id)}, sort_keys=True))
            return 0
        if action == "remove":
            print(json.dumps({"removed": remove_startup(account_id)}, sort_keys=True))
            return 0
        interval, limit = 300, 50
        unread = "--unread" in argv[4:]
        options = [value for value in argv[4:] if value != "--unread"]
        if options:
            if len(options) not in (2, 4) or options[0] != "--every":
                return _fail(["error: startup install acepta --every N, --limit N y --unread", USAGE])
            interval = int(options[1])
            if len(options) == 4 and options[2] == "--limit":
                limit = int(options[3])
            elif len(options) == 4:
                return _fail(["error: startup install acepta --every N, --limit N y --unread", USAGE])
        path = install_startup(root, account_id, interval, limit, unread)
        print(json.dumps({"installed": path}, sort_keys=True))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError):
        _print_stderr(["error: no se pudo modificar el inicio automatico"])
        return 1


_MESSAGE_ACTION_USAGE = (
    "  message delete ROOT REL_PATH  mueve un nodo .md a root/.trash",
    "  message restore ROOT TRASH_REL_PATH  devuelve un nodo desde .trash",
    "  message trash ROOT  lista los manifiestos de root/.trash",
    "  message purge ROOT TRASH_REL_PATH CONFIRMAR BORRADO PERMANENTE",
    "  message remote-delete ROOT ACCOUNT_ID UID TRASH_MAILBOX  "
    "mueve el mensaje remoto a Trash (COPY + Deleted, sin expunge)",
    "  message remote-restore ROOT ACCOUNT_ID UID TRASH_MAILBOX ORIGINAL_MAILBOX  "
    "devuelve el mensaje desde Trash",
    "  message remote-purge ROOT ACCOUNT_ID UID MAILBOX "
    "CONFIRMAR BORRADO PERMANENTE  expurga solo con UIDPLUS",
)


def _parse_uid(raw):
    """UID como int >= 1 desde argv; None si no es valido (sin signos ni espacios)."""
    if not isinstance(raw, str) or not raw.isdigit() or not int(raw) >= 1:
        return None
    return int(raw)


def _run_remote_message(argv, action):
    """Capa fina sobre ImapDeletionProvider: cuenta/config/UID resueltos del store."""
    if action == "remote-restore":
        if len(argv) != 7:
            return _fail([
                "error: message remote-restore requiere ROOT, ACCOUNT_ID, "
                "UID, TRASH_MAILBOX y ORIGINAL_MAILBOX",
                USAGE,
            ])
        root, account_id, raw_uid, mailbox, original = argv[2:7]
    elif action == "remote-delete":
        if len(argv) != 6:
            return _fail([
                "error: message remote-delete requiere ROOT, ACCOUNT_ID, "
                "UID y TRASH_MAILBOX",
                USAGE,
            ])
        root, account_id, raw_uid, mailbox = argv[2:6]
        original = None
    else:
        if len(argv) < 7:
            return _fail([
                "error: message remote-purge requiere ROOT, ACCOUNT_ID, UID, "
                "MAILBOX y la confirmacion literal CONFIRMAR BORRADO PERMANENTE",
                USAGE,
            ])
        root, account_id, raw_uid, mailbox = argv[2], argv[3], argv[4], argv[5]
        if " ".join(argv[6:]) != _PURGE_CONFIRMATION:
            _print_stderr([
                "error: confirmacion explicita requerida para el borrado permanente",
            ])
            return 1
        original = None
    uid = _parse_uid(raw_uid)
    if uid is None:
        return _fail(["error: UID debe ser un entero positivo", USAGE])
    try:
        accounts = load_email_accounts(root)
    except Exception:
        _print_stderr(["error: el store de cuentas es ilegible"])
        return 1
    account = next(
        (item for item in accounts if item.get("account_id") == account_id),
        None,
    )
    if account is None:
        _print_stderr(["error: cuenta no encontrada"])
        return 1
    try:
        servers = load_mail_server_config(root, account_id)
    except Exception:
        _print_stderr(["error: la configuracion de servidores es ilegible"])
        return 1
    try:
        secret = resolve_credential(account["credential_ref"])
    except Exception:
        _print_stderr(["error: credencial irresoluble"])
        return 1
    host = (
        servers["imap_host"]
        if servers is not None
        else _PROVIDER_HOSTS.get(account.get("provider"))
    )
    if not host:
        _print_stderr(["error: provider sin host por defecto"])
        return 1
    config = {"host": host, "username": account["email"], "password": secret}
    if servers is not None:
        config["port"] = servers["imap_port"]
    provider = ImapDeletionProvider()
    try:
        if action == "remote-delete":
            # TRASH_MAILBOX va como parametro explicito; el mailbox origen lo
            # resuelve el provider (config["mailbox"] si existiera, o INBOX).
            receipt = provider.soft_delete(account, config, uid, mailbox)
        elif action == "remote-restore":
            receipt = provider.restore(account, config, mailbox, uid, original)
        else:
            receipt = provider.permanent_delete(
                account, config, mailbox, uid, _PURGE_CONFIRMATION
            )
    except ValueError:
        _print_stderr([
            "error: la operacion remota fallo (cuenta o datos invalidos)",
        ])
        return 1
    except Exception:
        _print_stderr(["error: la operacion IMAP fallo (sin cambios seguros)"])
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


def _run_message(argv):
    """Capa fina de presentacion sobre deletion (local .trash y remoto IMAP)."""
    if len(argv) < 2 or argv[1] not in (
        "delete", "restore", "trash", "purge",
        "remote-delete", "remote-restore", "remote-purge",
    ):
        return _fail([
            "error: message requiere 'delete', 'restore', 'trash', 'purge', "
            "'remote-delete', 'remote-restore' o 'remote-purge'",
            USAGE,
        ] + list(_MESSAGE_ACTION_USAGE))
    action = argv[1]
    if action in ("remote-delete", "remote-restore", "remote-purge"):
        return _run_remote_message(argv, action)
    if action == "trash":
        if len(argv) != 3:
            return _fail(["error: message trash requiere exactamente ROOT", USAGE])
        try:
            manifests = list_trash(argv[2])
        except (ValueError, RuntimeError, OSError):
            _print_stderr(["error: la papelera no se pudo leer (raiz invalida)"])
            return 1
        for manifest in manifests:
            print(json.dumps(manifest, sort_keys=True))
        return 0
    if action == "delete":
        if len(argv) != 4:
            return _fail(["error: message delete requiere ROOT y REL_PATH", USAGE])
        try:
            manifest = soft_delete(argv[2], argv[3])
        except ValueError:
            _print_stderr([
                "error: rel_path invalido o el elemento ya esta en .trash",
            ])
            return 1
        except (FileNotFoundError, OSError):
            _print_stderr(["error: el nodo no existe"])
            return 1
        print(json.dumps(manifest, sort_keys=True))
        return 0
    if action == "restore":
        if len(argv) != 4:
            return _fail([
                "error: message restore requiere ROOT y TRASH_REL_PATH",
                USAGE,
            ])
        try:
            manifest = restore(argv[2], argv[3])
        except ValueError:
            _print_stderr([
                "error: la restauracion fallo (ruta fuera de .trash, "
                "manifiesto invalido o destino ya existe)",
            ])
            return 1
        except (FileNotFoundError, OSError):
            _print_stderr(["error: el elemento o su manifiesto no existe en .trash"])
            return 1
        print(json.dumps(manifest, sort_keys=True))
        return 0
    if len(argv) < 5:
        return _fail([
            "error: message purge requiere ROOT, TRASH_REL_PATH y la "
            "confirmacion literal CONFIRMAR BORRADO PERMANENTE",
            USAGE,
        ])
    if " ".join(argv[4:]) != _PURGE_CONFIRMATION:
        _print_stderr([
            "error: confirmacion explicita requerida para el borrado permanente",
        ])
        return 1
    try:
        removed = purge(argv[2], argv[3], _PURGE_CONFIRMATION)
    except ValueError:
        _print_stderr([
            "error: la ruta no es un elemento valido dentro de .trash",
        ])
        return 1
    except (FileNotFoundError, OSError):
        _print_stderr(["error: el elemento no esta en .trash"])
        return 1
    print(json.dumps(removed, sort_keys=True))
    return 0


def _resolve_dest_path(root, dest):
    """DEST como ruta segura bajo ROOT (misma politica anti-traversal de nodos)."""
    if not isinstance(dest, str) or not dest.strip():
        raise ValueError("dest debe ser str no vacio")
    portable = dest.replace("\\", "/")
    if (
        portable.startswith("~")
        or Path(portable).is_absolute()
        or (len(portable) >= 3 and portable[1:3] == ":/")
    ):
        raise ValueError("dest insegura (absoluta, ~ o unidad): " + repr(dest))
    if any(part in ("", ".", "..") for part in portable.split("/")):
        raise ValueError("dest con componente vacio, . o ..: " + repr(dest))
    root_path = Path(root).resolve()
    target = (root_path / Path(portable)).resolve()
    if target != root_path and root_path not in target.parents:
        raise ValueError("dest resuelve fuera de la raiz: " + repr(dest))
    return target


def _run_attachment_download(argv):
    """Extraccion autorizada: re-fetch RFC822 por UID, blob content-addressed y copia.

    Valida la frase literal y el nodo ANTES de conectar o escribir. Resuelve
    account_id/imap_uid/mailbox del nodo y cuenta/servidor/credencial desde
    los stores; los nodos legacy (sin imap_uid o account_id) se rechazan.
    """
    if len(argv) < 7:
        return _fail([
            "error: attachment download requiere ROOT, REL_PATH, INDEX, DEST "
            "y la confirmacion literal CONFIRMAR EXTRACCION",
            USAGE,
        ])
    root, rel_path, raw_index, dest = argv[2:6]
    if " ".join(argv[6:]) != _EXTRACTION_CONFIRMATION:
        _print_stderr([
            "error: confirmacion explicita requerida para extraer adjuntos",
        ])
        return 1
    try:
        index = int(raw_index)
    except ValueError:
        index = -1
    if index < 0:
        return _fail(["error: INDEX debe ser un entero >= 0", USAGE])
    try:
        node_text = read_email_node(root, rel_path)
    except ValueError:
        _print_stderr([
            "error: la lectura es invalida (raiz o ruta relativa insegura)",
        ])
        return 2
    except Exception:
        _print_stderr(["error: el nodo no existe o no se pudo leer"])
        return 1
    try:
        dest_path = _resolve_dest_path(root, dest)
    except ValueError:
        _print_stderr([
            "error: DEST insegura (debe ser relativa y quedar bajo ROOT, "
            "sin traversal)",
        ])
        return 2
    try:
        entry = next(
            (
                item
                for item in read_attachment_entries(node_text)
                if item["part_index"] == index
            ),
            None,
        )
    except Exception:
        _print_stderr(["error: el frontmatter del nodo es ilegible"])
        return 1
    if entry is None or not entry["sha256"]:
        _print_stderr(["error: adjunto no encontrado en el nodo (INDEX invalido)"])
        return 1
    if legacy_attachment_block(node_text):
        _print_stderr([
            "error: nodo legacy con formato antiguo de adjuntos (hashes sueltos): "
            "no se puede asociar stored sin reescribir el formato "
            "(re-sincronizar para reintentar)",
        ])
        return 1
    account_id, imap_uid, mailbox = read_download_target(node_text)
    if not account_id or imap_uid is None:
        _print_stderr([
            "error: nodo legacy sin imap_uid o account_id: no es descargable "
            "(re-sincronizar para reintentar)",
        ])
        return 1
    if not is_type_allowed(entry["content_type"], entry["filename"]):
        _print_stderr([
            "error: tipo de adjunto no permitido por defecto (solo metadatos)",
        ])
        return 1
    if int(entry["size"] or 0) > MAX_ATTACHMENT_BYTES:
        _print_stderr(["error: el adjunto excede el limite de tamano"])
        return 1
    try:
        accounts = load_email_accounts(root)
    except Exception:
        _print_stderr(["error: el store de cuentas es ilegible"])
        return 1
    account = next(
        (item for item in accounts if item.get("account_id") == account_id),
        None,
    )
    if account is None:
        _print_stderr(["error: cuenta no encontrada"])
        return 1
    try:
        servers = load_mail_server_config(root, account_id)
    except Exception:
        _print_stderr(["error: la configuracion de servidores es ilegible"])
        return 1
    try:
        secret = resolve_credential(account["credential_ref"])
    except Exception:
        _print_stderr(["error: credencial irresoluble"])
        return 1
    host = (
        servers["imap_host"]
        if servers is not None
        else _PROVIDER_HOSTS.get(account.get("provider"))
    )
    if not host:
        _print_stderr(["error: provider sin host por defecto"])
        return 1
    config = {"host": host, "username": account["email"], "password": secret}
    if servers is not None:
        config["port"] = servers["imap_port"]
    if mailbox:
        config["mailbox"] = mailbox
    try:
        raw = fetch_raw_message_by_uid(account, config, imap_uid)
    except Exception:
        _print_stderr(["error: la descarga fallo (servidor o credencial invalidos)"])
        return 1
    try:
        extracted = extract_attachment_bytes(raw, index)
    except Exception:
        _print_stderr(["error: el mensaje remoto no se pudo interpretar"])
        return 1
    if extracted is None:
        _print_stderr(["error: adjunto no encontrado en el mensaje remoto"])
        return 1
    content, filename, content_type = extracted
    try:
        stored = store_attachment_bytes(
            root,
            entry["sha256"],
            content,
            {"filename": filename, "content_type": content_type, "part_index": index},
            authorize=True,
        )
    except AttachmentError as exc:
        _print_stderr([
            "error: " + exc.code + " (el adjunto no se pudo verificar o escribir)",
        ])
        return 1
    except Exception:
        _print_stderr(["error: el adjunto no se pudo almacenar"])
        return 1
    if not stored.get("stored"):
        _print_stderr([
            "error: extraccion omitida (" + str(stored.get("skipped") or "motivo") + ")",
        ])
        return 1
    try:
        payload = blob_path(root, entry["sha256"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise OSError("blob no coincide con el sha256 declarado")
        if dest_path.is_dir():
            raise OSError("el destino es un directorio")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest_path.with_name(dest_path.name + ".tmp")
        tmp.write_bytes(payload)
        os.replace(tmp, dest_path)
        if hashlib.sha256(dest_path.read_bytes()).hexdigest() != entry["sha256"]:
            raise OSError("copia en destino no coincide con el sha256 declarado")
    except Exception:
        _print_stderr(["error: la copia al destino fallo (hash o E/S invalidos)"])
        return 1
    try:
        updated = mark_attachment_stored(node_text, index)
        if updated != node_text:
            write_node_text_atomic(root, rel_path, updated)
    except Exception:
        # La asociacion fallo: el nodo queda intacto (escritura atomica) y la
        # copia en DEST se retira para no reportar un exito sin asociacion.
        try:
            if dest_path.exists() and dest_path.read_bytes() == payload:
                dest_path.unlink()
        except OSError:
            pass
        _print_stderr([
            "error: la asociacion stored en el nodo fallo (nodo intacto, "
            "copia en DEST retirada)",
        ])
        return 1
    print(json.dumps(
        {
            "sha256": entry["sha256"],
            "sha256_short": entry["sha256"][:12],
            "size": len(payload),
            "blob": str(stored.get("path") or ""),
            "dest": str(dest_path.relative_to(Path(root).resolve())).replace("\\", "/"),
            "display": sanitize_display_name(entry["filename"], index),
            "idempotent": bool(stored.get("idempotent")),
        },
        sort_keys=True,
    ))
    return 0


def _run_attachment_gc(argv):
    """GC de blobs: listado en seco sin borrar; borrado solo con frase literal.

    `attachment gc ROOT` lista candidatos (JSON, exit 0, cero mutaciones).
    `attachment gc ROOT CONFIRMAR BORRADO ADJUNTOS` valida la frase ANTES de
    mutar y elimina blobs (y su .meta) sin referencia; un blob corrupto o no
    reconocido nunca se borra y ante el primer fallo de E/S se detiene todo.
    La salida lista candidatos y eliminados; sin rutas absolutas ni secretos.
    """
    if len(argv) not in (3, 6):
        return _fail([
            "error: attachment gc requiere ROOT (listado en seco) o ROOT y la "
            "confirmacion literal " + GC_CONFIRMATION,
            USAGE,
        ])
    root = argv[2]
    execute = len(argv) == 6
    if execute and " ".join(argv[3:]) != GC_CONFIRMATION:
        _print_stderr([
            "error: confirmacion literal requerida para borrar blobs sin referencia",
        ])
        return 1
    try:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise ValueError("root no existe o no es directorio")
    except Exception:
        _print_stderr(["error: ROOT no existe o no es un directorio"])
        return 2
    try:
        result = gc_execute(root, GC_CONFIRMATION) if execute else gc_scan(root)
    except AttachmentError:
        _print_stderr([
            "error: el escaneo aborto (store ausente o nodo ilegible): "
            "no se borro nada",
        ])
        return 1
    except (OSError, ValueError):
        _print_stderr(["error: el escaneo fallo (E/S invalida): no se borro nada"])
        return 1
    payload = {
        "mode": "executed" if execute else "dry-run",
        "nodes_scanned": result["nodes_scanned"],
        "referenced_count": result["referenced_count"],
        "candidates": result["candidates"],
        "corrupt": result["corrupt"],
        "unrecognized": result["unrecognized"],
        "deleted": result.get("deleted", []),
        "failed": result.get("failed", []),
    }
    print(json.dumps(payload, sort_keys=True))
    return 1 if payload["failed"] else 0


def _run_attachment(argv):
    """Capa fina de presentacion sobre attachments (metadatos y descarga)."""
    if len(argv) < 2 or argv[1] not in ("list", "download", "gc"):
        return _fail([
            "error: attachment requiere 'list', 'download' o 'gc'",
            USAGE,
        ])
    if argv[1] == "download":
        return _run_attachment_download(argv)
    if argv[1] == "gc":
        return _run_attachment_gc(argv)
    if len(argv) != 4:
        return _fail(["error: attachment list requiere ROOT y REL_PATH", USAGE])
    try:
        rows = list_node_attachments(argv[2], argv[3])
    except ValueError:
        _print_stderr([
            "error: la lectura es invalida (raiz o ruta relativa insegura)",
        ])
        return 2
    except Exception:
        _print_stderr([
            "error: la lista de adjuntos fallo (nodo inexistente o fallo de E/S)",
        ])
        return 1
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    return 0


def _run_onboard(argv):
    """Diagnostica y dirige el primer uso al formulario adecuado."""
    if len(argv) < 2 or len(argv) > 5:
        return _fail(["error: onboard requiere ROOT y acepta --gui, --terminal o --lang es|en|pt", USAGE])
    root = argv[1]
    requested_mode = None
    requested_language = None
    options = argv[2:]
    while options:
        option = options.pop(0)
        if option in ("--gui", "--terminal") and requested_mode is None:
            requested_mode = option
        elif option == "--lang" and requested_language is None and options:
            requested_language = options.pop(0)
        else:
            return _fail(["error: onboard requiere ROOT y acepta --gui, --terminal o --lang es|en|pt", USAGE])
    if requested_language is not None:
        try:
            language = normalize_language(requested_language)
            save_language(root, language)
        except (OSError, ValueError):
            return _fail(["error: onboard acepta --lang es|en|pt", USAGE])
    else:
        language = load_language(root)
    try:
        before_ids = {item["account_id"] for item in load_email_accounts(root)}
    except (ValueError, RuntimeError):
        before_ids = set()
    result = run_diagnostics(root)
    if result["status"] != "ready":
        next_steps = {
            "es": "Corrige los checks marcados como error y vuelve a ejecutar doctor",
            "en": "Fix the checks marked as errors and run doctor again",
            "pt": "Corrija as verificações marcadas como erro e execute doctor novamente",
        }
        print(json.dumps({"status": result["status"], "checks": result["checks"], "next": next_steps[language], "action": "email-agent doctor --fix", "language": language}, sort_keys=True))
        return 1
    gui_available = any(item["name"] == "gui" and item["status"] == "ok" for item in result["checks"])
    if requested_mode == "--gui" and not gui_available:
        _print_stderr(["onboard: el formulario grafico no esta disponible; usa --terminal"])
        return 1
    use_gui = requested_mode == "--gui" or (requested_mode is None and gui_available)
    setup_argv = ["account", "setup", root]
    if not use_gui and requested_language is not None:
        setup_argv += ["--lang", language]
    code = _account_setup_gui(["account", "setup-gui", root]) if use_gui else _account_setup(setup_argv)
    if code != 0:
        messages = {
            "es": "onboard: configuracion cancelada o incompleta; puedes volver a ejecutar 'email-agent onboard ROOT'",
            "en": "onboard: setup was cancelled or incomplete; you can run 'email-agent onboard ROOT' again",
            "pt": "onboard: a configuracao foi cancelada ou ficou incompleta; voce pode executar 'email-agent onboard ROOT' novamente",
        }
        _print_stderr([messages[language]])
        return code
    try:
        accounts = load_email_accounts(root)
    except (ValueError, RuntimeError):
        accounts = []
    candidates = [item for item in accounts if item["account_id"] not in before_ids]
    account = candidates[-1] if candidates else (accounts[-1] if accounts else None)
    public_account = None if account is None else {
        "account_id": account["account_id"],
        "provider": account["provider"],
        "email": account["email"],
    }
    account_id = public_account["account_id"] if public_account else "ACCOUNT_ID"
    next_steps = {
        "es": "Puedes sincronizar ahora con: email-agent sync ROOT " + account_id,
        "en": "You can sync now with: email-agent sync ROOT " + account_id,
        "pt": "Voce pode sincronizar agora com: email-agent sync ROOT " + account_id,
    }
    print(json.dumps({"status": "configured", "language": language, "account": public_account, "next": next_steps[language]}, sort_keys=True))
    return code


def cli_main(argv: list) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        print("  query ROOT INSTRUCTION  consulta el store local con query_email")
        print("  account setup ROOT  alta guiada interactiva")
        print("  account setup ROOT --lang es|en|pt  asistente localizado")
        print("  account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF")
        print("  account setup-gui ROOT  formulario local seguro")
        print("  account list ROOT")
        print("  contact list ROOT  lista la libreta de contactos")
        print("  search ROOT QUERY  busca nodos .md que contengan QUERY")
        print("  read ROOT REL_PATH  imprime el texto integro de un nodo .md")
        print("  attachment list ROOT REL_PATH  lista los adjuntos de un nodo .md")
        print(
            "  attachment download ROOT REL_PATH INDEX DEST CONFIRMAR EXTRACCION"
            "  extrae un adjunto (requiere confirmacion literal)"
        )
        print(
            "  attachment gc ROOT  lista en seco los blobs sin referencia (JSON, "
            "sin borrar)"
        )
        print(
            "  attachment gc ROOT CONFIRMAR BORRADO ADJUNTOS  elimina blobs (y "
            ".meta) sin referencia (requiere confirmacion literal)"
        )
        for line in _MESSAGE_ACTION_USAGE:
            print(line)
        print(SYNC_USAGE)
        print(WATCH_USAGE)
        print("  notification add ROOT NAME QUERY  crea una regla local")
        print("  notification list ROOT  lista reglas")
        print("  notification delete ROOT NAME  elimina una regla")
        print("  startup install|status|remove ROOT ACCOUNT_ID  inicio automatico")
        print("  doctor [ROOT] [--fix] [--lang es|en|pt] [--format json|text] [--report FILE]  diagnóstico seguro")
        print("  language set ROOT es|en|pt  guarda la preferencia local")
        print("  language get ROOT  muestra la preferencia efectiva")
        print("  onboard ROOT [--gui|--terminal] [--lang es|en|pt]  revisa requisitos y abre el flujo de primer uso")
        print("  draft ROOT ACCOUNT_ID TO SUBJECT BODY")
        print("  send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR ENVIO")
        return 0

    if not argv:
        return _fail([
            "error: subcomando invalido (se esperaba 'query', 'search', "
            "'read', 'account', 'contact', 'message', 'attachment', 'sync', "
            "'draft', 'send', 'doctor' o 'onboard')",
            USAGE,
        ])

    if argv[0] == "message":
        return _run_message(argv)
    if argv[0] == "attachment":
        return _run_attachment(argv)
    if argv[0] == "query":
        return _run_query(argv)
    if argv[0] == "account":
        return _run_account(argv)
    if argv[0] == "contact":
        return _run_contact(argv)
    if argv[0] == "search":
        return _run_search(argv)
    if argv[0] == "read":
        return _run_read(argv)
    if argv[0] == "sync":
        return _run_sync(argv)
    if argv[0] == "watch":
        return _run_watch(argv)
    if argv[0] == "notification":
        return _run_notification(argv)
    if argv[0] == "startup":
        return _run_startup(argv)
    if argv[0] == "draft":
        return _run_draft(argv)
    if argv[0] == "send":
        return _run_send(argv)
    if argv[0] == "doctor":
        repair = "--fix" in argv[1:]
        arguments = [value for value in argv[1:] if value != "--fix"]
        report_path = None
        language = None
        report_format = "json"
        if "--report" in arguments:
            report_index = arguments.index("--report")
            if report_index + 1 >= len(arguments):
                return _fail(["error: doctor --report requiere FILE", USAGE])
            report_path = arguments[report_index + 1]
            del arguments[report_index:report_index + 2]
        for option, default in (("--lang", "es"), ("--format", "json")):
            if option in arguments:
                option_index = arguments.index(option)
                if option_index + 1 >= len(arguments):
                    return _fail([f"error: doctor {option} requiere un valor", USAGE])
                value = arguments[option_index + 1]
                if option == "--lang":
                    language = value
                else:
                    report_format = value
                del arguments[option_index:option_index + 2]
        roots = arguments
        if len(roots) > 1 or any(value.startswith("--") for value in roots):
            return _fail(["error: doctor acepta un solo ROOT", USAGE])
        root = roots[0] if roots else None
        if language is None:
            language = load_language(root) if root else "es"
        else:
            try:
                language = normalize_language(language)
            except ValueError:
                return _fail(["error: doctor acepta --lang es|en|pt", USAGE])
        result = run_diagnostics(root, repair=repair)
        if report_path is not None:
            try:
                _write_diagnostic_report(report_path, result, language, report_format)
            except (OSError, ValueError):
                _print_stderr(["error: no se pudo guardar el reporte de diagnostico"])
                return 1
        result = dict(result)
        result["language"] = language
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "ready" else 1
    if argv[0] == "onboard":
        return _run_onboard(argv)
    if argv[0] == "language":
        if len(argv) < 3 or argv[1] not in ("set", "get"):
            return _fail(["error: language requiere set o get y ROOT", USAGE])
        if argv[1] == "get":
            if len(argv) != 3:
                return _fail(["error: language get requiere ROOT", USAGE])
            try:
                print(json.dumps({"language": load_language(argv[2])}, sort_keys=True))
                return 0
            except (OSError, ValueError):
                return _fail(["error: no se pudo leer la preferencia de idioma", USAGE])
        if len(argv) != 4:
            return _fail(["error: language set requiere ROOT y es|en|pt", USAGE])
        try:
            print(json.dumps({"language": save_language(argv[2], normalize_language(argv[3])), "saved": True}, sort_keys=True))
            return 0
        except (OSError, ValueError):
            return _fail(["error: no se pudo guardar la preferencia de idioma", USAGE])

    return _fail([
        "error: subcomando invalido (se esperaba 'query', 'search', "
        "'read', 'account', 'contact', 'message', 'attachment', 'sync', "
        "'draft' o 'send')",
        USAGE,
        "  search ROOT QUERY  busca nodos .md que contengan QUERY",
        "  read ROOT REL_PATH  imprime el texto integro de un nodo .md",
        "  attachment list ROOT REL_PATH  lista los adjuntos de un nodo .md",
    ] + list(_MESSAGE_ACTION_USAGE))


def main() -> int:
    """Entry point for the installed ``email-agent`` command."""
    return cli_main(sys.argv[1:])
