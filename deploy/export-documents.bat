@echo off
rem Runs deploy\export-documents.ps1 without changing the PowerShell execution policy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0export-documents.ps1" %*
pause
