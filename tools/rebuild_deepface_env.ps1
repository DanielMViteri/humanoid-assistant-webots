param(
    [string]$PythonExe = "",
    [string]$VenvName = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeConfig = Join-Path $PSScriptRoot "runtime_env.conf"
$weightsDir = Join-Path $repoRoot "data\processed\deepface\.deepface\weights"
$weightsPath = Join-Path $weightsDir "facial_expression_model_weights.h5"
$weightsUrl = "https://github.com/serengil/deepface_models/releases/download/v1.0/facial_expression_model_weights.h5"

function Get-RuntimeConfigValue {
    param(
        [string]$Name,
        [string]$DefaultValue = ""
    )

    if (-not (Test-Path $runtimeConfig)) {
        return $DefaultValue
    }

    $match = Get-Content $runtimeConfig |
        Where-Object { $_ -match "^\s*$Name=" } |
        Select-Object -First 1

    if (-not $match) {
        return $DefaultValue
    }

    return (($match -split "=", 2)[1]).Trim()
}

if (-not $VenvName) {
    $VenvName = Get-RuntimeConfigValue -Name "DEEPFACE_VENV" -DefaultValue ".venv-deepface310"
}

if (-not $PythonExe) {
    $pythonSpec = Get-RuntimeConfigValue -Name "DEEPFACE_PYTHON_SPEC" -DefaultValue "3.10"
    $PythonExe = (& py "-$pythonSpec" -c "import sys; print(sys.executable)").Trim()
}

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

$venvPath = Join-Path $repoRoot $VenvName
$pythonInVenv = Join-Path $venvPath "Scripts\python.exe"

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
