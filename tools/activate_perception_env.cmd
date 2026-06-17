@echo off
cd /d "%~dp0.."
call "%~dp0load_runtime_env.cmd" || exit /b 1
set PIP_CERT=
set REQUESTS_CA_BUNDLE=
set SSL_CERT_FILE=
set CURL_CA_BUNDLE=
if not exist "%PERCEPTION_VENV%\Scripts\activate.bat" (
  echo Missing perception env: "%PERCEPTION_VENV%"
  echo Rebuild it with: powershell -ExecutionPolicy Bypass -File tools\rebuild_perception_env.ps1
  exit /b 1
)
call "%PERCEPTION_VENV%\Scripts\activate.bat"
echo Activated %PERCEPTION_VENV%
python -c "import sys; print(sys.executable)"
