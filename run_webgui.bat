@echo off
cd /d "%~dp0"
python -m job_watch.webapp
if errorlevel 1 pause
