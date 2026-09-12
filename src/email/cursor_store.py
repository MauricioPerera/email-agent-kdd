"""Persistencia del cursor de sincronizacion IMAP en root/.email-agent/cursors.json.

Esquema exacto del fichero: {"cursors": {"<account_id>": <uid>}}. Ausencia = 0;
corrupcion (JSON o esquema) = RuntimeError, nunca 0 y nunca sobreescritura.
"""

import json
import os
import sqlite3
from pathlib import Path

_ALLOWED_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"
)


def load_mailbox_cursor(root, account_id, mailbox):
    """V2 cursors never reinterpret legacy sequence numbers as UIDs."""
    _validate_args(root, account_id)
    path = Path(root) / '.email-agent' / 'uid-cursors.sqlite3'
    if not path.exists():
        return {'uid': 0, 'uidvalidity': None}
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        row = connection.execute(
            'SELECT uid, validity FROM cursors WHERE account=? AND mailbox=?',
            (account_id, mailbox),
        ).fetchone()
        return {'uid': row[0], 'uidvalidity': row[1]} if row else {'uid': 0, 'uidvalidity': None}
    finally:
        connection.close()


def save_mailbox_cursor(root, account_id, mailbox, uidvalidity, uid):
    _validate_args(root, account_id)
    if not isinstance(mailbox, str) or not mailbox:
        raise ValueError('mailbox invalido')
    for value, minimum in ((uidvalidity, 1), (uid, 0)):
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= 4294967295:
            raise ValueError('identidad UID invalida')
    path = Path(root) / '.email-agent' / 'uid-cursors.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    try:
        connection.execute('PRAGMA synchronous=FULL')
        with connection:
            connection.execute('CREATE TABLE IF NOT EXISTS cursors '
                               '(account TEXT, mailbox TEXT, validity INTEGER, uid INTEGER, '
                               'PRIMARY KEY(account, mailbox))')
            connection.execute('INSERT OR REPLACE INTO cursors VALUES (?, ?, ?, ?)',
                               (account_id, mailbox, uidvalidity, uid))
    finally:
        connection.close()


def _valid_account(account_id: str) -> bool:
    if account_id in (".", ".."):
        return False
    return 1 <= len(account_id) <= 64 and all(c in _ALLOWED_CHARS for c in account_id)


def _validate_args(root: str, account_id: str) -> None:
    if not isinstance(root, str) or not root:
        raise ValueError("root debe ser un str no vacio")
    if not isinstance(account_id, str) or not _valid_account(account_id):
        raise ValueError("account_id invalido")


def _cursor_path(root: str) -> Path:
    return Path(root) / ".email-agent" / "cursors.json"


def _read_cursors(path: Path) -> dict:
    """Lee y valida el esquema completo; {} si el fichero no existe."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError("cursor store: cursors.json no parsea como JSON") from None
    if (
        not isinstance(data, dict)
        or set(data) != {"cursors"}
        or not isinstance(data["cursors"], dict)
    ):
        raise RuntimeError("cursor store: esquema de cursors.json corrupto")
    for key, value in data["cursors"].items():
        if not isinstance(key, str) or not _valid_account(key):
            raise RuntimeError("cursor store: account_id invalido en cursors.json")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise RuntimeError("cursor store: uid invalido en cursors.json")
    return data["cursors"]


def load_sync_cursor(root: str, account_id: str) -> int:
    """Devuelve el ultimo uid persistido de account_id, o 0 si no hay entrada."""
    _validate_args(root, account_id)
    path = _cursor_path(root)
    if not path.exists():
        return 0
    return _read_cursors(path).get(account_id, 0)


def save_sync_cursor(root: str, account_id: str, uid: int) -> str:
    """Reemplaza la entrada de account_id con uid y escribe el JSON atomicamente."""
    _validate_args(root, account_id)
    if not isinstance(uid, int) or isinstance(uid, bool) or uid < 0:
        raise ValueError("uid debe ser int (no bool) >= 0")
    path = _cursor_path(root)
    cursors = dict(_read_cursors(path))
    cursors[account_id] = uid
    os.makedirs(path.parent, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(
        {"cursors": cursors},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return str(path)
