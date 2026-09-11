"""Aprovisionamiento seguro de cuentas de correo locales.

Pipeline de delegacion puro: valida las entradas publicas, guarda el
secreto UNICAMENTE en el almacenamiento seguro de Windows via
`store_windows_credential`, construye el registro con `create_email_account`
y persiste la cuenta con `save_email_account`. Devuelve solo el registro
publico de cuatro claves; el secreto vive solo en memoria durante la
llamada. Sin red, sin `subprocess`, sin UI ni logs.
"""

from src.email.account import create_email_account
from src.email.account_store import save_email_account
from src.email.wincred import store_windows_credential

_PUBLIC_KEYS = ("account_id", "provider", "email", "status")


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

    Valida `root`/`account_id`/`provider`/`email` ANTES de cualquier
    efecto; delega el resto exclusivamente en `store_windows_credential`,
    `create_email_account` y `save_email_account`. Devuelve un dict con
    EXACTAMENTE `account_id`, `provider`, `email` y `status` (sin
    `credential_ref` ni el secreto). Propaga `ValueError` por entradas
    invalidas y `RuntimeError` si el almacenamiento seguro falla.
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