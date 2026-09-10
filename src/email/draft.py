"""Borradores de correo serializables, sin enviar nada.

Construye el objeto de borrador con id determinista (sha256) y estado
``pending``. Solo construye: no envia, no escribe archivos y no toca la red.
"""

import hashlib


def create_email_draft(account_id: str, to: list, subject: str, body: str) -> dict:
    """Convertir datos crudos de borrador en un dict serializable.

    Normaliza destinatarios (strip -> descartar vacios -> minusculas ->
    dedup conservando orden) y calcula el ``id`` con la regla sha256
    documentada. Rechaza entradas invalidas con ``ValueError``.
    """
    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id debe ser un str no vacio")
    if not isinstance(to, list):
        raise ValueError("to debe ser una lista de str")
    for entry in to:
        if not isinstance(entry, str):
            raise ValueError("cada destinatario de to debe ser str")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("subject debe ser un str no vacio")
    if not isinstance(body, str) or not body:
        raise ValueError("body debe ser un str no vacio")

    to_norm = []
    for entry in to:
        trimmed = entry.strip()
        if not trimmed:
            continue
        lowered = trimmed.lower()
        if lowered not in to_norm:
            to_norm.append(lowered)
    if not to_norm:
        raise ValueError("to normalizado queda vacio")

    id_payload = account_id + "|" + ",".join(to_norm) + "|" + subject + "|" + body
    draft_id = hashlib.sha256(id_payload.encode("utf-8")).hexdigest()

    return {
        "id": draft_id,
        "account_id": account_id,
        "to": to_norm,
        "subject": subject,
        "body": body,
        "status": "pending",
    }