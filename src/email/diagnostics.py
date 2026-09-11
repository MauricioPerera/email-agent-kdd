"""Diagnostico local y de solo lectura para preparar el primer uso."""

import importlib.util
import shutil
import sys
from pathlib import Path


def _check(name, status, detail, required=True):
    return {"name": name, "status": status, "detail": detail, "required": required}


def run_diagnostics(root=None):
    """Devuelve checks seguros sin red, credenciales ni escrituras."""
    checks = []
    supported = sys.platform == "win32" or sys.platform == "darwin" or sys.platform.startswith("linux")
    checks.append(_check(
        "platform",
        "ok" if supported else "error",
        "sistema operativo soportado" if supported else "sistema operativo sin almacén nativo soportado",
    ))
    version_ok = sys.version_info >= (3, 10)
    checks.append(_check(
        "python",
        "ok" if version_ok else "error",
        "Python 3.10 o superior" if version_ok else "se requiere Python 3.10 o superior",
    ))
    pip_ok = importlib.util.find_spec("pip") is not None
    checks.append(_check(
        "pip",
        "ok" if pip_ok else "error",
        "pip disponible" if pip_ok else "pip no está disponible para este Python",
    ))
    tkinter_ok = importlib.util.find_spec("tkinter") is not None
    checks.append(_check(
        "gui",
        "ok" if tkinter_ok else "warning",
        "formulario gráfico disponible" if tkinter_ok else "Tkinter no está disponible; se puede usar el asistente de terminal",
        required=False,
    ))
    if sys.platform == "darwin":
        native_ok, detail = shutil.which("security") is not None, "Keychain disponible" if shutil.which("security") else "falta el comando security"
        native_name = "keychain"
    elif sys.platform.startswith("linux"):
        native_ok, detail = shutil.which("secret-tool") is not None, "Secret Service disponible" if shutil.which("secret-tool") else "falta secret-tool; se requiere libsecret y una sesión de escritorio"
        native_name = "secretservice"
    elif sys.platform == "win32":
        native_ok, detail, native_name = True, "Credential Manager se comprobará al guardar la cuenta", "credential_manager"
    else:
        native_ok, detail, native_name = False, "no hay almacén nativo soportado", "native_store"
    checks.append(_check(native_name, "ok" if native_ok else "error", detail))
    if root is not None:
        root_ok = isinstance(root, str) and bool(root.strip()) and Path(root).is_dir()
        checks.append(_check("root", "ok" if root_ok else "warning", "carpeta local accesible" if root_ok else "la carpeta indicada no existe; se creará durante la configuración", required=False))
    required_errors = [item for item in checks if item["required"] and item["status"] == "error"]
    return {
        "status": "ready" if not required_errors else "needs_attention",
        "checks": checks,
        "next": "Puedes abrir account setup-gui o account setup" if not required_errors else "Corrige los checks marcados como error y vuelve a ejecutar doctor",
    }
