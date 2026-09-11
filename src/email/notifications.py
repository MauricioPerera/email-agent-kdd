"""Reglas y notificaciones locales para correos sincronizados."""

import base64
import json
import os
import platform
import re
import subprocess

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
    return all(not token.casefold().startswith("para:") or bool(token[5:])
               for token in normalized.split())


def _valid_rule(rule):
    return (
        isinstance(rule, dict)
        and isinstance(rule.get("name"), str)
        and _NAME_RE.fullmatch(rule["name"]) is not None
        and _valid_query(rule.get("query"))
        and isinstance(rule.get("enabled", True), bool)
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


def save_notification_rule(root, name, query, enabled=True):
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError("nombre de regla invalido")
    if not _valid_query(query):
        raise ValueError("filtro invalido")
    normalized_query = query.strip()
    if not isinstance(enabled, bool):
        raise ValueError("enabled invalido")
    rules = [rule for rule in list_notification_rules(root) if rule.get("name") != name]
    if len(rules) >= MAX_NOTIFICATION_RULES:
        raise ValueError("limite de reglas de notificacion alcanzado")
    rules.append({"name": name, "query": normalized_query, "enabled": enabled})
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
    if not isinstance(record, dict) or not isinstance(query, str):
        return False
    delivered = {str(value).casefold() for value in record.get("delivered_to", [])}
    searchable = " ".join(str(record.get(key, "")) for key in ("subject", "body"))
    for token in query.split():
        lowered = token.casefold()
        if lowered.startswith("para:"):
            if lowered[5:] not in delivered:
                return False
        elif lowered not in searchable.casefold():
            return False
    return True


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
    for record in records:
        if not isinstance(record, dict):
            continue
        identity = str(record.get("raw_sha256", ""))
        if not identity or identity in sent:
            continue
        if not any(notification_matches(record, rule.get("query", "")) for rule in rules):
            continue
        subject = str(record.get("subject", "")) or "Nuevo correo"
        try:
            notifier("Email Agent", subject)
        except Exception:
            failures += 1
            continue
        sent.add(identity)
        notified += 1
    _write(_path(root, _STATE), {"sent": sorted(sent)[-5000:]})
    if failures:
        raise RuntimeError("fallo al emitir notificaciones")
    return notified
