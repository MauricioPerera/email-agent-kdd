"""Sandbox absence must never launch an unrestricted parser."""

import pytest
from src.email import pdf_sandbox


@pytest.mark.parametrize('platform', ['win32', 'darwin'])
def test_unsupported_platform_does_not_start_process(monkeypatch, platform):
    monkeypatch.setattr(pdf_sandbox.sys, 'platform', platform)
    def forbidden(*args, **kwargs):
        raise AssertionError('unrestricted process launch')
    monkeypatch.setattr(pdf_sandbox.subprocess, 'run', forbidden)
    with pytest.raises(pdf_sandbox.SandboxUnavailable):
        pdf_sandbox.run_pdf(b'%PDF-synthetic')


def test_missing_tools_do_not_start_process(monkeypatch):
    monkeypatch.setattr(pdf_sandbox.sys, 'platform', 'linux')
    monkeypatch.setattr(pdf_sandbox.shutil, 'which', lambda name: None)
    with pytest.raises(pdf_sandbox.SandboxUnavailable):
        pdf_sandbox.run_pdf(b'%PDF-synthetic')


def test_runtime_refusal_is_reported_as_sandbox_unavailable(monkeypatch):
    import subprocess
    monkeypatch.setattr(pdf_sandbox, 'linux_command', lambda _: ['sandbox'])
    monkeypatch.setattr(pdf_sandbox.subprocess, 'run',
                        lambda *args, **kwargs: subprocess.CompletedProcess(args, 1))
    with pytest.raises(pdf_sandbox.SandboxUnavailable):
        pdf_sandbox.run_pdf(b'%PDF-synthetic')
