@echo off
rem Launch the NESTO Care web app: FastAPI API (:8000) + Next.js UI (:3000),
rem each in its own window. The robot bridge / Webots / telemetry run as before.
start "NESTO API" cmd /k "%~dp0run_web_backend.cmd"
start "NESTO UI" cmd /k "%~dp0run_web_frontend.cmd"
echo.
echo   API : http://127.0.0.1:8000/api/health
echo   UI  : http://localhost:3000   (login: testninep@gmail.com / test1234)
echo.
