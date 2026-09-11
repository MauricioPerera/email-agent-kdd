"""Puente declarativo entre las operaciones de correo y LSFA."""


def connect_email_request():
    """Construye una solicitud LSFA sin incluir valores de credenciales."""
    return {
        "operation": "connect_email",
        "purpose": "Configurar una cuenta IMAP/SMTP",
        "risk": "medium",
        "initiator": "agent",
        "presentation": "auto",
        "fields": [
            {"name": "email", "type": "email", "sensitivity": "private", "required": True},
            {"name": "password", "type": "secret", "sensitivity": "secret", "required": True},
            {"name": "imap_host", "type": "hostname", "sensitivity": "public", "required": True},
            {"name": "imap_port", "type": "integer", "sensitivity": "public", "default": 993},
            {"name": "smtp_host", "type": "hostname", "sensitivity": "public", "required": True},
            {"name": "smtp_port", "type": "integer", "sensitivity": "public", "default": 465},
        ],
        "validation": {"preflight": "imap_auth_and_smtp_auth", "on_failure": "do_not_store"},
        "confirmation": {"method": "user_accept", "required": True},
        "expires_in_seconds": 600,
    }


def send_email_request():
    """Construye una solicitud LSFA de envío; no contiene el contenido real."""
    return {
        "operation": "send_email",
        "purpose": "Enviar un correo preparado por el usuario",
        "risk": "high",
        "initiator": "agent",
        "fields": [
            {"name": "account_ref", "type": "opaque_reference", "sensitivity": "private", "required": True},
            {"name": "to", "type": "email_list", "sensitivity": "private", "required": True},
            {"name": "subject", "type": "text", "sensitivity": "private", "required": True},
            {"name": "body", "type": "multiline", "sensitivity": "private", "required": True},
        ],
        "validation": {"preflight": "recipient_and_draft_review"},
        "confirmation": {"method": "pin", "required": True, "summary": ["to", "subject"]},
        "expires_in_seconds": 300,
    }
