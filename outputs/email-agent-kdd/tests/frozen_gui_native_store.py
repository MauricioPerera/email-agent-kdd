"""Contrato frozen del despacho nativo de credenciales de la GUI (Sprint 9).

Congela, SIN importar ninguna funcion objetivo ni tocar almacen nativo:
1) `provision_email_account` con plataforma `darwin` o `linux` en un
   sistema sin ese almacen nativo PARARA con RuntimeError que empieza
   por "PARAR" (no hay fallback a texto plano ni a env://).
2) Al fallar el almacen, `accounts.json` NO se crea: el secreto jamas
   llega a disco.
3) Una plataforma sin soporte tambien PARARA.

Se ejecuta localmente en cualquier OS: en no-macOS el backend de
Keychain PARARA antes de invocar `security`, y en no-Linux el de
Secret Service antes de invocar `secret-tool`.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.email.provision_account import provision_email_account

_ROOT_FILES = ("accounts.json",)


def _fresh_root():
    return tempfile.mkdtemp(prefix="frozen-gui-native-store-")


def _root_files(root):
    return tuple(name for name in _ROOT_FILES if os.path.exists(os.path.join(root, name)))


def test_darwin_without_keychain_stops():
    """Plataforma darwin sin Keychain disponible: PARAR, sin escrituras."""
    root = _fresh_root()
    try:
        try:
            provision_email_account(
                root, "cuenta-x", "custom", "x@example.com",
                "email-cuenta-x", "secreto-frozen", platform="darwin",
            )
        except RuntimeError as exc:
            assert str(exc).startswith("PARAR"), (
                "el mensaje de parada debe empezar por PARAR: " + str(exc)
            )
        else:
            raise AssertionError(
                "darwin sin Keychain debe PARAR con RuntimeError (no fallback)"
            )
        assert _root_files(root) == (), (
            "al PARAR el almacen nativo, accounts.json no debe existir"
        )
    finally:
        for name in _root_files(root):
            os.remove(os.path.join(root, name))


def test_linux_without_secret_service_stops():
    """Plataforma linux sin Secret Service disponible: PARAR, sin escrituras."""
    root = _fresh_root()
    try:
        try:
            provision_email_account(
                root, "cuenta-x", "custom", "x@example.com",
                "email-cuenta-x", "secreto-frozen", platform="linux",
            )
        except RuntimeError as exc:
            assert str(exc).startswith("PARAR"), (
                "el mensaje de parada debe empezar por PARAR: " + str(exc)
            )
        else:
            raise AssertionError(
                "linux sin Secret Service debe PARAR con RuntimeError (no fallback)"
            )
        assert _root_files(root) == (), (
            "al PARAR el almacen nativo, accounts.json no debe existir"
        )
    finally:
        for name in _root_files(root):
            os.remove(os.path.join(root, name))


def test_unsupported_platform_stops():
    """Plataforma sin almacen nativo soportado: PARAR, sin escrituras."""
    root = _fresh_root()
    try:
        try:
            provision_email_account(
                root, "cuenta-x", "custom", "x@example.com",
                "email-cuenta-x", "secreto-frozen", platform="sunos",
            )
        except RuntimeError as exc:
            assert str(exc).startswith("PARAR"), (
                "el mensaje de parada debe empezar por PARAR: " + str(exc)
            )
        else:
            raise AssertionError(
                "plataforma sin soporte debe PARAR con RuntimeError (no fallback)"
            )
        assert _root_files(root) == (), (
            "al PARAR el almacen nativo, accounts.json no debe existir"
        )
    finally:
        for name in _root_files(root):
            os.remove(os.path.join(root, name))


if __name__ == "__main__":
    test_darwin_without_keychain_stops()
    test_linux_without_secret_service_stops()
    test_unsupported_platform_stops()
    print("frozen_gui_native_store: 3/3 PASS")