"""Almacenamiento local seguro de cuentas de correo, sin conectarse a proveedores.

Guarda y lee los registros de `create_email_account` en
`<root>/.email-agent/accounts.json`. Solo viajan referencias opacas
(`credential_ref`): el esquema acepta exactamente las cinco claves del
registro, rechaza claves extra o valores que no sean `str` y no hay red.
"""

import json
import os
from pathlib import Path

_RECORD_KEYS = ("account_id", "provider", "email", "credential_ref", "status")
_INITIAL_STATUS = "disconnected"


def _validate_record(record, error):
    if not isinstance(record, dict):
        raise error("account debe ser un dict con el registro de create_email_account")
    if set(record) != set(_RECORD_KEYS):
        raise error("account debe tener exactamente las claves " + ", ".join(_RECORD_KEYS))
    for key in _RECORD_KEYS[:4]:
        if not isinstance(record[key], str) or not record[key].strip():
            raise error(key + " debe ser un str no vacio")
    if record["status"] != _INITIAL_STATUS:
        raise error('status debe ser "' + _INITIAL_STATUS + '"')


def _store_path(root):
    """Resolver `<root>/.email-agent/accounts.json` o rechazar root invalido."""
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root debe ser un str no vacio")
    return Path(root) / ".email-agent" / "accounts.json"


def _read_records(path, error):
    """Leer los registros del store; lanza ``error`` si esta corrupto."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise error("accounts.json corrupto o ilegible: " + type(exc).__name__)
    if not isinstance(data, dict) or set(data) != {"accounts"} or not isinstance(data["accounts"], list):
        raise error("accounts.json no tiene el esquema esperado")
    records = []
    for record in data["accounts"]:
        _validate_record(record, error)
        records.append({key: record[key] for key in _RECORD_KEYS})
    return records


def save_email_account(root: str, account: dict) -> str:
    """Guardar (o reemplazar por account_id) una cuenta en el store local.

    Valida el registro contra el esquema de `create_email_account`, crea
    `<root>/.email-agent/` y escribe `accounts.json` de forma atomica y
    determinista (claves ordenadas, UTF-8). Devuelve la ruta absoluta del
    archivo; jamas interpreta ni loguea `credential_ref`.
    """
    path = _store_path(root)
    _validate_record(account, ValueError)
    records = _read_records(path, RuntimeError) if path.exists() else []
    records = [r for r in records if r["account_id"] != account["account_id"]]
    records.append({key: account[key] for key in _RECORD_KEYS})
    path.parent.mkdir(parents=True, exist_ok=True)
    records.sort(key=lambda r: r["account_id"])
    payload = json.dumps({"accounts": records}, sort_keys=True, ensure_ascii=False)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes((payload + "\n").encode("utf-8"))
    os.replace(temporary, path)
    return str(path.resolve())


def load_email_accounts(root: str) -> list:
    """Leer las cuentas guardadas, ordenadas por account_id.

    Devuelve `[]` si el store aun no existe. Un archivo corrupto o con
    entradas fuera del esquema lanza `RuntimeError`; el mensaje jamas
    incluye contenido de las entradas (sin filtrar secretos).
    """
    path = _store_path(root)
    if not path.exists():
        return []
    records = _read_records(path, RuntimeError)
    records.sort(key=lambda r: r["account_id"])
    return records