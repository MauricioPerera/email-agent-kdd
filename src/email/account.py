"""Registro local de cuentas de correo, sin conectarse a ningun proveedor.

Construye un registro serializable y determinista de la cuenta como
preparacion para OAuth/sincronizacion futura. Solo transforma los datos en
memoria: no se conecta, no guarda, no abre credenciales y no escribe
archivos. ``credential_ref`` es una referencia opaca (texto que apunta al
secreto), nunca el secreto mismo.
"""

_INITIAL_STATUS = "disconnected"


def _require_non_empty_str(value: str, name: str) -> str:
    """Validar que ``value`` sea un str no vacio (rechazo con ValueError)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + " debe ser un str no vacio")
    return value


def _normalize_provider(provider: str) -> str:
    """Normalizar el proveedor: bordes recortados y minusculas."""
    return provider.strip().lower()


def _normalize_email(email: str) -> str:
    """Normalizar el email: minusculas y sin ningun espacio en blanco."""
    return "".join(email.split()).lower()


def create_email_account(
    account_id: str, provider: str, email: str, credential_ref: str
) -> dict:
    """Registrar localmente una cuenta de correo sin conectar nada.

    Devuelve un dict serializable a JSON con ``account_id`` y
    ``credential_ref`` verbatim, ``provider`` en minusculas, ``email`` en
    minusculas sin espacios y ``status: "disconnected"``. Rechaza entradas
    invalidas con ``ValueError``; jamas interpreta ``credential_ref`` ni
    muta los argumentos de entrada.
    """
    _require_non_empty_str(account_id, "account_id")
    _require_non_empty_str(provider, "provider")
    _require_non_empty_str(email, "email")
    _require_non_empty_str(credential_ref, "credential_ref")

    return {
        "account_id": account_id,
        "provider": _normalize_provider(provider),
        "email": _normalize_email(email),
        "credential_ref": credential_ref,
        "status": _INITIAL_STATUS,
    }