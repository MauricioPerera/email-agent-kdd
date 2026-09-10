"""Contactos del destinatario To de un mensaje saliente confirmado."""

from email.utils import getaddresses


def extract_outgoing_contacts(message: dict) -> list:
    """Deriva contactos deduplicados leyendo solo ``message["to"]``."""
    if not isinstance(message, dict):
        raise ValueError("message debe ser un dict de mensaje saliente")
    to = message.get("to")
    if not isinstance(to, list):
        raise ValueError("message['to'] debe ser una lista de destinatarios")
    contacts = []
    seen = set()
    for element in to:
        if not isinstance(element, str):
            continue
        groups = getaddresses([element])
        if not groups:
            continue
        name, address = groups[0]
        address = address.strip().lower()
        if not address or address in seen:
            continue
        seen.add(address)
        contacts.append({"name": name.strip(), "email": address})
    return contacts