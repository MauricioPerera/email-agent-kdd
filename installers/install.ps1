param(
  [switch]$FromSource,
  [string]$Source = "https://github.com/MauricioPerera/email-agent-kdd.git",
  [string]$Ref = "v0.1.0"
)
$ErrorActionPreference = "Stop"
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $PythonCommand) {
  throw "No se encontro Python. Instala Python 3.10 o superior y vuelve a ejecutar este instalador."
}
$PythonVersionOk = & python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
  throw "Se encontro Python, pero necesitas Python 3.10 o superior."
}
& python -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Python esta instalado, pero falta pip. Repara la instalacion de Python y vuelve a intentarlo."
}
$ReleaseBase = "https://github.com/MauricioPerera/email-agent-kdd/releases/download/v0.1.0"
$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("email-agent-install-" + [guid]::NewGuid().ToString("N"))
try {
  Write-Host "Instalando Email Agent. Puede tardar unos minutos; no cierres esta ventana."
  if ($FromSource) {
    Write-Host "Modo desarrollo: instalando desde $Source@$Ref"
    python -m pip install "git+$Source@$Ref"
  } else {
    New-Item -ItemType Directory -Path $TempRoot | Out-Null
    $Wheel = Join-Path $TempRoot "email_agent_cli-0.1.0-py3-none-any.whl"
    $Sums = Join-Path $TempRoot "SHA256SUMS.txt"
    Invoke-WebRequest -UseBasicParsing "$ReleaseBase/email_agent_cli-0.1.0-py3-none-any.whl" -OutFile $Wheel
    Invoke-WebRequest -UseBasicParsing "$ReleaseBase/SHA256SUMS.txt" -OutFile $Sums
    $Expected = ((Get-Content $Sums | Where-Object { $_ -match "  email_agent_cli-0\.1\.0-py3-none-any\.whl$" }) -split "\s+")[0].ToLowerInvariant()
    $Actual = (Get-FileHash $Wheel -Algorithm SHA256).Hash.ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($Expected) -or $Actual -ne $Expected) {
      throw "La verificacion de integridad del instalador fallo. No se instalara el paquete."
    }
    python -m pip install --no-index $Wheel
  }
  if ($LASTEXITCODE -ne 0) { throw "La instalacion fallo. Revisa el mensaje anterior de pip y vuelve a intentarlo." }
} finally {
  if (Test-Path -LiteralPath $TempRoot) { Remove-Item -LiteralPath $TempRoot -Recurse -Force }
}
if ($LASTEXITCODE -ne 0) { throw "La instalacion fallo. Revisa el mensaje anterior de pip y vuelve a intentarlo." }
Write-Host "Instalado. Comprobando que el programa responde (email-agent --help)..."
email-agent --help
if ($LASTEXITCODE -ne 0) {
  Write-Host "El sistema no encuentra el comando 'email-agent'. Solucion: anade la carpeta 'Scripts' de Python a la variable PATH, cierra y vuelve a abrir la terminal, y ejecuta 'email-agent --help'."
  exit 1
}
Write-Host "Instalacion completada y comprobada. Siguiente paso: crea tu cuenta con 'email-agent account setup-gui <carpeta>' (formulario) o 'email-agent account setup <carpeta>' (terminal)."
