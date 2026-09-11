"""Resolucion de referencias de credenciales al secreto correspondiente.

El secreto vive unicamente en memoria: nunca se imprime, persiste ni se
incluye en mensajes de error. `env://NAME` consulta environ; `wincred://`
delega en src.email.wincred (Windows Credential Manager), `keychain://`
en src.email.keychain (macOS Keychain) y `secretservice://` en
src.email.secretservice (Secret Service de Linux); ninguno pasa environ
ni ofrece fallback, y cada uno PARAR si su almacen nativo no existe.
Otros esquemas se rechazan con ValueError.
"""

import os
import re

from src.email.keychain import delete_keychain_secret, resolve_keychain_secret
from src.email.secretservice import (
    delete_secretservice_secret,
    resolve_secretservice_secret,
)
from src.email.wincred import delete_windows_credential, resolve_windows_credential

_ENV_PATTERN = re.compile(r"^env://([A-Za-z0-9_]+)$")
_WINCRED_PREFIX = "wincred://"
_KEYCHAIN_PREFIX = "keychain://"
_SECRETSERVICE_PREFIX = "secretservice://"


def resolve_credential(credential_ref: str, environ=None) -> str:
    if not isinstance(credential_ref, str):
        raise ValueError("credential_ref invalida: se espera str")
    if credential_ref.startswith(_WINCRED_PREFIX):
        return resolve_windows_credential(credential_ref)
    if credential_ref.startswith(_KEYCHAIN_PREFIX):
        return resolve_keychain_secret(credential_ref)
    if credential_ref.startswith(_SECRETSERVICE_PREFIX):
        return resolve_secretservice_secret(credential_ref)
    match = _ENV_PATTERN.match(credential_ref)
    if match is None:
        raise ValueError(
            "referencia invalida: solo se aceptan env://NAME, wincred://LABEL, "
            "keychain://LABEL y secretservice://LABEL"
        )
    source = os.environ if environ is None else environ
    value = source.get(match.group(1))
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("credencial ausente o con valor vacio")
    return value


def delete_stored_credential(credential_ref: str) -> None:
    """Borrar el secreto persistido de la referencia; env:// no persiste nada."""
    if not isinstance(credential_ref, str):
        raise ValueError("credential_ref invalida: se espera str")
    if credential_ref.startswith(_WINCRED_PREFIX):
        delete_windows_credential(credential_ref)
    elif credential_ref.startswith(_KEYCHAIN_PREFIX):
        delete_keychain_secret(credential_ref)
    elif credential_ref.startswith(_SECRETSERVICE_PREFIX):
        delete_secretservice_secret(credential_ref)