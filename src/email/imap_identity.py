"""Mailbox identity checks before using persistent IMAP UIDs."""


def selected_uidvalidity(connection):
    kind, values = connection.response('UIDVALIDITY')
    if kind not in ('UIDVALIDITY', b'UIDVALIDITY') or not values or len(values) != 1:
        raise RuntimeError('UIDVALIDITY unavailable')
    value = values[0]
    if isinstance(value, bytes):
        value = value.decode('ascii')
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise RuntimeError('UIDVALIDITY invalid')
    number = int(value)
    if not 0 < number <= 4294967295:
        raise RuntimeError('UIDVALIDITY invalid')
    return number


def require_uidvalidity(connection, expected):
    if isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0:
        raise RuntimeError('legacy remote reference; synchronization required')
    current = selected_uidvalidity(connection)
    if current != expected:
        raise RuntimeError('mailbox identity changed; synchronization required')
    return current
