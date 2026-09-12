"""Missing identity must be rejected before resolving credentials or connecting."""

import pytest
from src.email import cli


@pytest.mark.parametrize('suffix', [[], ['--uidvalidity'], ['--uidvalidity', '0'],
    ['--uidvalidity', '4294967296'], ['--uidvalidity', '1', '--uidvalidity', '2']])
def test_remote_command_requires_valid_generation(monkeypatch, suffix):
    def forbidden(*args):
        raise AssertionError('must not access accounts')
    monkeypatch.setattr(cli, 'load_email_accounts', forbidden)
    assert cli.cli_main(['message', 'remote-delete', '.', 'test', '1', 'Trash', *suffix]) == 2
