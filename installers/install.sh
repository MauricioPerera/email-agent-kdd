#!/usr/bin/env sh
set -eu
SOURCE="https://github.com/MauricioPerera/email-agent-kdd.git"
REF="v0.2.1"
FROM_SOURCE=0
if [ "${1:-}" = "--source" ]; then
  FROM_SOURCE=1
  SOURCE="${2:-$SOURCE}"
  REF="${3:-$REF}"
fi
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
if [ "$FROM_SOURCE" -eq 1 ]; then
  printf '%s\n' "Modo desarrollo: instalando desde ${SOURCE}@${REF}"
  "$PYTHON_BIN" -m pip install "git+${SOURCE}@${REF}"
else
  RELEASE_BASE="https://github.com/MauricioPerera/email-agent-kdd/releases/download/v0.2.1"
  TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/email-agent-install.XXXXXX")"
  trap 'rm -rf "$TEMP_ROOT"' EXIT HUP INT TERM
  WHEEL="$TEMP_ROOT/email_agent_cli-0.2.1-py3-none-any.whl"
  DEPENDENCY_WHEEL="$TEMP_ROOT/pypdf-6.18.1-py3-none-any.whl"
  TYPING_WHEEL="$TEMP_ROOT/typing_extensions-4.16.0-py3-none-any.whl"
  SUMS="$TEMP_ROOT/SHA256SUMS.txt"
  curl -fsSL "$RELEASE_BASE/SHA256SUMS.txt" -o "$SUMS"
  for ARTIFACT in "$WHEEL" "$DEPENDENCY_WHEEL" "$TYPING_WHEEL"; do
    ARTIFACT_NAME="$(basename "$ARTIFACT")"
    curl -fsSL "$RELEASE_BASE/$ARTIFACT_NAME" -o "$ARTIFACT"
    EXPECTED="$(awk -v name="$ARTIFACT_NAME" '$2 == name {print tolower($1)}' "$SUMS")"
    if command -v sha256sum >/dev/null 2>&1; then
      ACTUAL="$(sha256sum "$ARTIFACT" | awk '{print tolower($1)}')"
    else
      ACTUAL="$(shasum -a 256 "$ARTIFACT" | awk '{print tolower($1)}')"
    fi
    if [ "${#EXPECTED}" -ne 64 ] || [ "$ACTUAL" != "$EXPECTED" ]; then
      printf '%s\n' "La verificacion de integridad del instalador fallo. No se instalara el paquete." >&2
      exit 1
    fi
  done
  "$PYTHON_BIN" -m pip install --no-index "$TYPING_WHEEL" "$DEPENDENCY_WHEEL" "$WHEEL"
fi
if [ "$?" -ne 0 ]; then
  printf '%s\n' "La instalacion fallo. Revisa el mensaje anterior de pip y vuelve a intentarlo." >&2
  exit 1
fi
printf '%s\n' "Instalado. Comprobando que el programa responde (email-agent --help)..."
if ! email-agent --help; then
  printf '%s\n' "El sistema no encuentra el comando 'email-agent'. Solucion: anade la carpeta 'bin' de Python a la variable PATH, cierra y vuelve a abrir la terminal, y ejecuta 'email-agent --help'."
  exit 1
fi
printf '%s\n' "Instalacion completada y comprobada. Siguiente paso: crea tu cuenta con 'email-agent account setup-gui <carpeta>' (formulario) o 'email-agent account setup <carpeta>' (terminal)."
