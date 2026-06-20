@echo off
rem Launch the NESTO Care dashboard with the PINNED main venv python.
rem Why pinned: the Atlas URI is mongodb+srv://, which needs the dnspython package.
rem A bare "python" on PATH may lack it, in which case db_queries silently falls back
rem to mongodb://localhost:27017 and the dashboard stops reaching Atlas (bridge sees nothing).
call "%~dp0load_runtime_env.cmd" || exit /b 1

set "MAIN_PY=%~dp0..\%MAIN_VENV%\Scripts\python.exe"
if not exist "%MAIN_PY%" (
  echo Missing main venv python: "%MAIN_PY%"
  echo This venv must have streamlit + pymongo + python-dotenv + dnspython.
  exit /b 1
)

rem Run from the dashboard folder so db_queries' find_dotenv walks up to swarmsense\.env (Atlas).
cd /d "%~dp0..\nesto-dashboard" || exit /b 1
echo Dashboard interpreter: "%MAIN_PY%"
echo Working dir: %CD%
"%MAIN_PY%" -m streamlit run app.py %*
