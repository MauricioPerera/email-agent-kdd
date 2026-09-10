"""Resolucion de referencias env:// al secreto de su variable de entorno.

El secreto vive unicamente en memoria: nunca se imprime, persiste ni se
incluye en mensajes de error.
"""

import os
import re

_REF_PATTERN = re.compile(r"^env://([A-Za-z0-9_]+)$")


def resolve_credential(credential_ref: str, environ=None) -> str:
    if not isinstance(credential_ref, str):
        raise ValueError("credential_ref invalida: se espera str")
    match = _REF_PATTERN.match(credential_ref)
    if match is None:
        raise ValueError("referencia invalida: solo se acepta env://NAME")
    source = os.environ if environ is None else environ
    value = source.get(match.group(1))
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("credencial ausente o con valor vacio")
    return value