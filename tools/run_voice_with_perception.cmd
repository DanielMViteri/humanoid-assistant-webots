@echo off
cd /d "%~dp0.."
".\.venv-perception311\Scripts\python.exe" "ros2_ws\src\robot_assistant\robot_assistant\voice_assistant_runner.py" %*
