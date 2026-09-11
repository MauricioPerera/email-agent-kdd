"""Aprovisionamiento seguro de cuentas de correo locales.

Pipeline de delegacion puro: valida las entradas publicas, guarda el
secreto UNICAMENTE en el almacenamiento seguro NATIVO del sistema y
construye el registro con `create_email_account` para persistirlo con
`save_email_account`. Devuelve solo el registro publico de cuatro claves;
el secreto vive solo en memoria durante la llamada. Sin red, sin UI ni
logs; jamas imprime secretos. La eleccion del almacen es por plataforma:
Windows Credential Manager (`wincred://`), macOS Keychain (`keychain://`)
y Linux Secret Service (`secretservice://`). Si el almacen nativo de la
plataforma no esta disponible, PARAR con RuntimeError: no hay fallback
ni texto plano.
"""

import sys

from src.email.account import create_email_account
from src.email.account_store import save_email_account
from src.email.keychain import store_keychain_secret
from src.email.secretservice import store_secretservice_secret
from src.email.wincred import store_windows_credential

_PUBLIC_KEYS = ("account_id", "provider", "email", "status")


def provision_email_account(
    root: str,
    account_id: str,
    provider: str,
    email: str,
    label: str,
    secret: str,
    platform=None,
    backend=None,
) -> dict:
    """Aprovisionar una cuenta local con el secreto en el almacen nativo.

    Elige el almacen por `sys.platform` (o el `platform` explicito, para
    pruebas): `win32` -> wincred, `darwin` -> Keychain, `linux` ->
    Secret Service; cualquier otro PARAR con RuntimeError. Devuelve un
    dict con EXACTAMENTE `account_id`, `provider`, `email` y `status`
    (sin `credential_ref` ni el secreto). Propaga `ValueError` por
    entradas invalidas y `RuntimeError` si el almacen nativo falla.
    """
    for value, name in (
        (root, "root"),
        (account_id, "account_id"),
        (provider, "provider"),
        (email, "email"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(name + " debe ser un str no vacio")
    system = sys.platform if platform is None else platform
    if system == "win32":
        store = store_windows_credential
    elif system == "darwin":
        store = store_keychain_secret
    elif system.startswith("linux"):
        store = store_secretservice_secret
    else:
        raise RuntimeError(
            "PARAR: este sistema no tiene almacenamiento seguro nativo "
            "soportado; no hay fallback"
        )
    ref = store(label, secret, backend) if backend is not None else store(label, secret)
    record = create_email_account(account_id, provider, email, ref)
    save_email_account(root, record)
    return {key: record[key] for key in _PUBLIC_KEYS}


def provision_windows_email_account(
    root: str,
    account_id: str,
    provider: str,
    email: str,
    label: str,
    secret: str,
    backend=None,
) -> dict:
    """Aprovisionar una cuenta local con el secreto solo en wincred.

    Mismo pipeline que `provision_email_account` con la plataforma fijada
    a Windows; se conserva como API estable para el flujo historico.
    """
    for value, name in (
        (root, "root"),
        (account_id, "account_id"),
        (provider, "provider"),
        (email, "email"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(name + " debe ser un str no vacio")
    ref = store_windows_credential(label, secret, backend)
    record = create_email_account(account_id, provider, email, ref)
    save_email_account(root, record)
    return {key: record[key] for key in _PUBLIC_KEYS}