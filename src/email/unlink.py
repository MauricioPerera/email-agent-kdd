"""Desvinculacion transaccional de una cuenta de correo local.

La desvinculacion es una transaccion: primero se leen los estados previos
(sin mutar), luego se limpia lo local (config de servidores y registro de
la cuenta) y AL FINAL se borra el secreto del almacen nativo. Jamas se
resuelve ni se lee el secreto (no se llama a `resolve_credential`): solo
se elimina la referencia. Si un paso falla despues de mutar algo local,
se restaura ese estado previo (rollback best-effort: si la propia
restauracion falla, se re-lanza el error ORIGINAL) y el secreto queda
intacto. Los correos descargados no se tocan nunca.
"""

from src.email.account_store import (
    load_email_accounts,
    remove_email_account,
    save_email_account,
)
from src.email.credentials import delete_stored_credential
from src.email.mail_server_store import (
    load_mail_server_config,
    remove_mail_server_config,
    store_mail_server_config,
)


def unlink_email_account(
    root: str,
    account_id: str,
    credential=delete_stored_credential,
    servers=remove_mail_server_config,
) -> dict:
    """Desvincular una cuenta sin tocar los correos descargados.

    Orden transaccional: pre-lecturas, limpieza de la config de
    servidores, borrado del registro (commit local) y, al final, borrado
    del secreto nativo. Devuelve solo `account_id`, `email` y `status`:
    jamas `credential_ref` ni secretos.
    """
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id debe ser un str no vacio")
    record = _find_record(root, account_id)
    snapshot = load_mail_server_config(root, account_id)
    try:
        servers(root, account_id)
        remove_email_account(root, account_id)
    except (ValueError, RuntimeError, OSError) as exc:
        _restore_servers(root, account_id, snapshot)
        raise exc
    try:
        credential(record["credential_ref"])
    except (ValueError, RuntimeError, OSError) as exc:
        _restore_account(root, record, snapshot)
        raise exc
    return {
        "account_id": record["account_id"],
        "email": record["email"],
        "status": "unlinked",
    }


def _find_record(root, account_id):
    """Leer el registro de la cuenta sin mutar nada; LookupError si falta."""
    for record in load_email_accounts(root):
        if record["account_id"] == account_id:
            return record
    raise LookupError("cuenta no encontrada")


def _restore_servers(root, account_id, snapshot):
    """Rollback best-effort de mail-servers.json; jamas enmascara el error."""
    if snapshot is None:
        return
    try:
        store_mail_server_config(root, account_id, snapshot)
    except (ValueError, RuntimeError, OSError):
        pass  # best-effort: se conserva el error original de la desvinculacion


def _restore_account(root, record, snapshot):
    """Rollback best-effort: reponer la cuenta y su config de servidores.

    El secreto no se toca aqui: si se llega a este rollback es porque el
    borrado del secreto fallo y el backend no lo elimino.
    """
    try:
        save_email_account(root, dict(record))
        if snapshot is not None:
            store_mail_server_config(root, record["account_id"], snapshot)
    except (ValueError, RuntimeError, OSError):
        pass  # best-effort: se conserva el error original de la desvinculacion