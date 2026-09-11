"""Puerta antivirus para bytes de adjuntos, sin filtrar contenido en errores."""

import shutil
import subprocess


class AntivirusError(Exception):
    """Resultado seguro y nominal del escaneo antivirus."""

    def __init__(self, status):
        self.status = status
        super().__init__(status)


def scan_bytes(content, scanner=None, *, max_bytes=25 * 1024 * 1024):
    """Devuelve ``clean``, ``infected``, ``unavailable`` o ``error``.

    `scanner` recibe bytes y existe para pruebas/adaptadores locales. El
    adaptador por defecto usa ClamAV por stdin, sin crear archivos temporales.
    """
    if not isinstance(content, (bytes, bytearray)):
        return "error"
    if max_bytes is not None and len(content) > max_bytes:
        return "error"
    if scanner is not None:
        try:
            result = scanner(bytes(content))
        except Exception:
            return "error"
        return result if result in {"clean", "infected"} else "error"
    executable = shutil.which("clamscan")
    if not executable:
        return "unavailable"
    try:
        result = subprocess.run(
            [executable, "--no-summary", "--stdout", "-"],
            input=bytes(content),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "error"
    if result.returncode == 0:
        return "clean"
    if result.returncode == 1:
        return "infected"
    return "error"
