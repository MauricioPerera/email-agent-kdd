"""Durable send claims. A crashed claim is never automatically retried."""

import sqlite3
from pathlib import Path


class SendBlocked(RuntimeError):
    pass


def read_status(root, draft_id):
    """Read without creating a database or changing a send claim."""
    path = Path(root) / '.email-agent' / 'send-state.sqlite3'
    if not path.exists():
        return 'pending'
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        row = connection.execute('SELECT status FROM sends WHERE draft_id=?',
                                 (draft_id,)).fetchone()
        status = row[0] if row else 'pending'
        if status not in ('pending', 'sending', 'sent', 'unknown'):
            raise SendBlocked('estado de envio ilegible')
        return status
    finally:
        connection.close()


def _connect(root):
    directory = Path(root) / '.email-agent'
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(directory / 'send-state.sqlite3', timeout=5)
    connection.execute('PRAGMA synchronous=FULL')
    connection.execute('CREATE TABLE IF NOT EXISTS sends '
                       '(draft_id TEXT PRIMARY KEY, status TEXT NOT NULL)')
    return connection


def claim(root, draft_id, retry_unknown=False):
    connection = _connect(root)
    try:
        with connection:
            if retry_unknown:
                updated = connection.execute(
                    'UPDATE sends SET status=? WHERE draft_id=? AND status=?',
                    ('sending', draft_id, 'unknown'),
                )
                if updated.rowcount != 1:
                    raise SendBlocked('solo se puede reintentar un resultado unknown')
            else:
                connection.execute('INSERT INTO sends VALUES (?, ?)', (draft_id, 'sending'))
    except sqlite3.IntegrityError:
        raise SendBlocked('borrador enviado o de resultado incierto; no reenviar') from None
    finally:
        connection.close()


def finish(root, draft_id, status):
    if status not in ('sent', 'unknown'):
        raise ValueError('estado invalido')
    connection = _connect(root)
    try:
        with connection:
            result = connection.execute(
                'UPDATE sends SET status=? WHERE draft_id=? AND status=?',
                (status, draft_id, 'sending'),
            )
            if result.rowcount != 1:
                raise SendBlocked('transicion de envio invalida')
    finally:
        connection.close()
