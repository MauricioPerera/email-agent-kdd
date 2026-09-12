"""Run real installer scripts against synthetic downloads, without pip effects."""
import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[3]
WHEELS = ('email_agent_cli-0.2.0-py3-none-any.whl', 'pypdf-6.18.1-py3-none-any.whl',
          'typing_extensions-4.16.0-py3-none-any.whl')


@pytest.mark.parametrize('fault', ['none', 'app', 'dependency', 'typing', 'missing', 'duplicate'])
def test_verified_installer_blocks_bad_downloads(tmp_path, fault):
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    rows = []
    for name in WHEELS:
        content = b'synthetic-wheel-not-installed'
        (downloads / name).write_bytes(content)
        rows.append(hashlib.sha256(content).hexdigest() + '  ' + name)
    if fault in ('app', 'dependency', 'typing'):
        (downloads / WHEELS[('app', 'dependency', 'typing').index(fault)]).write_bytes(b'tampered')
    if fault == 'missing':
        rows.pop()
    if fault == 'duplicate':
        rows.append(rows[-1])
    (downloads / 'SHA256SUMS.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    log = tmp_path / 'pip.log'
    env = dict(os.environ, RELEASE_FIXTURE=str(downloads), RELEASE_INSTALL_LOG=str(log))
    if sys.platform == 'win32':
        shell = shutil.which('pwsh') or shutil.which('powershell')
        assert shell, 'PowerShell required for Windows installer test'
        script = tmp_path / 'harness.ps1'
        installer = str(REPO / 'installers' / 'install.ps1').replace("'", "''")
        script.write_text('''
function python {
  if ($args -contains 'install') { Add-Content -LiteralPath $env:RELEASE_INSTALL_LOG -Value ($args -join ' ') }
  $global:LASTEXITCODE = 0
}
function email-agent { $global:LASTEXITCODE = 0 }
function Invoke-WebRequest {
  param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
  $name = ($Uri -split '/')[-1]
  Copy-Item -LiteralPath (Join-Path $env:RELEASE_FIXTURE $name) -Destination $OutFile
}
''' + "& '" + installer + "'\n", encoding='utf-8')
        command = [shell, '-NoProfile', '-File', str(script)]
    else:
        fake_bin = tmp_path / 'bin'
        fake_bin.mkdir()
        helper = tmp_path / 'fake_commands.py'
        helper.write_text('''
import os, pathlib, shutil, sys
command, *args = sys.argv[1:]
if command == 'curl':
    url = args[1]
    shutil.copyfile(pathlib.Path(os.environ['RELEASE_FIXTURE']) / url.rsplit('/', 1)[-1], args[args.index('-o') + 1])
elif command == 'python3' and 'install' in args:
    pathlib.Path(os.environ['RELEASE_INSTALL_LOG']).write_text(' '.join(args))
''', encoding='utf-8')
        for name in ('python3', 'curl', 'email-agent'):
            executable = fake_bin / name
            executable.write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' +
                                  shlex.quote(str(helper)) + ' ' + name + ' "$@"\n', encoding='utf-8')
            executable.chmod(0o755)
        env['PATH'] = str(fake_bin) + os.pathsep + env['PATH']
        command = ['sh', str(REPO / 'installers' / 'install.sh')]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
    if fault == 'none':
        assert result.returncode == 0, result.stdout + result.stderr
        invocation = log.read_text()
        assert '--no-index' in invocation
        assert all(name in invocation for name in WHEELS)
    else:
        assert result.returncode != 0
        assert not log.exists(), 'pip must not run before all hashes are valid'
