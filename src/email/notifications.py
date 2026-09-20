"""Reglas y notificaciones locales para correos sincronizados."""

import base64
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from time import time

from src.email.filter_grammar import parse_filter_query, record_from_markdown, record_matches

_RULES = "notification-rules.json"
_STATE = "notification-state.json"
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
MAX_NOTIFICATION_RULES = 100


def _path(root, name):
    if not isinstance(root, str) or not root or not os.path.isdir(root):
        raise ValueError("root invalido")
    return os.path.join(root, ".email-agent", name)


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as exc:
        raise RuntimeError("almacen de notificaciones ilegible") from exc
    return value


def _write(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.replace(temporary, path)


def _valid_query(query):
    if not isinstance(query, str) or not query.strip():
        return False
    normalized = query.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        return False
    try:
        parse_filter_query(normalized)
    except ValueError:
        return False
    return True


def _valid_rule(rule):
    return (
        isinstance(rule, dict)
        and isinstance(rule.get("name"), str)
        and _NAME_RE.fullmatch(rule["name"]) is not None
        and _valid_query(rule.get("query"))
        and isinstance(rule.get("enabled", True), bool)
        and isinstance(rule.get("summary", False), bool)
        and isinstance(rule.get("cooldown_seconds", 0), int)
        and not isinstance(rule.get("cooldown_seconds", 0), bool)
        and 0 <= rule.get("cooldown_seconds", 0) <= 86400
    )


def _valid_state(value):
    return (
        isinstance(value, dict)
        and isinstance(value.get("sent", []), list)
        and all(isinstance(item, str) and item for item in value["sent"])
    )


def list_notification_rules(root):
    value = _read(_path(root, _RULES), {"rules": []})
    rules = value.get("rules") if isinstance(value, dict) else None
    if not isinstance(rules, list) or not all(_valid_rule(rule) for rule in rules):
        raise RuntimeError("almacen de notificaciones invalido")
    return rules


def save_notification_rule(root, name, query, enabled=True, summary=False, cooldown_seconds=0):
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError("nombre de regla invalido")
    if not _valid_query(query):
        raise ValueError("filtro invalido")
    normalized_query = query.strip()
    if not isinstance(enabled, bool):
        raise ValueError("enabled invalido")
    if not isinstance(summary, bool):
        raise ValueError("summary invalido")
    if (
        not isinstance(cooldown_seconds, int)
        or isinstance(cooldown_seconds, bool)
        or not 0 <= cooldown_seconds <= 86400
    ):
        raise ValueError("cooldown invalido")
    rules = [rule for rule in list_notification_rules(root) if rule.get("name") != name]
    if len(rules) >= MAX_NOTIFICATION_RULES:
        raise ValueError("limite de reglas de notificacion alcanzado")
    rule = {"name": name, "query": normalized_query, "enabled": enabled}
    if summary:
        rule["summary"] = True
    if cooldown_seconds:
        rule["cooldown_seconds"] = cooldown_seconds
    rules.append(rule)
    _write(_path(root, _RULES), {"rules": rules})
    return name


def delete_notification_rule(root, name):
    rules = list_notification_rules(root)
    remaining = [rule for rule in rules if rule.get("name") != name]
    changed = len(rules) != len(remaining)
    if changed:
        _write(_path(root, _RULES), {"rules": remaining})
    return changed


def set_notification_rule_enabled(root, name, enabled):
    if not isinstance(enabled, bool):
        raise ValueError("enabled invalido")
    rules = list_notification_rules(root)
    found = False
    changed = False
    for rule in rules:
        if rule.get("name") == name:
            found = True
            changed = rule.get("enabled", True) != enabled
            if changed:
                rule["enabled"] = enabled
            break
    if not found:
        raise LookupError("regla no encontrada")
    if changed:
        _write(_path(root, _RULES), {"rules": rules})
    return name


def notification_matches(record, query):
    try:
        return record_matches(record, parse_filter_query(query))
    except (TypeError, ValueError):
        return False


def _record_from_node(path, root):
    """Carga solo el frontmatter y cuerpo local necesarios para probar reglas."""
    record = record_from_markdown(path.read_text(encoding="utf-8"))
    record["path"] = path.relative_to(root).as_posix()
    return record


def preview_notification_rule(root, name, limit=100):
    """Evalua una regla localmente sin escribir estado ni lanzar avisos."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit invalido")
    rule = next((item for item in list_notification_rules(root) if item.get("name") == name), None)
    if rule is None:
        raise LookupError("regla no encontrada")
    root_path = Path(root).resolve()
    emails = root_path / "store" / "emails"
    if not emails.is_dir():
        return {"name": name, "total": 0, "truncated": False, "results": []}
    results = []
    for path in sorted(emails.glob("*.md")):
        record = _record_from_node(path, root_path)
        if notification_matches(record, rule["query"]):
            results.append({
                "path": record["path"],
                "from": record.get("from", ""),
                "subject": record.get("subject", ""),
                "date": record.get("date", ""),
            })
    return {
        "name": name,
        "total": len(results),
        "truncated": len(results) > limit,
        "results": results[:limit],
    }


# Scripts CONSTANTES: el texto del correo jamas se interpola en ellos. En
# Windows y macOS el asunto viaja por variables de entorno (datos, nunca
# codigo parseado); en Linux notify-send lo recibe como argumento tras "--".
_WINDOWS_SCRIPT = (
    "$ws = New-Object -ComObject WScript.Shell; "
    "[void]$ws.Popup($env:EMAIL_AGENT_NOTIFY_BODY, 5, $env:EMAIL_AGENT_NOTIFY_TITLE, 64)"
)
_MACOS_SCRIPT = (
    'display notification (system attribute "EMAIL_AGENT_NOTIFY_BODY") '
    'with title (system attribute "EMAIL_AGENT_NOTIFY_TITLE")'
)
_ENV_TITLE = "EMAIL_AGENT_NOTIFY_TITLE"
_ENV_BODY = "EMAIL_AGENT_NOTIFY_BODY"


def _data_env(title, body):
    env = dict(os.environ)
    env[_ENV_TITLE] = title
    env[_ENV_BODY] = body
    return env


def _desktop_notify(title, body):
    system = platform.system()
    if system == "Windows":
        encoded = base64.b64encode(_WINDOWS_SCRIPT.encode("utf-16-le")).decode("ascii")
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            env=_data_env(title, body),
        )
        return "windows"
    if system == "Darwin":
        subprocess.Popen(["osascript", "-e", _MACOS_SCRIPT], env=_data_env(title, body))
        return "macos"
    subprocess.Popen(["notify-send", "--", title, body])
    return "linux"


def notify_new_records(root, records, notifier=None):
    rules = [rule for rule in list_notification_rules(root) if rule.get("enabled", True)]
    state = _read(_path(root, _STATE), {"sent": []})
    if not _valid_state(state):
        raise RuntimeError("almacen de notificaciones invalido")
    sent = set(state["sent"])
    notifier = notifier or _desktop_notify
    notified = 0
    failures = 0
    now = int(time())
    summaries = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        identity = str(record.get("raw_sha256", ""))
        if not identity or identity in sent:
            continue
        matches = [rule for rule in rules if notification_matches(record, rule.get("query", ""))]
        if not matches:
            continue
        rule = matches[0]
        cooldown = rule.get("cooldown_seconds", 0)
        last_notified = state.get("last_notified", {}).get(rule["name"], 0)
        if cooldown and now - last_notified < cooldown:
            sent.add(identity)
            continue
        if rule.get("summary", False):
            summaries.setdefault(rule["name"], []).append(identity)
            continue
        subject = str(record.get("subject", "")) or "Nuevo correo"
        try:
            notifier("Email Agent", subject)
        except Exception:
            failures += 1
            continue
        sent.add(identity)
        notified += 1
        if cooldown:
            state.setdefault("last_notified", {})[rule["name"]] = now
    for name, identities in summaries.items():
        try:
            notifier("Email Agent", f"{len(identities)} correos nuevos coinciden con la regla {name}")
        except Exception:
            failures += 1
            continue
        sent.update(identities)
        rule = next(item for item in rules if item["name"] == name)
        if rule.get("cooldown_seconds", 0):
            state.setdefault("last_notified", {})[name] = now
        notified += 1
    persisted_state = {"sent": sorted(sent)[-5000:]}
    if state.get("last_notified"):
        persisted_state["last_notified"] = state["last_notified"]
    _write(_path(root, _STATE), persisted_state)
    if failures:
        raise RuntimeError("fallo al emitir notificaciones")
    return notified
