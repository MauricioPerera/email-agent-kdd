"""Small, secret-free, atomic state store for assisted installation."""

import json
import os
from pathlib import Path


_ALLOWED_STATUSES = {
    "not-installed",
    "missing-runtime",
    "ready-for-install",
    "installed",
    "needs-account",
    "needs-user-action",
    "ready-to-sync",
    "complete",
    "failed",
}


def state_path(root) -> Path:
    return Path(root) / ".email-agent" / "bootstrap.json"


def read_bootstrap_state(root):
    target = state_path(root)
    if not target.exists():
        return None
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("bootstrap state is unreadable") from exc
    if not isinstance(value, dict) or value.get("status") not in _ALLOWED_STATUSES:
        raise RuntimeError("bootstrap state is invalid")
    return value


def write_bootstrap_state(root, status, *, account_id=None, language="es"):
    if status not in _ALLOWED_STATUSES:
        raise ValueError("invalid bootstrap status")
    payload = {"schema": 1, "status": status, "language": language}
    if account_id is not None:
        payload["account_id"] = str(account_id)
    target = state_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return payload
