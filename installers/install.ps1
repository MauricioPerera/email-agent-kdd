param(
  [string]$Source = "https://github.com/MauricioPerera/email-agent-kdd.git"
)
$ErrorActionPreference = "Stop"
Write-Host "Instalando Email Agent. Puede tardar unos minutos; no cierres esta ventana."
python -m pip install --upgrade pip
python -m pip install "git+$Source"
if ($LASTEXITCODE -ne 0) { throw "La instalacion fallo. Revisa el mensaje anterior de pip y vuelve a intentarlo." }
Write-Host "Instalado. Comprobando que el programa responde (email-agent --help)..."
email-agent --help
if ($LASTEXITCODE -ne 0) {
  Write-Host "El sistema no encuentra el comando 'email-agent'. Solucion: anade la carpeta 'Scripts' de Python a la variable PATH, cierra y vuelve a abrir la terminal, y ejecuta 'email-agent --help'."
  exit 1
}
Write-Host "Instalacion completada y comprobada. Siguiente paso: crea tu cuenta con 'email-agent account setup-gui <carpeta>' (formulario) o 'email-agent account setup <carpeta>' (terminal)."