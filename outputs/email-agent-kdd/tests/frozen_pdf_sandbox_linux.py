"""Real Linux sandbox probes, no production credentials or documents."""

import os
import subprocess
import sys
import tempfile

import pytest
from src.email.pdf_sandbox import linux_command

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux sandbox integration')


@pytest.mark.parametrize('encrypted,pages', [(True, 1), (False, 101)])
def test_pdf_policy_rejects_encryption_and_page_overflow(encrypted, pages):
    from io import BytesIO
    from pypdf import PdfWriter
    from src.email.pdf_sandbox import run_pdf
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt('synthetic-password')
    data = BytesIO()
    writer.write(data)
    result = run_pdf(data.getvalue())
    assert result.returncode != 0
    assert b'pdf-rejected' in result.stdout


def test_kernel_bounds_stdout_file(tmp_path):
    worker = tmp_path / 'output.py'
    worker.write_text('import os\nwhile True: os.write(1,b"x"*65536)\n', encoding='utf-8')
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(linux_command(worker), stdout=output,
                                stderr=subprocess.DEVNULL, timeout=10)
        assert result.returncode != 0
        assert output.tell() == 24 * 1024 * 1024


def test_runner_terminates_stalled_worker(tmp_path, monkeypatch):
    from src.email import pdf_sandbox
    import time
    worker = tmp_path / 'stalled.py'
    worker.write_text('import time\ntime.sleep(120)\n', encoding='utf-8')
    command = linux_command(worker)
    monkeypatch.setattr(pdf_sandbox, 'linux_command', lambda _: command)
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        pdf_sandbox.run_pdf(b'')
    assert 14 <= time.monotonic() - start < 22


def test_sandbox_denies_network_host_file_and_environment(tmp_path):
    secret = tmp_path / 'sentinel.txt'
    secret.write_text('synthetic sentinel', encoding='utf-8')
    worker = tmp_path / 'probe.py'
    worker.write_text(
        'import os,socket\n'
        'assert "EMAIL_AGENT_SENTINEL" not in os.environ\n'
        f'assert not os.path.exists({str(secret)!r})\n'
        's=socket.socket(); s.settimeout(1)\n'
        'try:\n s.connect(("192.0.2.1",80))\n'
        'except OSError:\n pass\n'
        'else:\n raise AssertionError("network accessible")\n'
        'print("isolated")\n', encoding='utf-8')
    result = subprocess.run(linux_command(worker), capture_output=True, timeout=10,
                            env=dict(os.environ, EMAIL_AGENT_SENTINEL='synthetic'))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b'isolated'


def test_sandbox_enforces_memory_limit(tmp_path):
    worker = tmp_path / 'memory.py'
    worker.write_text('try:\n x=bytearray(300*1024*1024)\n'
                      'except MemoryError:\n print("limited")\n'
                      'else:\n raise AssertionError("memory unrestricted")\n', encoding='utf-8')
    result = subprocess.run(linux_command(worker), capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b'limited'
