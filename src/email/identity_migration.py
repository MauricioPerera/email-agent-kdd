"""Refresh verified remote identity without rewriting local annotations or attachments."""


def refresh_identity(existing, record):
    parts = existing.split('\n---\n', 1)
    if not existing.startswith('---\n') or len(parts) != 2:
        raise ValueError('invalid existing node')
    front, body = parts
    lines = front.splitlines()[1:]
    for key in ('account_id', 'raw_sha256'):
        values = [line.partition(':')[2].strip() for line in lines if line.startswith(key + ':')]
        if values != [str(record[key])]:
            raise ValueError('node does not match verified message')
    if body != str(record['body']):
        raise ValueError('local body differs; preserve node')
    for key in ('imap_uid', 'uidvalidity'):
        value = record.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= 4294967295:
            raise ValueError('unverified remote identity')
    mailbox = record.get('mailbox')
    if not isinstance(mailbox, str) or not mailbox or '\n' in mailbox or '\r' in mailbox:
        raise ValueError('invalid mailbox')
    fields = ('imap_uid', 'uidvalidity', 'mailbox')
    lines = [line for line in lines if not any(line.startswith(key + ':') for key in fields)]
    identity = [key + ': ' + str(record[key]) for key in fields]
    return '---\n' + '\n'.join(identity + lines) + '\n---\n' + body
