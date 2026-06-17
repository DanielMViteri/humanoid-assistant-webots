param(
    [string]$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    [string]$VenvName = ".venv-deepface310"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot $VenvName
$pythonInVenv = Join-Path $venvPath "Scripts\python.exe"
$weightsDir = Join-Path $repoRoot "data\processed\deepface\.deepface\weights"
$weightsPath = Join-Path $weightsDir "facial_expression_model_weights.h5"
$weightsUrl = "https://github.com/serengil/deepface_models/releases/download/v1.0/facial_expression_model_weights.h5"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

if (Test-Path $venvPath) {
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

& $PythonExe -m venv $venvPath

$env:SSL_CERT_FILE = ""
$env:REQUESTS_CA_BUNDLE = ""
$env:CURL_CA_BUNDLE = ""

& $pythonInVenv -m pip install `
    --trusted-host pypi.org `
    --trusted-host files.pythonhosted.org `
    --trusted-host pypi.python.org `
    -r (Join-Path $repoRoot "requirements-perception.txt") `
    -r (Join-Path $repoRoot "requirements-deepface.txt") `
    -r (Join-Path $repoRoot "requirements-openai.txt") `
    -r (Join-Path $repoRoot "requirements-mongodb.txt") `
    pillow `
    requests

New-Item -ItemType Directory -Force -Path $weightsDir | Out-Null

if (-not (Test-Path $weightsPath)) {
    curl.exe -k -L $weightsUrl -o $weightsPath
}

Write-Host "DeepFace environment rebuilt at $venvPath"
Write-Host "Weights cached at $weightsPath"
