@echo off
rem Runs deploy\expose.ps1 without changing the PowerShell execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0expose.ps1"
pause
