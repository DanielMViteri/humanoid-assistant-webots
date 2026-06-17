@echo off
cd /d "%~dp0.."
set PIP_CERT=
set REQUESTS_CA_BUNDLE=
set SSL_CERT_FILE=
set CURL_CA_BUNDLE=
call .venv-perception311\Scripts\activate.bat
echo Activated .venv-perception311
python -c "import sys; print(sys.executable)"
