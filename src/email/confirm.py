"""Confirmacion de borradores pendientes, sin enviar nada.

Valida la frase de confirmacion exacta del usuario y el estado ``pending``,
y devuelve una copia del borrador con estado ``confirmed`` y un
``confirmation_hash`` determinista. Solo transforma el objeto en memoria:
no envia, no escribe archivos y no toca la red.
"""

import hashlib

_REQUIRED_KEYS = ("id", "account_id", "to", "subject", "body", "status")
_REQUIRED_PHRASE = "CONFIRMAR ENVIO"


def confirm_email_draft(draft: dict, confirmation: str) -> dict:
    """Confirmar un borrador ``pending`` con la frase exacta del usuario.

    La comparacion de la frase es de igualdad exacta contra
    ``"CONFIRMAR ENVIO"`` (sin strip, sin mayusculas, sin variantes). El
    ``confirmation_hash`` es ``sha256(draft["id"] + "|" + confirmation)``
    en hexadecimal minusculas. Rechaza entradas invalidas con
    ``ValueError``; jamas muta el dict de entrada.
    """
    if not isinstance(draft, dict):
        raise ValueError("draft debe ser un dict")
    missing = [key for key in _REQUIRED_KEYS if key not in draft]
    if missing:
        raise ValueError("falta la clave obligatoria: " + ", ".join(missing))
    if draft["status"] != "pending":
        raise ValueError("solo se confirma un borrador con status pending")
    if not isinstance(confirmation, str) or confirmation != _REQUIRED_PHRASE:
        raise ValueError("confirmation debe ser exactamente: " + _REQUIRED_PHRASE)

    result = dict(draft)
    hash_payload = result["id"] + "|" + confirmation
    result["status"] = "confirmed"
    result["confirmation_hash"] = hashlib.sha256(
        hash_payload.encode("utf-8")
    ).hexdigest()
    return result