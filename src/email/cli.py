"""CLI local de correo: capa fina de presentacion sobre search, cuentas y sync.

Interpreta `argv` (sin el nombre del programa): `--help`/`-h`, el subcomando
`query ROOT INSTRUCTION`, el subcomando `search ROOT QUERY`, el subcomando
`account` (`setup ROOT` guiado, `add ROOT ACCOUNT_ID PROVIDER EMAIL
CREDENTIAL_REF` y `list ROOT`) o el subcomando `sync ROOT ACCOUNT_ID [HOST]`. Los datos van a stdout; usage
y errores a stderr, siempre genericos
(sin `credential_ref` ni secretos ni tracebacks). Codigos: 0 exito/ayuda,
1 fallo de operacion, 2 error de argumentos. La lectura de cuentas, la
resolucion de credenciales, el fetch IMAP, la orquestacion, la persistencia
OKF y la extraccion/almacen de contactos no se reimplementan: se delega en
account, account_store, search, credentials, imap_reader, sync, persist_at,
contacts, contact_store, outgoing_contacts y cursor_store.
"""

import json
import os
import sys

from src.email.account import create_email_account
from src.email.account_store import load_email_accounts, save_email_account
from src.email.confirm import confirm_email_draft
from src.email.contacts import extract_contacts
from src.email.contact_store import load_email_contacts, store_email_contacts
from src.email.cursor_store import load_sync_cursor, save_sync_cursor
from src.email.draft import create_email_draft
from src.email.smtp_send import send_smtp_message
from src.email.conversation_index import persist_conversation_index
from src.email.credentials import resolve_credential
from src.email.imap_reader import fetch_imap_messages
from src.email.node import read_email_node
from src.email.outgoing_contacts import extract_outgoing_contacts
from src.email.persist_at import persist_email_okf_at
from src.email.topic_index import persist_topic_index
from src.email.query import query_email
from src.email.search import search_email_nodes
from src.email.sync import sync_email_account

USAGE = (
    "usage: email-cli [--help] | email-cli query ROOT INSTRUCTION | "
    "email-cli search ROOT QUERY | "
    "email-cli read ROOT REL_PATH | "
    "email-cli account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF | "
    "email-cli account setup ROOT | "
    "email-cli account list ROOT | email-cli contact list ROOT | "
    "email-cli sync ROOT ACCOUNT_ID [HOST] | "
    "email-cli draft ROOT ACCOUNT_ID TO SUBJECT BODY | "
    "email-cli send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR ENVIO"
)
SYNC_USAGE = "  sync ROOT ACCOUNT_ID [HOST]  sincroniza una cuenta guardada"
_PROVIDER_HOSTS = {"gmail": "imap.gmail.com", "outlook": "outlook.office365.com"}
_PUBLIC_KEYS = ("account_id", "provider", "email", "status")
_SMTP_PROVIDER_HOSTS = {"gmail": "smtp.gmail.com", "outlook": "smtp.office365.com"}
_DEFAULT_SMTP_PORT = 587
_CONFIRMATION_PHRASE = "CONFIRMAR ENVIO"
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
_SETUP_ENV_NAME_HEAD = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_SETUP_ENV_NAME_TAIL = _SETUP_ENV_NAME_HEAD + "0123456789"


def _print_stderr(lines):
    for line in lines:
        print(line, file=sys.stderr)


def _fail(lines):
    _print_stderr(lines)
    return 2


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
    if len(argv) != 3:
        return _fail([
            "error: account setup requiere exactamente ROOT",
            USAGE,
        ])
    print(_SETUP_INTRO)
    answers = []
    for prompt in _SETUP_PROMPTS:
        print(prompt, end="")
        try:
            answer = input().strip()
        except (EOFError, KeyboardInterrupt):
            return _setup_cancel("error: configuracion cancelada (entrada terminada)")
        if answer.lower() in ("cancelar", "cancel"):
            return _setup_cancel("error: configuracion cancelada por el usuario")
        if not answer:
            return _setup_cancel("error: la respuesta no puede estar vacia")
        answers.append(answer)
    account_id, provider, email, env_name = answers
    if provider.lower() not in ("gmail", "outlook"):
        _print_stderr([
            "error: proveedor no admitido (solo se admiten gmail u outlook)",
        ])
        return 1
    if env_name[0] not in _SETUP_ENV_NAME_HEAD or any(
        char not in _SETUP_ENV_NAME_TAIL for char in env_name[1:]
    ):
        _print_stderr(["error: nombre de variable de entorno invalido"])
        return 1
    try:
        account = create_email_account(
            account_id, provider, email, "env://" + env_name
        )
        save_email_account(argv[2], account)
    except (ValueError, RuntimeError):
        _print_stderr([
            "error: no se pudo guardar la cuenta "
            "(datos o almacenamiento invalidos)",
        ])
        return 1
    print("account saved: " + account["account_id"])
    return 0


def _run_account(argv):
    if len(argv) < 2 or argv[1] not in ("add", "setup", "list"):
        return _fail([
            "error: account requiere 'add', 'setup' o 'list'",
            USAGE,
            "  account setup ROOT  alta guiada interactiva",
            "  account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF",
            "  account list ROOT",
        ])
    if argv[1] == "add":
        return _account_add(argv)
    if argv[1] == "setup":
        return _account_setup(argv)
    return _account_list(argv)


