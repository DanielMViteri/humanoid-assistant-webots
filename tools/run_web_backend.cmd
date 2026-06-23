@echo off
rem NESTO Care web API (FastAPI). Thin layer over the existing nesto-dashboard
rem modules; writes the same events the robot bridge consumes. Port 8000.
set "WEB_PY=%~dp0..\.venv-web\Scripts\python.exe"
if not exist "%WEB_PY%" (
  echo Missing web venv: "%WEB_PY%"
  echo Create it with: tools\rebuild_web_env.cmd  (or see web\backend\requirements.txt^)
  exit /b 1
)
cd /d "%~dp0..\web\backend" || exit /b 1
echo NESTO API on http://127.0.0.1:8000  (health: /api/health)
"%WEB_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload %*
