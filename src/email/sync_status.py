"""Estado local y seguro de la última sincronización por cuenta."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _path(root):
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError("root invalido")
    return base / ".email-agent" / "sync-status.json"


def read_sync_status(root, account_id):
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("account_id invalido")
    try:
        payload = json.loads(_path(root).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise RuntimeError("estado de sincronizacion ilegible") from exc
    accounts = payload.get("accounts") if isinstance(payload, dict) else None
    if not isinstance(accounts, dict):
        raise RuntimeError("estado de sincronizacion invalido")
    entry = accounts.get(account_id)
    if entry is not None and not isinstance(entry, dict):
        raise RuntimeError("estado de sincronizacion invalido")
    return entry


def record_sync_status(root, summary):
    account_id = summary.get("account_id") if isinstance(summary, dict) else None
    if not isinstance(account_id, str) or not account_id:
        raise ValueError("summary invalido")
    path = _path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"accounts": {}}
    except (OSError, ValueError) as exc:
        raise RuntimeError("estado de sincronizacion ilegible") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("accounts"), dict):
        raise RuntimeError("estado de sincronizacion invalido")
    payload["accounts"][account_id] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "fetched": int(summary.get("fetched", 0)),
        "persisted": int(summary.get("persisted", 0)),
        "contacts_updated": bool(summary.get("contacts_updated", False)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
