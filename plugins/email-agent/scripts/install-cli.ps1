param()
$ErrorActionPreference = "Stop"
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $PythonCommand) {
  throw "No se encontro Python. Instala Python 3.10 o superior y vuelve a ejecutar este instalador."
}
& python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
  throw "Se encontro Python, pero necesitas Python 3.10 o superior."
}
& python -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Python esta instalado, pero falta pip. Repara la instalacion de Python y vuelve a intentarlo."
}
$ReleaseBase = "https://github.com/MauricioPerera/email-agent-kdd/releases/download/v0.2.0"
$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ("email-agent-plugin-install-" + [guid]::NewGuid().ToString("N"))
try {
  New-Item -ItemType Directory -Path $TempRoot | Out-Null
  $Wheel = Join-Path $TempRoot "email_agent_cli-0.2.0-py3-none-any.whl"
  $DependencyWheel = Join-Path $TempRoot "pypdf-6.18.1-py3-none-any.whl"
  $TypingWheel = Join-Path $TempRoot "typing_extensions-4.16.0-py3-none-any.whl"
  $Sums = Join-Path $TempRoot "SHA256SUMS.txt"
  Invoke-WebRequest -UseBasicParsing "$ReleaseBase/SHA256SUMS.txt" -OutFile $Sums
  foreach ($Artifact in @($Wheel, $DependencyWheel, $TypingWheel)) {
    $ArtifactName = [IO.Path]::GetFileName($Artifact)
    Invoke-WebRequest -UseBasicParsing "$ReleaseBase/$ArtifactName" -OutFile $Artifact
    $ChecksumLines = @(Get-Content $Sums | Where-Object { $_ -match ("^[a-fA-F0-9]{64}  " + [regex]::Escape($ArtifactName) + '$') })
    if ($ChecksumLines.Count -ne 1) { throw "Falta un hash unico del artefacto. No se instalara el paquete." }
    $Expected = ($ChecksumLines[0] -split "\s+")[0].ToLowerInvariant()
    $Actual = (Get-FileHash $Artifact -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) { throw "La verificacion de integridad fallo. No se instalara el paquete." }
  }
  & python -m pip install --no-index $TypingWheel $DependencyWheel $Wheel
  if ($LASTEXITCODE -ne 0) { throw "La instalacion fallo." }
} finally {
  if (Test-Path -LiteralPath $TempRoot) { Remove-Item -LiteralPath $TempRoot -Recurse -Force }
}
& email-agent --help
if ($LASTEXITCODE -ne 0) {
  throw "El comando email-agent no esta disponible. Agrega la carpeta Scripts de Python al PATH y abre otra terminal."
}
Write-Host "Email Agent instalado y verificado."
