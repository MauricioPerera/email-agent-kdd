"""Secretos locales via referencias keychain:// (macOS Keychain).

El secreto vive solo en memoria: jamas se imprime, escribe a disco, loguea
ni aparece en mensajes de error. store devuelve SOLO la referencia
`keychain://<label>`; resolve devuelve el secreto VERBATIM. Backend nativo
sin dependencias de terceros: el CLI `security` de macOS, invocado SIN
shell y con el secreto SOLO por stdin (nunca en argv, que es visible en
`ps`). En no-macOS o si `security` no existe, PARAR con RuntimeError
generico, sin fallback ni alternativa insegura.
"""

import re
import shutil
import subprocess
import sys

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REF_PREFIX = "keychain://"
_SERVICE = "email-agent"
_SUBPROCESS_TIMEOUT = 10  # segundos; un llavero bloqueado no debe colgar la GUI
_NOT_AVAILABLE = (
    "PARAR: el almacenamiento seguro de macOS (Keychain) "
    "no esta disponible en este sistema; no hay fallback"
)


def _run_security(argv, stdin=None):
    """Invocar `security` sin shell; devuelve (returncode, stdout, stderr).

    Con timeout: si el llavero esta bloqueado y `security` se queda
    esperando desbloqueo, se devuelve 124 (PARAR) en lugar de colgarse.
    """
    try:
        completed = subprocess.run(
            ["security", *argv],
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_SUBPROCESS_TIMEOUT,
        )
    except OSError:
        return 1, b"", b""
    except subprocess.TimeoutExpired:
        return 124, b"", b""
    return completed.returncode, completed.stdout, completed.stderr


class _KeychainBackend:
    """Backend real: `security add/find/delete-generic-password`.

    El secreto viaja por stdin; argv solo lleva service/account/etiqueta
    publica. Los errores son genericos y jamas incluyen stderr.
    """

    def __init__(self, runner=None):
        if sys.platform != "darwin" or shutil.which("security") is None:
            raise RuntimeError(_NOT_AVAILABLE)
        self._run = _run_security if runner is None else runner

    def write(self, label, secret):
        """Guardar/actualizar la contraseña; stdin lleva el secreto dos veces
        porque `security` puede exigir confirmacion al leer de una tuberia."""
        blob = secret.encode("utf-8")
        payload = blob + b"\n" + blob + b"\n"
        argv = [
            "add-generic-password", "-U",
            "-a", _SERVICE, "-s", label, "-w",
        ]
        code, _out, _err = self._run(argv, stdin=payload)
        if code != 0:
            raise RuntimeError(_NOT_AVAILABLE)

    def read(self, label):
        code, out, _err = self._run(
            ["find-generic-password", "-a", _SERVICE, "-s", label, "-w"]
        )
        if code == 124:  # timeout: el llavero no respondio; PARAR
            raise RuntimeError(_NOT_AVAILABLE)
        if code != 0:
            raise LookupError("credencial ausente")
        try:
            value = out.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("credencial ausente o vacia") from None
        if value.endswith("\n"):
            value = value[:-1]
        if value == "":
            raise ValueError("credencial ausente o vacia")
        return value

    def delete(self, label):
        """Eliminar la entrada; ausente se considera ya desvinculada."""
        code, _out, _err = self._run(
            ["delete-generic-password", "-a", _SERVICE, "-s", label]
        )
        if code != 0 and code != 44:  # 44 = item not found
            raise RuntimeError(_NOT_AVAILABLE)


def store_keychain_secret(label: str, secret: str, runner=None) -> str:
    """Valida label/secret, persiste el secreto y devuelve solo la ref."""
    if not isinstance(label, str) or _LABEL_RE.match(label) is None:
        raise ValueError("etiqueta invalida")
    if not isinstance(secret, str) or secret == "":
        raise ValueError("secreto invalido")
    backend = _KeychainBackend(runner)
    backend.write(label, secret)
    return _REF_PREFIX + label


def resolve_keychain_secret(ref: str, runner=None) -> str:
    """Valida la referencia keychain://<label> y devuelve el secreto verbatim."""
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(_REF_PREFIX):]
    if _LABEL_RE.match(label) is None:
        raise ValueError("referencia invalida")
    backend = _KeychainBackend(runner)
    try:
        value = backend.read(label)
    except LookupError:
        raise ValueError("credencial ausente") from None
    if not isinstance(value, str) or value == "":
        raise ValueError("credencial ausente o vacia")
    return value


def delete_keychain_secret(ref: str, runner=None) -> None:
    """Eliminar una referencia keychain:// sin exponer el secreto."""
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(_REF_PREFIX):]
    if _LABEL_RE.match(label) is None:
        raise ValueError("referencia invalida")
    backend = _KeychainBackend(runner)
    backend.delete(label)