"""Pruebas frozen offline del registro de inicio automatico (Sprint 13).

Importan el codigo REAL (`src.email.autostart`) y corren sin red y sin
ejecutar schtasks: el unico punto de inyeccion es `subprocess.run` (stub que
registra argv) y `platform.system`. Verifican que la raiz y los argumentos se
serializan de forma segura en los tres formatos (valor de /TR de schtasks,
plist XML de launchd y ExecStart de systemd), que datos hostiles viajan solo
como dato, la validacion de entradas, los fallos y la preservacion del
comportamiento previo.
"""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.email import autostart
from src.email.autostart import (_launchd_plist, _systemd_exec_start,
                                  _systemd_quote, _windows_watch_root,
                                  install_startup, remove_startup,
                                  startup_status)

SPACES_ROOT = "C:\\Usuarios\\Datos Personales"
POSIX_SPACES_ROOT = "/Usuarios/Sobre Mi"

# Rutas hostiles: si alguna se interpretara como markup o comando, el
# serializado real quedaria corrupto. Solo se comprueba que viajan intactas.
HOSTILE_ROOTS = [
    'C:\\dir"; schtasks /Delete /TN Todo /F; "',
    'C:\\dir\\" & whoami',
    "$(Start-Process calc.exe) & pause",
    "C:\\a <b>&amp;</b> c",
    "C:\\pro\\gram' & 'files",
    "C:\\100% de %h y %U",
    "/opt/mi \\backslash\\ dir",
    "C:\\correo 日本語 — € Ñoño 📧",
]

CONTROL_ROOTS = ["C:\\linea\nsalto", "C:\\tab\tx", "C:\\cr\rx", "C:\\nul\x00x", "C:\\del\x7fx"]


class _RunStub:
    def __init__(self, returncode=0, error=None):
        self.calls = []
        self.returncode = returncode
        self.error = error

    def __call__(self, argv, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append({"argv": list(argv), "kwargs": kwargs})
        return subprocess.CompletedProcess(argv, self.returncode, "", "")


@pytest.fixture
def run_stub(monkeypatch):
    stub = _RunStub()
    monkeypatch.setattr(autostart.subprocess, "run", stub)
    return stub


def _set_platform(monkeypatch, system):
    monkeypatch.setattr(autostart.platform, "system", lambda: system)


@pytest.fixture
def home_stub(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path(tmp_path)))
    return tmp_path


@pytest.fixture
def abspath_identity(monkeypatch):
    """Desactiva abspath (en el host real ya normaliza y quita la barra final)."""
    monkeypatch.setattr(autostart.os.path, "abspath", lambda value: value)


def _tr_value(call):
    argv = call["argv"]
    return argv[argv.index("/TR") + 1]


def _expected_args(root, unread=False, interval=300, limit=50):
    args = ["PY", "-m", "src.email", "watch", root, "cuenta1",
            "--every", str(interval), "--limit", str(limit)]
    if unread:
        args.append("--unread")
    return args


# --- Windows: /TR citado por list2cmdline --------------------------------


def test_windows_install_uses_schtasks_with_quoted_tr(run_stub, monkeypatch, abspath_identity):
    _set_platform(monkeypatch, "Windows")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    assert install_startup(SPACES_ROOT, "cuenta1") == "EmailAgent-cuenta1"
    assert len(run_stub.calls) == 1
    argv = run_stub.calls[0]["argv"]
    assert argv[0] == "schtasks"
    assert argv[argv.index("/TN") + 1] == "EmailAgent-cuenta1"
    assert argv[argv.index("/SC") + 1] == "ONLOGON"
    assert argv[-1] == "/F"
    expected = subprocess.list2cmdline(
        _expected_args(SPACES_ROOT))
    assert _tr_value(run_stub.calls[0]) == expected


def test_windows_tr_preserves_spaces_quotes_and_unicode(run_stub, monkeypatch, abspath_identity):
    _set_platform(monkeypatch, "Windows")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    for root in HOSTILE_ROOTS:
        run_stub.calls.clear()
        install_startup(root, "cuenta1")
        tr = _tr_value(run_stub.calls[0])
        assert tr == subprocess.list2cmdline(_expected_args(root))


