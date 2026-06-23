@echo off
rem NESTO Care web UI (Next.js dev server). --use-system-ca lets Node trust the
rem machine's certificate store (needed behind the local TLS-inspecting proxy).
cd /d "%~dp0..\web\frontend" || exit /b 1
set "NODE_OPTIONS=--use-system-ca"
echo NESTO UI on http://localhost:3000
call npm run dev
