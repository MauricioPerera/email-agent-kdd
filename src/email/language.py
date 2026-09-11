"""Preferencia local de idioma, sin secretos ni datos de correo."""

import json
import locale
import os
from pathlib import Path

SUPPORTED_LANGUAGES = {"es", "en", "pt"}
_PREFERENCES = Path(".email-agent") / "preferences.json"


def normalize_language(value):
    code = str(value or "").lower().replace("_", "-").split("-", 1)[0]
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError("idioma invalido")
    return code


def detect_language():
    """Detecta solo el idioma del sistema; nunca devuelve el valor completo."""
    candidates = [os.environ.get("LC_ALL"), os.environ.get("LANG"), locale.getlocale()[0]]
    for candidate in candidates:
        if candidate:
            code = str(candidate).lower().replace("_", "-").split("-", 1)[0]
            if code in SUPPORTED_LANGUAGES:
                return code
    return "es"


def _path(root):
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root invalido")
    return Path(root) / _PREFERENCES


def load_language(root):
    target = _path(root)
    if not target.exists():
        return detect_language()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return normalize_language(data.get("language"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return detect_language()


def save_language(root, language):
    language = normalize_language(language)
    target = _path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(json.dumps({"language": language}, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    return language