def test_windows_tr_never_ends_quoted_path_with_backslash(run_stub, monkeypatch, abspath_identity):
    _set_platform(monkeypatch, "Windows")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    install_startup("C:\\dir bar\\", "cuenta1")
    tr = _tr_value(run_stub.calls[0])
    # La contrabarra antes de la comilla de cierre partira el comando.
    assert '\\"' not in tr
    assert 'watch "C:\\dir bar" cuenta1' in tr


def test_windows_drive_root_stays_intact(run_stub, monkeypatch, abspath_identity):
    _set_platform(monkeypatch, "Windows")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    assert _windows_watch_root("C:\\") == "C:\\"
    assert _windows_watch_root("C:\\dir bar\\") == "C:\\dir bar"
    install_startup("C:\\", "cuenta1")
    tr = _tr_value(run_stub.calls[0])
    assert "watch C:\\ cuenta1" in tr


def test_windows_unread_flag_and_custom_options(run_stub, monkeypatch):
    _set_platform(monkeypatch, "Windows")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    install_startup(SPACES_ROOT, "cuenta1", interval=60, limit=7, unread=True)
    tr = _tr_value(run_stub.calls[0])
    assert "--every 60 --limit 7 --unread" in tr


# --- Windows: caracteres de control rechazados ----------------------------


@pytest.mark.parametrize("root", CONTROL_ROOTS)
def test_windows_control_chars_in_root_rejected(run_stub, monkeypatch, root):
    _set_platform(monkeypatch, "Windows")
    with pytest.raises(ValueError):
        install_startup(root, "cuenta1")
    assert run_stub.calls == []


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_control_chars_rejected_on_every_platform(monkeypatch, home_stub, run_stub, system, abspath_identity):
    _set_platform(monkeypatch, system)
    with pytest.raises(ValueError):
        install_startup("C:\\linea\nsalto", "cuenta1")
    # El plist y la unidad quedan intactos: nada se escribio.
    assert list(home_stub.rglob("*")) == []


# --- macOS: plist XML escapado --------------------------------------------


def _plist_document(home, account_id="cuenta1"):
    return ET.parse(home / "Library" / "LaunchAgents" / ("EmailAgent-" + account_id + ".plist")).getroot()


def _plist_value(plist, name):
    """Nodo de valor emparejado con <key>NAME</key> (ElementTree no soporta
    predicados con el nodo actual)."""
    children = list(plist.find("dict"))
    for index, node in enumerate(children):
        if node.tag == "key" and node.text == name:
            return children[index + 1]
    raise AssertionError("clave ausente: " + name)


def _plist_args(plist):
    return [node.text for node in _plist_value(plist, "ProgramArguments")]


def test_macos_plist_is_valid_xml_with_verbatim_args(monkeypatch, home_stub, abspath_identity):
    _set_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    path = install_startup(POSIX_SPACES_ROOT, "cuenta1", interval=45, limit=3, unread=True)
    assert path == str(home_stub / "Library" / "LaunchAgents" / "EmailAgent-cuenta1.plist")
    plist = _plist_document(home_stub)
    assert plist.tag == "plist"
    assert _plist_value(plist, "Label").text == "EmailAgent-cuenta1"
    assert _plist_args(plist) == _expected_args(POSIX_SPACES_ROOT, unread=True, interval=45, limit=3)
    assert _plist_value(plist, "RunAtLoad").tag == "true"


@pytest.mark.parametrize("root", HOSTILE_ROOTS)
def test_macos_hostile_roots_survive_as_data(monkeypatch, home_stub, abspath_identity, root):
    _set_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    install_startup(root, "cuenta1")
    plist = _plist_document(home_stub)
    args = _plist_args(plist)
    assert args[4] == root


def test_macos_markup_payload_cannot_break_the_plist(monkeypatch, home_stub, abspath_identity):
    _set_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    payload = 'C:\\</string><string>rm -rf ~</string><key>X</key><string>'
    install_startup(payload, "cuenta1")
    plist = _plist_document(home_stub)
    args = _plist_args(plist)
    assert args[4] == payload
    assert len(args) == len(_expected_args(payload))
    # El payload jamas crea claves nuevas: solo Label, ProgramArguments y RunAtLoad.
    keys = [node.text for node in plist.find("dict") if node.tag == "key"]
    assert keys == ["Label", "ProgramArguments", "RunAtLoad"]


def test_macos_install_creates_launchagents_dir(monkeypatch, home_stub, abspath_identity):
    _set_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    install_startup(POSIX_SPACES_ROOT, "cuenta1")
    assert (home_stub / "Library" / "LaunchAgents").is_dir()


