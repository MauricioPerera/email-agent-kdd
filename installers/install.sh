#!/usr/bin/env sh
set -eu
SOURCE="${1:-https://github.com/MauricioPerera/email-agent-kdd.git}"
REF="${2:-v0.1.0}"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  printf '%s\n' "No se encontro Python. Instala Python 3.10 o superior y vuelve a ejecutar este instalador." >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  printf '%s\n' "Se encontro Python, pero necesitas Python 3.10 o superior." >&2
  exit 1
fi
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  printf '%s\n' "Python esta instalado, pero falta pip. Repara la instalacion de Python y vuelve a intentarlo." >&2
  exit 1
fi
printf '%s\n' "Instalando Email Agent. Puede tardar unos minutos; no cierres esta ventana."
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install "git+${SOURCE}@${REF}"
printf '%s\n' "Instalado. Comprobando que el programa responde (email-agent --help)..."
if ! email-agent --help; then
  printf '%s\n' "El sistema no encuentra el comando 'email-agent'. Solucion: anade la carpeta 'bin' de Python a la variable PATH, cierra y vuelve a abrir la terminal, y ejecuta 'email-agent --help'."
  exit 1
fi
printf '%s\n' "Instalacion completada y comprobada. Siguiente paso: crea tu cuenta con 'email-agent account setup-gui <carpeta>' (formulario) o 'email-agent account setup <carpeta>' (terminal)."
