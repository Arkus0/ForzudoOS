@echo off
rem Doble clic para arrancar CapturaIA en Windows (necesita uv instalado).
cd /d "%~dp0"
uv run capturaia %*
if errorlevel 1 pause
