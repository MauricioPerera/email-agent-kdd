"""Secretos locales via referencias secretservice:// (Linux Secret Service).

El secreto vive solo en memoria: jamas se imprime, escribe a disco, loguea
ni aparece en mensajes de error. store devuelve SOLO la referencia
`secretservice://<label>`; resolve devuelve el secreto VERBATIM. Backend
nativo sin dependencias de terceros: `secret-tool` (libsecret, cliente del
Secret Service de freedesktop), invocado SIN shell y con el secreto SOLO
por stdin (nunca en argv). Los atributos de busqueda incluyen la etiqueta
(`username=<label>`), asi que con varias cuentas cada item se distingue:
`lookup` devuelve el secreto de ESA cuenta y `clear` borra SOLO su item.
Con timeout: si el daemon no responde, PARAR en lugar de colgarse. En
no-Linux o si `secret-tool` no existe, PARAR con RuntimeError generico,
sin fallback ni alternativa insegura.
"""

import re
import shutil
import subprocess
import sys

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REF_PREFIX = "secretservice://"
# Atributos fijos del esquema; la etiqueta viaja ademas como atributo
# `username` (ver _attributes) para que cada cuenta tenga SU item.
_BASE_ATTRIBUTES = ("application", "email-agent", "service", "email-agent")
_SUBPROCESS_TIMEOUT = 10  # segundos; un daemon colgado no debe colgar la GUI
_NOT_AVAILABLE = (
    "PARAR: el almacenamiento seguro de Linux (Secret Service) "
    "no esta disponible en este sistema; no hay fallback"
)


def _attributes(label: str):
    """Atributos de busqueda que identifican UNA sola cuenta.

    La etiqueta (que deriva del account_id) entra como atributo
    `username`, no solo como `--label`: asi `lookup`/`clear` solo
    casan con el item de ESA cuenta, y con varias cuentas jamas se
    resuelve el secreto equivocado ni se limpia el item ambiguo.
    """
    return _BASE_ATTRIBUTES + ("username", label)


def _run_secret_tool(argv, stdin=None):
    """Invocar `secret-tool` sin shell; devuelve (returncode, stdout, stderr).

    Con timeout: si el daemon no responde se devuelve 124 (PARAR) en
    lugar de dejar el proceso colgado esperando desbloqueo.
    """
    try:
        completed = subprocess.run(
            ["secret-tool", *argv],
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


class _SecretServiceBackend:
    """Backend real: `secret-tool store/lookup/clear`.

    `store` recibe los atributos (incluida la etiqueta) en argv y el
    secreto por stdin con `--label=<label>`; `lookup` imprime el secreto
    en stdout; los errores son genericos y jamas incluyen stderr. El
    chequeo de plataforma/herramienta corre SOLO sin `runner`: un runner
    inyectado es el unico canal de pruebas offline (doble en memoria).
    """

    def __init__(self, runner=None):
        if runner is None and (
            not sys.platform.startswith("linux")
            or shutil.which("secret-tool") is None
        ):
            raise RuntimeError(_NOT_AVAILABLE)
        self._run = _run_secret_tool if runner is None else runner

    def write(self, label, secret):
        blob = secret.encode("utf-8")
        argv = ["store", "--label=" + label, *_attributes(label)]
        code, _out, _err = self._run(argv, stdin=blob)
        if code != 0:
            raise RuntimeError(_NOT_AVAILABLE)

    def read(self, label):
        argv = ["lookup", *_attributes(label)]
        code, out, _err = self._run(argv)
        if code == 124:  # timeout: el daemon no respondio; PARAR
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
        """`clear` no falla aunque la entrada no exista."""
        argv = ["clear", *_attributes(label)]
        code, _out, _err = self._run(argv)
        if code != 0:
            raise RuntimeError(_NOT_AVAILABLE)


def store_secretservice_secret(label: str, secret: str, runner=None) -> str:
    """Valida label/secret, persiste el secreto y devuelve solo la ref."""
    if not isinstance(label, str) or _LABEL_RE.match(label) is None:
        raise ValueError("etiqueta invalida")
    if not isinstance(secret, str) or secret == "":
        raise ValueError("secreto invalido")
    backend = _SecretServiceBackend(runner)
    backend.write(label, secret)
    return _REF_PREFIX + label


def resolve_secretservice_secret(ref: str, runner=None) -> str:
    """Valida secretservice://<label> y devuelve el secreto verbatim."""
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(_REF_PREFIX):]
    if _LABEL_RE.match(label) is None:
        raise ValueError("referencia invalida")
    backend = _SecretServiceBackend(runner)
    try:
        value = backend.read(label)
    except LookupError:
        raise ValueError("credencial ausente") from None
    if not isinstance(value, str) or value == "":
        raise ValueError("credencial ausente o vacia")
    return value


def delete_secretservice_secret(ref: str, runner=None) -> None:
    """Eliminar una referencia secretservice:// sin exponer el secreto."""
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(_REF_PREFIX):]
    if _LABEL_RE.match(label) is None:
        raise ValueError("referencia invalida")
    backend = _SecretServiceBackend(runner)
    backend.delete(label)