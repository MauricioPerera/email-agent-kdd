#!/usr/bin/env sh
set -eu
SOURCE="${1:-https://github.com/MauricioPerera/email-agent-kdd.git}"
printf '%s\n' "Instalando Email Agent. Puede tardar unos minutos; no cierres esta ventana."
python3 -m pip install --upgrade pip
python3 -m pip install "git+${SOURCE}"
printf '%s\n' "Instalado. Comprobando que el programa responde (email-agent --help)..."
if ! email-agent --help; then
  printf '%s\n' "El sistema no encuentra el comando 'email-agent'. Solucion: anade la carpeta 'bin' de Python a la variable PATH, cierra y vuelve a abrir la terminal, y ejecuta 'email-agent --help'."
  exit 1
fi
printf '%s\n' "Instalacion completada y comprobada. Siguiente paso: crea tu cuenta con 'email-agent account setup-gui <carpeta>' (formulario) o 'email-agent account setup <carpeta>' (terminal)."