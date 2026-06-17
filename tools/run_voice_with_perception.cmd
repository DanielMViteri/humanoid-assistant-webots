@echo off
cd /d "%~dp0.."
call "%~dp0load_runtime_env.cmd" || exit /b 1
if not exist "%PERCEPTION_VENV%\Scripts\python.exe" (
  echo Missing perception env: "%PERCEPTION_VENV%"
  echo Rebuild it with: powershell -ExecutionPolicy Bypass -File tools\rebuild_perception_env.ps1
  exit /b 1
)
".\%PERCEPTION_VENV%\Scripts\python.exe" "ros2_ws\src\robot_assistant\robot_assistant\voice_assistant_runner.py" %*
