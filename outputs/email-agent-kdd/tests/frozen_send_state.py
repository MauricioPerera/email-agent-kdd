"""Durable claims are shared by concurrent callers and survive reconnects."""

from concurrent.futures import ThreadPoolExecutor
import pytest
from src.email.send_state import claim, finish, SendBlocked
from src.email.send_state import read_status


def test_status_read_does_not_create_store(tmp_path):
    assert read_status(tmp_path, 'draft') == 'pending'
    assert list(tmp_path.iterdir()) == []


def test_explicit_retry_can_claim_unknown_once(tmp_path):
    claim(tmp_path, 'draft')
    finish(tmp_path, 'draft', 'unknown')
    claim(tmp_path, 'draft', retry_unknown=True)
    with pytest.raises(SendBlocked):
        claim(tmp_path, 'draft', retry_unknown=True)
    finish(tmp_path, 'draft', 'sent')
    with pytest.raises(SendBlocked):
        claim(tmp_path, 'draft', retry_unknown=True)


def test_retry_cannot_create_new_attempt_without_unknown(tmp_path):
    with pytest.raises(SendBlocked):
        claim(tmp_path, 'draft', retry_unknown=True)


@pytest.mark.parametrize('status', ['sent', 'unknown'])
def test_status_tracks_committed_transitions(tmp_path, status):
    claim(tmp_path, 'draft')
    assert read_status(tmp_path, 'draft') == 'sending'
    finish(tmp_path, 'draft', status)
    assert read_status(tmp_path, 'draft') == status


def test_corrupt_store_is_not_reported_as_pending(tmp_path):
    folder = tmp_path / '.email-agent'
    folder.mkdir()
    (folder / 'send-state.sqlite3').write_bytes(b'corrupt')
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):
        read_status(tmp_path, 'draft')


def test_process_crash_preserves_claim(tmp_path):
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, '-c',
         'import os,sys; from src.email.send_state import claim; '
         'claim(sys.argv[1], "crashed"); os._exit(17)', str(tmp_path)],
        timeout=10,
    )
    assert result.returncode == 17
    with pytest.raises(SendBlocked):
        claim(tmp_path, 'crashed')


@pytest.mark.parametrize('status', ['sent', 'unknown', 'sending'])
def test_repeated_claim_is_blocked(tmp_path, status):
    claim(tmp_path, 'draft')
    if status != 'sending':
        finish(tmp_path, 'draft', status)
    with pytest.raises(SendBlocked):
        claim(tmp_path, 'draft')


def test_concurrent_claim_has_single_winner(tmp_path):
    def attempt(_):
        try:
            claim(tmp_path, 'same-draft')
            return True
        except SendBlocked:
            return False
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(attempt, range(8))) == 1
