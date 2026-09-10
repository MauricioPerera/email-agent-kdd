"""Sincronizacion de una cuenta (orquestador puro, ver contrato sync-email-account)."""

from typing import List


def _fail(account_id, stage):
    raise RuntimeError(
        "sincronizacion de cuenta '%s' fallo en etapa '%s'" % (account_id, stage)
    )


def _wrap(account_id, stage, fn, *args):
    try:
        return fn(*args)
    except Exception:
        _fail(account_id, stage)


def _validate_messages(account_id, messages):
    if not isinstance(messages, list):
        _fail(account_id, "fetch")
    for message in messages:
        if not isinstance(message, dict):
            _fail(account_id, "fetch")


def sync_email_account(account, fetch_messages, persist_message, update_contacts=None):
    """Orquesta la sincronizacion de una cuenta con callables inyectados.

    Llama `fetch_messages(account)` una vez, persiste cada mensaje en orden
    y, si se pasa `update_contacts`, lo alimenta una vez con una copia de los
    mensajes. Devuelve el resumen exacto de cinco claves del contrato.
    """
    if not isinstance(account, dict):
        raise RuntimeError("sincronizacion requiere account dict")
    account_id = account.get("account_id")
    if not isinstance(account_id, str) or not account_id:
        raise RuntimeError("sincronizacion requiere account_id str no vacio")
    if not callable(fetch_messages) or not callable(persist_message):
        raise RuntimeError("sincronizacion requiere callables inyectados")

    messages = _wrap(account_id, "fetch", fetch_messages, account)
    _validate_messages(account_id, messages)

    persisted_paths: List[str] = []
    for message in messages:
        path = _wrap(account_id, "persist", persist_message, message)
        persisted_paths.append(path)

    contacts_updated = False
    if update_contacts is not None:
        _wrap(account_id, "contacts", update_contacts, list(messages))
        contacts_updated = True

    return {
        "account_id": account_id,
        "fetched": len(messages),
        "persisted": len(persisted_paths),
        "persisted_paths": persisted_paths,
        "contacts_updated": contacts_updated,
    }