def _run_query(argv):
    if len(argv) != 3:
        return _fail([
            "error: query requiere exactamente ROOT e INSTRUCTION "
            "(citada como un solo argumento)",
            USAGE,
        ])
    try:
        matches = query_email(argv[1], argv[2])
    except ValueError:
        _print_stderr([
            "error: la consulta es invalida (raiz inexistente o "
            "instruccion sin criterios validos)",
        ])
        return 2
    except Exception:
        _print_stderr(["error: la consulta fallo"])
        return 1
    for path in matches:
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
    sys.stdout.write(text)
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
        secret = resolve_credential(account["credential_ref"])
    except Exception:
        _print_stderr(["error: credencial irresoluble"])
        return 1
    host = account.get("smtp_host") or _SMTP_PROVIDER_HOSTS.get(account.get("provider"))
    if not host:
        _print_stderr(["error: provider sin host smtp por defecto"])
        return 1
    config = {
        "host": host,
        "port": _DEFAULT_SMTP_PORT,
        "username": account["email"],
        "password": secret,
    }
    try:
        send_smtp_message(account, config, confirmed)
    except Exception:
        _print_stderr(["error: el envio fallo"])
        return 1
    # Post-envio: registro de contactos salientes. El SMTP ya pudo entregar el
    # mensaje; si el registro falla NO se reintentara el envio automaticamente
    # (reenviar duplicaria el correo; la libreta puede actualizarse por otra via).
    try:
        contacts = extract_outgoing_contacts(confirmed)
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
    if len(argv) < 2 or argv[1] != "list":
        return _fail([
            "error: contact requiere el subcomando 'list'",
            USAGE,
            "  contact list ROOT  lista la libreta de contactos",
        ])
    if len(argv) != 3:
        return _fail([
            "error: contact list requiere exactamente ROOT",
            USAGE,
        ])
    try:
        contacts = load_email_contacts(argv[2])
    except (ValueError, RuntimeError):
        _print_stderr([
            "error: no se pudieron leer los contactos (almacenamiento invalido)",
        ])
        return 1
    for record in contacts:
        print(json.dumps(
            {"name": record["name"], "email": record["email"]},
            sort_keys=True,
        ))
    return 0


def _run_sync(argv):
    if len(argv) not in (3, 4):
        return _fail([
            "error: sync requiere ROOT y ACCOUNT_ID y HOST opcional",
            USAGE,
            SYNC_USAGE,
        ])
    root, account_id = argv[1], argv[2]
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
        secret = resolve_credential(account["credential_ref"])
    except Exception:
        _print_stderr(["error: credencial irresoluble"])
        return 1
    if len(argv) == 4:
        host = argv[3]
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
    fetched = []

    def fetch(_account):
        nonlocal fetched
        fetched = fetch_imap_messages(_account, config)
        return fetched

    def persist(record):
        rel_path = "store/emails/" + record["raw_sha256"] + ".md"
        path = persist_email_okf_at(record, root, rel_path)
        persist_conversation_index(root, record, rel_path)
        persist_topic_index(root, record, rel_path)
        return path

    try:
        summary = sync_email_account(account, fetch, persist, _make_update_contacts(root))
    except Exception:
        _print_stderr(["error: la sincronizacion fallo (cuenta o almacen invalido)"])
        return 1
    if fetched:
        try:
            save_sync_cursor(
                root, account_id, max(record["imap_uid"] for record in fetched)
            )
        except (ValueError, RuntimeError):
            _print_stderr(["error: el cursor de sincronizacion no se pudo guardar"])
            return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


def cli_main(argv: list) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(USAGE)
        print("  query ROOT INSTRUCTION  consulta el store local con query_email")
        print("  account setup ROOT  alta guiada interactiva")
        print("  account add ROOT ACCOUNT_ID PROVIDER EMAIL CREDENTIAL_REF")
        print("  account list ROOT")
        print("  contact list ROOT  lista la libreta de contactos")
        print("  search ROOT QUERY  busca nodos .md que contengan QUERY")
        print("  read ROOT REL_PATH  imprime el texto integro de un nodo .md")
        print(SYNC_USAGE)
        print("  draft ROOT ACCOUNT_ID TO SUBJECT BODY")
        print("  send ROOT ACCOUNT_ID DRAFT_ID CONFIRMAR ENVIO")
        return 0

    if not argv:
        return _fail([
            "error: subcomando invalido (se esperaba 'query', 'search', "
            "'read', 'account', 'contact', 'sync', 'draft' o 'send')",
            USAGE,
        ])

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
    if argv[0] == "draft":
        return _run_draft(argv)
    if argv[0] == "send":
        return _run_send(argv)

    return _fail([
        "error: subcomando invalido (se esperaba 'query', 'search', "
        "'read', 'account', 'contact', 'sync', 'draft' o 'send')",
        USAGE,
        "  search ROOT QUERY  busca nodos .md que contengan QUERY",
        "  read ROOT REL_PATH  imprime el texto integro de un nodo .md",
    ])