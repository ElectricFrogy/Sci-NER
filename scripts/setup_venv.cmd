@echo off
REM Run the PowerShell setup with execution policy bypass and preserve args
powershell -ExecutionPolicy Bypass -File "scripts\setup_venv.ps1" %*
