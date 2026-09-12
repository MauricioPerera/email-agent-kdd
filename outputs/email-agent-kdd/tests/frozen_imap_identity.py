"""Identity must be established from the selected mailbox, never inferred."""

import pytest
from src.email.imap_identity import selected_uidvalidity, require_uidvalidity


class Mailbox:
    def __init__(self, response):
        self.result = response
    def response(self, key):
        assert key == 'UIDVALIDITY'
        return self.result


@pytest.mark.parametrize('value', [b'123', '123'])
def test_reads_real_imap_response(value):
    assert selected_uidvalidity(Mailbox(('UIDVALIDITY', [value]))) == 123


@pytest.mark.parametrize('response', [(None, [None]), ('UIDVALIDITY', []),
    ('UIDVALIDITY', [b'0']), ('UIDVALIDITY', [b'4294967296']),
    ('UIDVALIDITY', [b'12', b'13']), ('UIDVALIDITY', [True])])
def test_missing_or_invalid_identity_is_rejected(response):
    with pytest.raises(RuntimeError):
        selected_uidvalidity(Mailbox(response))


@pytest.mark.parametrize('expected', [None, True, 122])
def test_legacy_or_changed_identity_is_rejected(expected):
    with pytest.raises(RuntimeError):
        require_uidvalidity(Mailbox(('UIDVALIDITY', [b'123'])), expected)


def test_matching_identity_is_accepted():
    assert require_uidvalidity(Mailbox(('UIDVALIDITY', [b'123'])), 123) == 123


@pytest.mark.parametrize('payload', [[None], [], [b')'], [b'1 (UID 80)']])
def test_vanished_message_is_not_parsed_as_mail(payload):
    from src.email.imap_reader import _raw_message
    with pytest.raises(RuntimeError, match='no message literal'):
        _raw_message(('OK', payload))


def test_expunge_between_pages_does_not_skip_or_fetch_wrong_message(tmp_path):
    from src.email.imap_reader import fetch_imap_messages
    from src.email.cursor_store import load_mailbox_cursor, save_mailbox_cursor
    messages = {20: b'Subject: first\r\n\r\none',
                80: b'Subject: second\r\n\r\ntwo'}
    class Connection(Mailbox):
        def login(self, *args):
            pass
        def select(self, *args, **kwargs):
            return 'OK', [str(len(messages)).encode()]
        def uid(self, command, *args):
            if command == 'SEARCH':
                return 'OK', [' '.join(map(str, sorted(messages))).encode()]
            uid = int(args[0])
            sequence = sorted(messages).index(uid) + 1
            return 'OK', [(f'{sequence} (UID {uid})'.encode(), messages[uid])]
        def close(self):
            pass
        def logout(self):
            pass
    account = {'account_id': 'test', 'email': 'test@example.test'}
    root = str(tmp_path)
    def page():
        cursor = load_mailbox_cursor(root, 'test', 'INBOX')
        return fetch_imap_messages(account,
            {'host': 'example.test', 'username': 'test', 'password': 'synthetic',
             'limit': 1, 'since_uid': cursor['uid'], 'uidvalidity': cursor['uidvalidity']},
            connection_factory=lambda *args: Connection(('UIDVALIDITY', [b'123'])))
    first = page()[0]
    assert first['imap_uid'] == 20
    save_mailbox_cursor(root, 'test', 'INBOX', 123, 20)
    del messages[20]  # UID 80 now has sequence number 1.
    second = page()[0]
    assert second['imap_uid'] == 80
    assert second['subject'] == 'second'
    save_mailbox_cursor(root, 'test', 'INBOX', 123, 80)
    assert page() == []


@pytest.mark.parametrize('fields,expected', [
    ('uidvalidity: 123\n', 123), ('imap_uid: 123\n', None),
    ('uidvalidity: 0\n', None), ('uidvalidity: 1\nuidvalidity: 2\n', None),
    ('  uidvalidity: 123\n', None), ('uidvalidity: 4294967296\n', None),
])
def test_node_generation_must_be_unambiguous(fields, expected):
    from src.email.attachments import read_download_uidvalidity
    assert read_download_uidvalidity('---\n' + fields + '---\nbody') == expected


@pytest.mark.parametrize('generation,expected', [(123, [80]), (122, [20, 80]), (None, [20, 80])])
def test_fetch_uses_uids_and_resets_untrusted_cursor(monkeypatch, generation, expected):
    from src.email import imap_reader
    calls = []
    class Connection(Mailbox):
        def login(self, *args):
            pass
        def select(self, *args, **kwargs):
            return 'OK', [b'2']
        def uid(self, command, *args):
            calls.append((command, args))
            if command == 'SEARCH':
                return 'OK', [b'20 80']
            return 'OK', [(b'1 (UID 80)', b'synthetic')]
        def close(self):
            pass
        def logout(self):
            pass
    monkeypatch.setattr(imap_reader, 'parse_raw_email', lambda raw, account: {})
    result = imap_reader.fetch_imap_messages(
        {'account_id': 'test', 'email': 'test@example.test'},
        {'host': 'example.test', 'username': 'test', 'password': 'synthetic',
         'since_uid': 50, 'uidvalidity': generation},
        connection_factory=lambda *args: Connection(('UIDVALIDITY', [b'123'])),
    )
    assert [item['imap_uid'] for item in result] == expected
    assert all(item['uidvalidity'] == 123 for item in result)
    assert calls[0] == ('SEARCH', (None, 'ALL'))
    assert [args for cmd, args in calls if cmd == 'FETCH'] == [
        (str(uid), '(BODY.PEEK[])') for uid in expected]
