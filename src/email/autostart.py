"""Registro opcional de Email Agent al inicio del usuario.

Serializacion segura por plataforma: el valor de ``/TR`` de schtasks se
construye con ``subprocess.list2cmdline`` y sin contrabarra final antes de la
comilla de cierre; el plist de launchd escapa todo valor con reglas XML; y el
``ExecStart`` de systemd cita cada argumento con el escapado propio de systemd
(``\\``, ``\"`` y ``%%``). Los datos hostiles (espacios, comillas, Unicode)
viajan siempre como dato: nunca se interpretan como markup, comando ni
especificador.
"""

import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

_SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

_PLIST_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
    '<plist version="1.0">\n'
)


def _validate_account_id(account_id):
    if not isinstance(account_id, str) or not _SAFE.fullmatch(account_id):
        raise ValueError("account_id invalido")


def _validate(account_id, interval, limit):
    _validate_account_id(account_id)
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 30:
        raise ValueError("interval invalido")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit invalido")


def _task_name(account_id):
    return "EmailAgent-" + account_id


def _clean_root(root):
    """Raiz absoluta y sin caracteres de control (ningun formato los admite)."""
    if not isinstance(root, str) or not root:
        raise ValueError("root invalido")
    if _CONTROL.search(root):
        raise ValueError("root invalido")
    return os.path.abspath(root)


def _command(root, account_id, interval, limit, unread):
    args = [sys.executable, "-m", "src.email", "watch", root, account_id,
            "--every", str(interval), "--limit", str(limit)]
    if unread:
        args.append("--unread")
    for value in args:
        if _CONTROL.search(value):
            raise ValueError("root invalido")
    return args


def _windows_watch_root(root):
    """Raiz sin contrabarra final: en el valor de /TR, ``"C:\\dir bar\\"`` se
    leeria como comilla escapada y partiria el comando. Una raiz de unidad se
    conserva intacta porque ``list2cmdline`` nunca la cita."""
    trimmed = root.rstrip("\\/")
    if trimmed.endswith(":"):
        return root
    return trimmed or root


def _launchd_plist(task, command):
    values = "".join("    <string>%s</string>\n" % _xml_escape(value) for value in command)
    return (_PLIST_HEADER
            + "<dict>\n"
            + "    <key>Label</key>\n    <string>%s</string>\n" % _xml_escape(task)
            + "    <key>ProgramArguments</key>\n    <array>\n" + values + "    </array>\n"
            + "    <key>RunAtLoad</key>\n    <true/>\n"
            + "</dict>\n</plist>\n")


def _systemd_quote(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return '"%s"' % escaped


def _systemd_exec_start(command):
    return " ".join(_systemd_quote(value) for value in command)


def startup_status(account_id):
    _validate_account_id(account_id)
    system = platform.system()
    if system == "Windows":
        result = subprocess.run(["schtasks", "/Query", "/TN", _task_name(account_id)],
                                capture_output=True, text=True, check=False)
        return result.returncode == 0
    if system == "Darwin":
        return Path.home().joinpath("Library", "LaunchAgents", _task_name(account_id) + ".plist").is_file()
    return Path.home().joinpath(".config", "systemd", "user", _task_name(account_id) + ".service").is_file()


def install_startup(root, account_id, interval=300, limit=50, unread=False):
    _validate(account_id, interval, limit)
    base = _clean_root(root)
    command = _command(base, account_id, interval, limit, unread)
    system = platform.system()
    task = _task_name(account_id)
    if system == "Windows":
        args = _command(_windows_watch_root(base), account_id, interval, limit, unread)
        subprocess.run(["schtasks", "/Create", "/SC", "ONLOGON", "/TN", task,
                        "/TR", subprocess.list2cmdline(args), "/F"], check=True)
        return task
    if system == "Darwin":
        path = Path.home() / "Library" / "LaunchAgents" / (task + ".plist")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_launchd_plist(task, command), encoding="utf-8")
        return str(path)
    path = Path.home() / ".config" / "systemd" / "user" / (task + ".service")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[Unit]\nDescription=Email Agent\n[Service]\nExecStart=%s\nRestart=always\n"
                    % _systemd_exec_start(command), encoding="utf-8")
    return str(path)


def remove_startup(account_id):
    _validate_account_id(account_id)
    task = _task_name(account_id)
    system = platform.system()
    if system == "Windows":
        subprocess.run(["schtasks", "/Delete", "/TN", task, "/F"], check=False)
        return True
    if system == "Darwin":
        path = Path.home() / "Library" / "LaunchAgents" / (task + ".plist")
    else:
        path = Path.home() / ".config" / "systemd" / "user" / (task + ".service")
    if path.is_file():
        path.unlink()
        return True
    return False