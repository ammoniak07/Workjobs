@echo off
cd /d "%~dp0"
python -m job_watch.gui
if errorlevel 1 pause
