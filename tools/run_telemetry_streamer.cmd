@echo off
cd /d "%~dp0.."
call "%~dp0load_runtime_env.cmd" || exit /b 1
if not exist "%PERCEPTION_VENV%\Scripts\python.exe" (
  echo Missing perception env: "%PERCEPTION_VENV%"
  echo Rebuild it with: powershell -ExecutionPolicy Bypass -File tools\rebuild_perception_env.ps1
  exit /b 1
)
rem Continuously stream new Webots robot events into MongoDB so the dashboard is live.
rem Streams ALL new events; to cut idle perception noise, pass:
rem   tools\run_telemetry_streamer.cmd --skip-types object_detected,object_distance_estimated,scene_described
".\%PERCEPTION_VENV%\Scripts\python.exe" "ros2_ws\src\robot_assistant\robot_assistant\webots_event_importer.py" --follow %*
