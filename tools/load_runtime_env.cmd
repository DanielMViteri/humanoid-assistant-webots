@echo off
set "RUNTIME_ENV_FILE=%~dp0runtime_env.conf"

if not exist "%RUNTIME_ENV_FILE%" (
  echo Missing runtime env config: "%RUNTIME_ENV_FILE%"
  exit /b 1
)

for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%RUNTIME_ENV_FILE%") do (
  if not "%%A"=="" set "%%A=%%B"
)

exit /b 0
