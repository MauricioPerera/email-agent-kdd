"""Linux PDF sandbox with namespaces, resource limits and bounded output."""

import shutil
import sys
import subprocess
import tempfile
from pathlib import Path
import importlib.util


class SandboxUnavailable(RuntimeError):
    pass


def linux_command(worker_path):
    if sys.platform != 'linux':
        raise SandboxUnavailable('PDF sandbox requires a supported Linux runtime')
    bwrap = shutil.which('bwrap')
    prlimit = shutil.which('prlimit')
    if not bwrap or not prlimit:
        raise SandboxUnavailable('PDF sandbox tools unavailable')
    spec = importlib.util.find_spec('pypdf')
    if spec is None or not spec.origin:
        raise SandboxUnavailable('PDF parser unavailable')
    parser = str(Path(spec.origin).parent.resolve())
    return [bwrap, '--unshare-all', '--die-with-parent', '--new-session',
            '--ro-bind', '/usr', '/usr', '--symlink', 'usr/lib', '/lib',
            '--symlink', 'usr/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
            '--tmpfs', '/tmp', '--ro-bind', str(worker_path), '/worker.py',
            '--dir', '/parser', '--ro-bind', parser, '/parser/pypdf',
            '--clearenv', '--setenv', 'PATH', '/usr/bin',
            prlimit, '--as=268435456', '--cpu=15', '--nproc=1', '--fsize=25165824',
            '--', '/usr/bin/python3', '-I', '/worker.py']


def run_pdf(content):
    if len(content) > 25 * 1024 * 1024:
        raise ValueError('PDF input too large')
    command = linux_command(Path(__file__).with_name('pdf_worker.py').resolve())
    # Regular-file stdout permits kernel-enforced output bounds, unlike PIPE.
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(command, input=content, stdout=output,
                                stderr=subprocess.DEVNULL, timeout=15,
                                env={'PATH': '/usr/bin:/bin'}, check=False)
        output.seek(0)
        data = output.read(24 * 1024 * 1024 + 1)
    if len(data) > 24 * 1024 * 1024:
        raise ValueError('PDF output too large')
    if result.returncode != 0 and not data:
        raise SandboxUnavailable('PDF sandbox could not run or exceeded resource limits')
    return subprocess.CompletedProcess(command, result.returncode, data)
