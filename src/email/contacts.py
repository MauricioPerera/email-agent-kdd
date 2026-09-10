"""Extraccion de contactos desde los headers From, To y Cc."""

from email.utils import getaddresses

_HEADER_ORDER = ("from", "to", "cc")


def _new_contacts(values, seen):
    """Convierte un header en contactos, deduplicando por email en minusculas."""
    contacts = []
    for name, address in getaddresses([values]):
        email = address.lower()
        if not email or email in seen:
            continue
        seen.add(email)
        contacts.append({"name": name, "email": email})
    return contacts


def extract_contacts(record: dict) -> list:
    """Devuelve contactos deduplicados en orden From, To, Cc.

    Pura: no modifica el registro ni toca la red. El email sale en
    minusculas; la primera aparicion gana su ``name``. Si el registro
    trae ``headers`` (formato de ``normalize_email``) se lee de ahi; si
    no, se leen los campos top-level ``from``, ``to`` y ``cc`` que
    produce ``parse_raw_email``.
    """
    headers = record.get("headers")
    if not isinstance(headers, dict):
        headers = record
    seen = set()
    contacts = []
    for key in _HEADER_ORDER:
        contacts.extend(_new_contacts(headers.get(key) or "", seen))
    return contacts