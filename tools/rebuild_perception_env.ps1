param(
    [string]$PythonExe = "",
    [string]$VenvName = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeConfig = Join-Path $PSScriptRoot "runtime_env.conf"
$venvPath = Join-Path $repoRoot $VenvName
$pythonInVenv = Join-Path $venvPath "Scripts\python.exe"

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
    $VenvName = Get-RuntimeConfigValue -Name "PERCEPTION_VENV" -DefaultValue ".venv-perception311"
}

if (-not $PythonExe) {
    $pythonSpec = Get-RuntimeConfigValue -Name "PERCEPTION_PYTHON_SPEC" -DefaultValue "3.11"
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