# --- Linux: ExecStart de systemd ------------------------------------------


def _split_systemd(exec_start):
    """Mini-parser del escapado citado de systemd: comillas, \\, \" y %%."""
    items, value, quoted, index = [], "", False, 0
    while index < len(exec_start):
        char = exec_start[index]
        if char == '"':
            quoted = not quoted
            index += 1
        elif char == "\\" and index + 1 < len(exec_start):
            value += exec_start[index + 1]
            index += 2
        elif char == "%" and exec_start[index:index + 2] == "%%":
            value += "%"
            index += 2
        elif char == " " and not quoted:
            items.append(value)
            value = ""
            index += 1
        else:
            value += char
            index += 1
    items.append(value)
    return [item for item in items if item != "" or quoted]


def test_linux_exec_start_round_trips_args_verbatim(monkeypatch, home_stub, abspath_identity):
    _set_platform(monkeypatch, "Linux")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    path = install_startup(POSIX_SPACES_ROOT, "cuenta1", interval=90, limit=9, unread=True)
    assert path == str(home_stub / ".config" / "systemd" / "user" / "EmailAgent-cuenta1.service")
    unit = (home_stub / ".config" / "systemd" / "user" / "EmailAgent-cuenta1.service").read_text(encoding="utf-8")
    assert unit.startswith("[Unit]\nDescription=Email Agent\n[Service]\n")
    assert unit.count("\nExecStart=") == 1
    assert "[Install]" not in unit
    exec_start = unit.split("ExecStart=", 1)[1].split("\n", 1)[0]
    assert _split_systemd(exec_start) == _expected_args(POSIX_SPACES_ROOT, unread=True, interval=90, limit=9)


@pytest.mark.parametrize("root", HOSTILE_ROOTS)
def test_linux_hostile_roots_survive_as_data(monkeypatch, home_stub, abspath_identity, root):
    _set_platform(monkeypatch, "Linux")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    install_startup(root, "cuenta1")
    unit = (home_stub / ".config" / "systemd" / "user" / "EmailAgent-cuenta1.service").read_text(encoding="utf-8")
    exec_start = unit.split("ExecStart=", 1)[1].split("\n", 1)[0]
    assert _split_systemd(exec_start)[4] == root


def test_systemd_escaping_rules():
    assert _systemd_quote("C:\\a b") == '"C:\\\\a b"'
    assert _systemd_quote('el "problema"') == '"el \\"problema\\""'
    assert _systemd_quote("50% de %h") == '"50%% de %%h"'
    assert _split_systemd(_systemd_exec_start(["py", "a\\b", 'c"d', "e%f"])) == [
        "py", "a\\b", 'c"d', "e%f"]


def test_systemd_multiline_cannot_inject_a_new_directive(run_stub, monkeypatch, home_stub, abspath_identity):
    _set_platform(monkeypatch, "Linux")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    with pytest.raises(ValueError):
        install_startup("C:\\linea\nWantedBy=hack", "cuenta1")
    assert run_stub.calls == []
    assert not (home_stub / ".config" / "systemd" / "user").exists()


# --- Validaciones ----------------------------------------------------------

BAD_ACCOUNT_IDS = ["", "cuenta uno", "../escape", "cuenta/1", "cuenta;uno",
                   "cuenta'uno", "a" * 65, "cuenta\n", "cuenta\u00e9", 42, None]


@pytest.mark.parametrize("account_id", BAD_ACCOUNT_IDS)
def test_invalid_account_id_rejected_everywhere(run_stub, monkeypatch, home_stub, account_id):
    for system in ("Windows", "Darwin", "Linux"):
        _set_platform(monkeypatch, system)
        with pytest.raises(ValueError):
            install_startup("C:\\raiz", account_id)
        with pytest.raises(ValueError):
            startup_status(account_id)
        with pytest.raises(ValueError):
            remove_startup(account_id)
    assert run_stub.calls == []
    assert list(home_stub.rglob("*")) == []


@pytest.mark.parametrize("interval", [29, 0, -5, True, False, "300", 300.0, None])
def test_invalid_interval_rejected(run_stub, monkeypatch, interval):
    _set_platform(monkeypatch, "Windows")
    with pytest.raises(ValueError):
        install_startup("C:\\raiz", "cuenta1", interval=interval)
    assert run_stub.calls == []


