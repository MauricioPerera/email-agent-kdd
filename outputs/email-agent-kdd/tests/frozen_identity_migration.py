import pytest
from src.email.persist_at import persist_email_okf_at


def test_resync_preserves_annotations_and_attachment_state(tmp_path):
    node = tmp_path / 'mail.md'
    node.write_text('---\naccount_id: test\nraw_sha256: abc\nimap_uid: 2\n'
                    'note: preserve\nattachments:\n  - stored: true\n---\nbody', encoding='utf-8')
    record = dict(account_id='test', raw_sha256='abc', body='body',
                  imap_uid=80, uidvalidity=123, mailbox='INBOX')
    persist_email_okf_at(record, str(tmp_path), 'mail.md')
    text = node.read_text(encoding='utf-8')
    assert 'imap_uid: 80\n' in text and 'uidvalidity: 123\n' in text
    assert 'note: preserve\nattachments:\n  - stored: true\n' in text
    assert text.endswith('---\nbody')
    record['uidvalidity'] = 124
    persist_email_okf_at(record, str(tmp_path), 'mail.md')
    assert 'uidvalidity: 124\n' in node.read_text(encoding='utf-8')


def test_migration_refuses_another_account(tmp_path):
    node = tmp_path / 'mail.md'
    original = '---\naccount_id: other\nraw_sha256: abc\n---\nbody'
    node.write_text(original, encoding='utf-8')
    with pytest.raises(OSError):
        persist_email_okf_at(dict(account_id='test', raw_sha256='abc', body='body',
                                 imap_uid=80, uidvalidity=123, mailbox='INBOX'), str(tmp_path), 'mail.md')
    assert node.read_text(encoding='utf-8') == original
