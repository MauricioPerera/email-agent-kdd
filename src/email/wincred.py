"""Secretos locales via referencias wincred:// (Windows Credential Manager).

El secreto vive solo en memoria: jamas se imprime, escribe a disco, loguea
ni aparece en mensajes de error. store devuelve SOLO la referencia
`wincred://<label>`; resolve devuelve el secreto VERBATIM.
"""

import ctypes
import re

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_REF_PREFIX = "wincred://"
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_NOT_AVAILABLE = (
    "PARAR: el almacenamiento seguro de Windows (Credential Manager) "
    "no esta disponible en este sistema; no hay fallback"
)


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_uint32),
        ("dwHighDateTime", ctypes.c_uint32),
    ]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


class _WindowsCredentialBackend:
    """Backend real: advapi32 CredWriteW/CredReadW/CredFree via ctypes.

    JAMAS subprocess/cmdkey/archivos/env/red. En no-Windows o si advapi32
    no esta disponible, PARAR con RuntimeError generico, sin fallback.
    """

    def __init__(self):
        loader = getattr(ctypes, "WinDLL", None)
        if loader is None:
            raise RuntimeError(_NOT_AVAILABLE)
        try:
            self._advapi32 = loader("advapi32.dll")
            self._advapi32.CredWriteW.restype = ctypes.c_int
            self._advapi32.CredWriteW.argtypes = [
                ctypes.POINTER(_CREDENTIALW),
                ctypes.c_uint32,
            ]
            self._advapi32.CredReadW.restype = ctypes.c_int
            self._advapi32.CredReadW.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
            ]
            self._advapi32.CredDeleteW.restype = ctypes.c_int
            self._advapi32.CredDeleteW.argtypes = [
                ctypes.c_wchar_p,
                ctypes.c_uint32,
                ctypes.c_uint32,
            ]
            self._advapi32.CredFree.restype = None
            self._advapi32.CredFree.argtypes = [ctypes.c_void_p]
        except (OSError, AttributeError, ValueError):
            raise RuntimeError(_NOT_AVAILABLE) from None

    def write(self, label, secret):
        try:
            blob = secret.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("secreto invalido") from None
        cred = _CREDENTIALW()
        cred.Flags = 0
        cred.Type = _CRED_TYPE_GENERIC
        cred.TargetName = label
        cred.Comment = None
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = (ctypes.c_byte * len(blob)).from_buffer_copy(blob)
        cred.Persist = _CRED_PERSIST_LOCAL_MACHINE
        cred.AttributeCount = 0
        cred.Attributes = None
        cred.TargetAlias = None
        cred.UserName = None
        if not self._advapi32.CredWriteW(ctypes.byref(cred), 0):
            raise RuntimeError(_NOT_AVAILABLE)

    def read(self, label):
        cred_ptr = ctypes.POINTER(_CREDENTIALW)()
        if not self._advapi32.CredReadW(
            label, _CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)
        ):
            raise LookupError("credencial ausente")
        try:
            cred = cred_ptr.contents
            size = cred.CredentialBlobSize
            blob = ctypes.string_at(cred.CredentialBlob, size) if size else b""
        finally:
            self._advapi32.CredFree(cred_ptr)
        try:
            return blob.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("credencial ausente o vacia") from None

    def delete(self, label):
        """Eliminar una credencial; ausente se considera ya desvinculada."""
        if not self._advapi32.CredDeleteW(label, _CRED_TYPE_GENERIC, 0):
            # `get_last_error` solo existe en Windows. El fallback permite
            # probar el backend con un stub multiplataforma sin cambiar la
            # semántica real de Windows.
            last_error = getattr(ctypes, "get_last_error", lambda: 1168)()
            if last_error != 1168:  # ERROR_NOT_FOUND
                raise RuntimeError(_NOT_AVAILABLE)


def store_windows_credential(label: str, secret: str, backend=None) -> str:
    """Valida label/secret, persiste el secreto y devuelve solo la ref."""
    if not isinstance(label, str) or _LABEL_RE.match(label) is None:
        raise ValueError("etiqueta invalida")
    if not isinstance(secret, str) or secret == "":
        raise ValueError("secreto invalido")
    if backend is None:
        backend = _WindowsCredentialBackend()
    backend.write(label, secret)
    return _REF_PREFIX + label


def resolve_windows_credential(ref: str, backend=None) -> str:
    """Valida la referencia wincred://<label> y devuelve el secreto verbatim."""
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(_REF_PREFIX):]
    if _LABEL_RE.match(label) is None:
        raise ValueError("referencia invalida")
    if backend is None:
        backend = _WindowsCredentialBackend()
    try:
        value = backend.read(label)
    except LookupError:
        raise ValueError("credencial ausente") from None
    if not isinstance(value, str) or value == "":
        raise ValueError("credencial ausente o vacia")
    return value


def delete_windows_credential(ref: str, backend=None) -> None:
    """Eliminar una referencia wincred:// sin exponer el secreto."""
    if not isinstance(ref, str) or not ref.startswith(_REF_PREFIX):
        raise ValueError("referencia invalida")
    label = ref[len(_REF_PREFIX):]
    if _LABEL_RE.match(label) is None:
        raise ValueError("referencia invalida")
    if backend is None:
        backend = _WindowsCredentialBackend()
    backend.delete(label)
