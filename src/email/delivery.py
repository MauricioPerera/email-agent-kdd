"""Extraccion del destinatario real de entrega (contrato delivery-recipient)."""

import email.utils

_ENVELOPE_HEADERS = ("Delivered-To", "X-Original-To", "Envelope-To")


def extract_delivered_to(message) -> list:
    """Devuelve las direcciones de envelope (Delivered-To/X-Original-To/Envelope-To) verbatim."""
    get_all = getattr(message, "get_all", None)
    if not callable(get_all):
        raise TypeError("message debe ser un email.message.Message parseado")
    found = set()
    for name in _ENVELOPE_HEADERS:
        for value in get_all(name, []):
            for _display, addr_spec in email.utils.getaddresses([str(value)]):
                addr = addr_spec.strip()
                if addr and "@" in addr:
                    found.add(addr)
    return sorted(found)