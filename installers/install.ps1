param(
  [string]$Source = "https://github.com/MauricioPerera/email-agent-kdd.git"
)
$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install "git+$Source"
Write-Host "Email Agent instalado. Ejecuta: email-agent --help"
