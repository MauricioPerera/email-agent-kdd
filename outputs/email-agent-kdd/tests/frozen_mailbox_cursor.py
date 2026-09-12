"""V2 cursor migration preserves legacy data and scopes identities."""

from src.email.cursor_store import load_mailbox_cursor, save_mailbox_cursor


def test_legacy_cursor_is_preserved_but_never_reused(tmp_path):
    folder = tmp_path / '.email-agent'
    folder.mkdir()
    legacy = folder / 'cursors.json'
    content = b'{"cursors":{"test":11000}}'
    legacy.write_bytes(content)
    assert load_mailbox_cursor(str(tmp_path), 'test', 'INBOX') == {'uid': 0, 'uidvalidity': None}
    save_mailbox_cursor(str(tmp_path), 'test', 'INBOX', 8, 12000)
    assert legacy.read_bytes() == content
    assert load_mailbox_cursor(str(tmp_path), 'test', 'INBOX') == {'uid': 12000, 'uidvalidity': 8}


def test_cursors_are_separate_by_account_and_mailbox(tmp_path):
    root = str(tmp_path)
    save_mailbox_cursor(root, 'a', 'INBOX', 9, 20)
    save_mailbox_cursor(root, 'a', 'Sent', 10, 30)
    save_mailbox_cursor(root, 'b', 'INBOX', 11, 40)
    assert load_mailbox_cursor(root, 'a', 'INBOX')['uid'] == 20
    assert load_mailbox_cursor(root, 'a', 'Sent')['uid'] == 30
    assert load_mailbox_cursor(root, 'b', 'INBOX')['uid'] == 40
    save_mailbox_cursor(root, 'a', 'INBOX', 12, 1)
    assert load_mailbox_cursor(root, 'a', 'INBOX') == {'uid': 1, 'uidvalidity': 12}
