#!/usr/bin/env sh
set -eu
SOURCE="${1:-https://github.com/MauricioPerera/email-agent-kdd.git}"
python3 -m pip install --upgrade pip
python3 -m pip install "git+${SOURCE}"
printf '%s\n' 'Email Agent instalado. Ejecuta: email-agent --help'
