#!/usr/bin/env sh
set -eu

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  printf '%s\n' "No se encontro Python. Instala Python 3.10 o superior y vuelve a ejecutar este instalador." >&2
  exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  printf '%s\n' "Se requiere Python 3.10 o superior." >&2
  exit 1
fi
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  printf '%s\n' "Falta pip para este Python." >&2
  exit 1
fi

RELEASE_BASE="https://github.com/MauricioPerera/email-agent-kdd/releases/download/v0.2.1"
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/email-agent-plugin-install.XXXXXX")"
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
    printf '%s\n' "La verificacion de integridad fallo. No se instalara el paquete." >&2
    exit 1
  fi
done

"$PYTHON_BIN" -m pip install --no-index "$TYPING_WHEEL" "$DEPENDENCY_WHEEL" "$WHEEL"
email-agent --help >/dev/null
printf '%s\n' "Email Agent instalado y verificado."
