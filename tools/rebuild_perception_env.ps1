param(
    [string]$PythonExe = "C:\Users\danie\OneDrive\Documents\Project\python.exe",
    [string]$VenvName = ".venv-perception311"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot $VenvName
$pythonInVenv = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

if (Test-Path $venvPath) {
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

& $PythonExe -m venv $venvPath

foreach ($name in "PIP_CERT", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE") {
    if (Test-Path "Env:$name") {
        Remove-Item "Env:$name"
    }
}

& $pythonInVenv -m pip install --upgrade pip
& $pythonInVenv -m pip install `
    -r (Join-Path $repoRoot "requirements-perception.txt") `
    -r (Join-Path $repoRoot "requirements-deepface.txt") `
    -r (Join-Path $repoRoot "requirements-openai.txt") `
    -r (Join-Path $repoRoot "requirements-mongodb.txt") `
    -r (Join-Path $repoRoot "requirements-voice.txt")

Write-Host "Perception environment rebuilt at $venvPath"
Write-Host "Run: call tools\\activate_perception_env.cmd"
