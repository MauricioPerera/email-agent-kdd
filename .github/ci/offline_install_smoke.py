"""Build and install the exact release wheel set into a clean isolated venv.

Network is used only while staging public build/runtime dependencies. The
installation itself has no index and runs outside the source checkout.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def run(args, cwd):
    subprocess.run(args, cwd=cwd, check=True, timeout=180)


def main():
    repository = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='email-release-smoke-') as name:
        root = Path(name)
        wheels = root / 'wheels'
        wheels.mkdir()
        run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', str(repository),
             '--wheel-dir', str(wheels)], root)
        run([sys.executable, '-m', 'pip', 'download', '--no-deps', '--only-binary=:all:',
             'pypdf==6.18.1', 'typing_extensions==4.16.0', '-d', str(wheels)], root)
        expected = {'email_agent_cli-0.2.1-py3-none-any.whl',
                    'pypdf-6.18.1-py3-none-any.whl', 'typing_extensions-4.16.0-py3-none-any.whl'}
        assert {p.name for p in wheels.iterdir()} == expected
        environment = root / 'venv'
        venv.EnvBuilder(with_pip=True).create(environment)
        scripts = environment / ('Scripts' if sys.platform == 'win32' else 'bin')
        python = scripts / ('python.exe' if sys.platform == 'win32' else 'python')
        cli = scripts / ('email-agent.exe' if sys.platform == 'win32' else 'email-agent')
        run([str(python), '-m', 'pip', 'install', '--no-index',
             *[str(wheels / n) for n in sorted(expected)]], root)
        run([str(python), '-I', '-c',
             "import importlib.metadata as m, pypdf, src.email.cli; "
             "assert m.version('email-agent-cli') == '0.2.1'; "
             "assert m.version('pypdf') == '6.18.1'"], root)
        run([str(cli), '--help'], root)
    print('OK: release wheels install offline in a clean environment')


if __name__ == '__main__':
    main()
