"""Resolucion de referencias env://NAME y wincred://LABEL al secreto.

El secreto vive unicamente en memoria: nunca se imprime, persiste ni se
incluye en mensajes de error. wincred:// delega en src.email.wincred
(Windows Credential Manager) sin pasar environ y sin fallback; otros
esquemas se rechazan con ValueError.
"""

import os
import re

from src.email.wincred import resolve_windows_credential

_ENV_PATTERN = re.compile(r"^env://([A-Za-z0-9_]+)$")
_WINCRED_PREFIX = "wincred://"


def resolve_credential(credential_ref: str, environ=None) -> str:
    if not isinstance(credential_ref, str):
        raise ValueError("credential_ref invalida: se espera str")
    if credential_ref.startswith(_WINCRED_PREFIX):
        return resolve_windows_credential(credential_ref)
    match = _ENV_PATTERN.match(credential_ref)
    if match is None:
        raise ValueError(
            "referencia invalida: solo se aceptan env://NAME y wincred://LABEL"
        )
    source = os.environ if environ is None else environ
    value = source.get(match.group(1))
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("credencial ausente o con valor vacio")
    return value