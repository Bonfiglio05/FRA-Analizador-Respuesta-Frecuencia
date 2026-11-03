@echo off
rem Abre la app del FRA con el Python del entorno virtual (.venv) si existe; si no, con el Python del sistema.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)
if errorlevel 1 (
    echo.
    echo La aplicacion se cerro con un error. Revisa el mensaje de arriba.
    pause
)
