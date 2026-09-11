"""Registro opcional de Email Agent al inicio del usuario."""

import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

_SAFE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _validate(account_id, interval, limit):
    if not isinstance(account_id, str) or not _SAFE.fullmatch(account_id):
        raise ValueError("account_id invalido")
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 30:
        raise ValueError("interval invalido")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("limit invalido")


def _task_name(account_id):
    return "EmailAgent-" + account_id


def _command(root, account_id, interval, limit, unread):
    args = [sys.executable, "-m", "src.email", "watch", root, account_id,
            "--every", str(interval), "--limit", str(limit)]
    if unread:
        args.append("--unread")
    return args


def startup_status(account_id):
    if not isinstance(account_id, str) or not _SAFE.fullmatch(account_id):
        raise ValueError("account_id invalido")
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
    if not isinstance(root, str) or not root:
        raise ValueError("root invalido")
    command = _command(os.path.abspath(root), account_id, interval, limit, unread)
    system = platform.system()
    task = _task_name(account_id)
    if system == "Windows":
        subprocess.run(["schtasks", "/Create", "/SC", "ONLOGON", "/TN", task,
                        "/TR", subprocess.list2cmdline(command), "/F"], check=True)
        return task
    if system == "Darwin":
        path = Path.home() / "Library" / "LaunchAgents" / (task + ".plist")
        path.parent.mkdir(parents=True, exist_ok=True)
        values = "".join("<string>%s</string>" % value for value in command)
        path.write_text("<?xml version=\"1.0\"?><plist version=\"1.0\"><dict>"
                        "<key>Label</key><string>%s</string><key>ProgramArguments</key>"
                        "<array>%s</array><key>RunAtLoad</key><true/>" 
                        "</dict></plist>" % (task, values), encoding="utf-8")
        return str(path)
    path = Path.home() / ".config" / "systemd" / "user" / (task + ".service")
    path.parent.mkdir(parents=True, exist_ok=True)
    quoted = " ".join('"%s"' % value.replace('"', '\\"') for value in command)
    path.write_text("[Unit]\nDescription=Email Agent\n[Service]\nExecStart=%s\nRestart=always\n" % quoted,
                    encoding="utf-8")
    return str(path)


def remove_startup(account_id):
    if not isinstance(account_id, str) or not _SAFE.fullmatch(account_id):
        raise ValueError("account_id invalido")
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