@pytest.mark.parametrize("limit", [0, 101, -1, True, False, "50", 50.0, None])
def test_invalid_limit_rejected(run_stub, monkeypatch, limit):
    _set_platform(monkeypatch, "Windows")
    with pytest.raises(ValueError):
        install_startup("C:\\raiz", "cuenta1", limit=limit)
    assert run_stub.calls == []


@pytest.mark.parametrize("root", ["", None, 42, ["C:\\raiz"]])
def test_invalid_root_rejected(run_stub, monkeypatch, root):
    _set_platform(monkeypatch, "Windows")
    with pytest.raises(ValueError):
        install_startup(root, "cuenta1")
    assert run_stub.calls == []


@pytest.mark.parametrize("system", ["Windows", "Darwin", "Linux"])
def test_defaults_are_every_300_limit_50(run_stub, monkeypatch, home_stub, abspath_identity, system):
    _set_platform(monkeypatch, system)
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    install_startup(SPACES_ROOT, "cuenta1")
    if system == "Windows":
        assert "--every 300 --limit 50" in _tr_value(run_stub.calls[0])
        assert "--unread" not in _tr_value(run_stub.calls[0])
    else:
        marker = home_stub / ("Library/LaunchAgents" if system == "Darwin" else ".config/systemd/user")
        text = next((p.read_text(encoding="utf-8") for p in marker.rglob("*") if p.is_file()), "")
        if system == "Darwin":
            assert "<string>--every</string>" in text and "<string>300</string>" in text
        else:
            assert '"--every" "300"' in text
        assert "--unread" not in text


# --- Fallos ----------------------------------------------------------------


def test_windows_install_failure_propagates(monkeypatch):
    _set_platform(monkeypatch, "Windows")
    failing = _RunStub(error=subprocess.CalledProcessError(1, "schtasks"))
    monkeypatch.setattr(autostart.subprocess, "run", failing)
    with pytest.raises(subprocess.CalledProcessError):
        install_startup(SPACES_ROOT, "cuenta1")


def test_windows_status_reflects_returncode(monkeypatch):
    _set_platform(monkeypatch, "Windows")
    ok = _RunStub(returncode=0)
    monkeypatch.setattr(autostart.subprocess, "run", ok)
    assert startup_status("cuenta1") is True
    missing = _RunStub(returncode=1)
    monkeypatch.setattr(autostart.subprocess, "run", missing)
    assert startup_status("cuenta1") is False


def test_windows_remove_is_best_effort(monkeypatch):
    _set_platform(monkeypatch, "Windows")
    missing = _RunStub(returncode=1)
    monkeypatch.setattr(autostart.subprocess, "run", missing)
    assert remove_startup("cuenta1") is True
    argv = missing.calls[0]["argv"]
    assert argv[0] == "schtasks" and "/Delete" in argv and argv[argv.index("/TN") + 1] == "EmailAgent-cuenta1"


# --- Estado, eliminacion y preservacion ------------------------------------


@pytest.mark.parametrize("system,relative", [
    ("Darwin", "Library/LaunchAgents/EmailAgent-cuenta1.plist"),
    ("Linux", ".config/systemd/user/EmailAgent-cuenta1.service"),
])
def test_status_and_remove_by_file_presence(monkeypatch, home_stub, system, relative):
    _set_platform(monkeypatch, system)
    target = home_stub / relative
    assert startup_status("cuenta1") is False
    assert remove_startup("cuenta1") is False
    target.parent.mkdir(parents=True)
    target.write_text("x", encoding="utf-8")
    assert startup_status("cuenta1") is True
    assert remove_startup("cuenta1") is True
    assert not target.exists()
    assert startup_status("cuenta1") is False


def test_persisted_file_is_utf8_and_untouched_by_platform_quirks(monkeypatch, home_stub, abspath_identity):
    _set_platform(monkeypatch, "Darwin")
    monkeypatch.setattr(autostart.sys, "executable", "PY")
    install_startup(POSIX_SPACES_ROOT, "cuenta1")
    raw = (home_stub / "Library" / "LaunchAgents" / "EmailAgent-cuenta1.plist").read_bytes()
    # El modo texto del host puede traducir los finales de linea.
    assert raw.decode("utf-8").replace("\r\n", "\n") == _launchd_plist(
        "EmailAgent-cuenta1", _expected_args(POSIX_SPACES_ROOT))
