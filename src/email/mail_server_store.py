# -*- coding: utf-8 -*-
"""Store JSON de configuracion publica de servidores IMAP/SMTP por cuenta.

Guarda y lee `<root>/.email-agent/mail-servers.json`: un objeto con la
unica clave "servers" que mapea account_id -> registro de cuatro claves
(imap_host, imap_port, smtp_host, smtp_port). Jamas secretos: ni
`password`, ni `credential_ref`, ni claves extra. Escritura atomica
(temporal en el mismo directorio + os.replace) y JSON determinista
(claves ordenadas, ensure_ascii=False, salto de linea final).
"""

import json
import os
import re
from pathlib import Path

STORE_DIR = ".email-agent"
STORE_NAME = "mail-servers.json"
_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]{0,251}[a-z0-9])?$")
_CONFIG_KEYS = frozenset({"imap_host", "imap_port", "smtp_host", "smtp_port"})
_ERROR_ROOT = "root invalido"
_ERROR_ACCOUNT = "account_id invalido"
_ERROR_CONFIG = "config invalida"
_ERROR_CORRUPT = "store corrupto"
_ERROR_SCHEMA = "store fuera de esquema"


def store_mail_server_config(root: str, account_id: str, config: dict) -> str:
    """Valida, fusiona el registro de la cuenta y devuelve la ruta absoluta del store."""
    _validate_identity(root, account_id)
    _validate_config(config)
    path = _store_path(root)
    data = _read_store(path)
    data["servers"][account_id] = dict(config)
    _write_store(path, data)
    return os.path.abspath(str(path))


def load_mail_server_config(root: str, account_id: str) -> dict:
    """Devuelve el registro de cuatro claves; None si el archivo o la cuenta no existen."""
    _validate_identity(root, account_id)
    data = _read_store(_store_path(root))
    entry = data["servers"].get(account_id)
    if entry is None:
        return None
    return dict(entry)


def remove_mail_server_config(root: str, account_id: str) -> bool:
    """Eliminar solo la configuracion publica de servidores de una cuenta."""
    _validate_identity(root, account_id)
    path = _store_path(root)
    data = _read_store(path)
    if account_id not in data["servers"]:
        return False
    del data["servers"][account_id]
    _write_store(path, data)
    return True


def _validate_identity(root, account_id):
    if not isinstance(root, str) or not root.strip():
        raise ValueError(_ERROR_ROOT)
    if not isinstance(account_id, str) or _ACCOUNT_ID_RE.match(account_id) is None:
        raise ValueError(_ERROR_ACCOUNT)


def _validate_config(config):
    if not isinstance(config, dict) or set(config) != _CONFIG_KEYS:
        raise ValueError(_ERROR_CONFIG)
    for key in ("imap_host", "smtp_host"):
        if not _is_host(config[key]):
            raise ValueError(_ERROR_CONFIG)
    for key in ("imap_port", "smtp_port"):
        if not _is_port(config[key]):
            raise ValueError(_ERROR_CONFIG)


def _is_host(host):
    return (
        isinstance(host, str)
        and len(host) <= 253
        and _HOST_RE.match(host) is not None
        and ".." not in host
    )


def _is_port(port):
    return (
        isinstance(port, int)
        and not isinstance(port, bool)
        and 1 <= port <= 65535
    )


def _store_path(root):
    return Path(root).resolve() / STORE_DIR / STORE_NAME


def _read_store(path):
    """Lee y valida el esquema completo del store; RuntimeError si esta mal."""
    if not path.exists():
        return {"servers": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError(_ERROR_CORRUPT) from None
    if not isinstance(data, dict) or set(data) != {"servers"}:
        raise RuntimeError(_ERROR_SCHEMA)
    if not isinstance(data["servers"], dict):
        raise RuntimeError(_ERROR_SCHEMA)
    for entry in data["servers"].values():
        try:
            _validate_config(entry)
        except ValueError:
            raise RuntimeError(_ERROR_SCHEMA) from None
    return data


def _write_store(path, data):
    text = json.dumps(data, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))
