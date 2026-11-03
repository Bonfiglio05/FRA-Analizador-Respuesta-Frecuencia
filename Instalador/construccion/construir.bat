@echo off
rem Genera el instalador de la app del FRA: FRA_Instalador_<version>.exe, en la carpeta de arriba (Instalador).
rem
rem Uso:  construir.bat [carpeta_de_la_app]
rem   carpeta_de_la_app = la carpeta que contiene run.py y src\ (el codigo de la app).
rem   Si se omite, se usa la que esta dos niveles arriba (cuando esta carpeta esta dentro de App\Instalador).
rem
rem Requisitos: Python y Inno Setup 6 (https://jrsoftware.org/isinfo.php).
setlocal
cd /d "%~dp0"

set "APP=%~1"
if "%APP%"=="" set "APP=%~dp0..\.."
for %%I in ("%APP%") do set "APP=%%~fI"
if not exist "%APP%\run.py" (
    echo No se encontro la app en "%APP%" ^(falta run.py^).
    echo Uso: construir.bat carpeta_de_la_app
    goto :error
)
set "FRA_APP_DIR=%APP%"

rem Python del entorno de la app (.venv); si no existe, el del sistema
set "PY=%APP%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

rem Dependencias de la app y PyInstaller, si faltan
"%PY%" -c "import PySide6, matplotlib, numpy, serial" >nul 2>&1
if errorlevel 1 (
    echo Instalando las dependencias de la app...
    "%PY%" -m pip install -r "%APP%\requirements.txt" || goto :error
)
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller...
    "%PY%" -m pip install -r requirements-build.txt || goto :error
)

rem Se construye en una carpeta temporal CORTA: con rutas largas (carpetas de OneDrive, etc.) Windows falla
rem al cargar algunos modulos de la app empaquetada.
set "BUILD=%TEMP%\fra_build"
if exist "%BUILD%" rmdir /s /q "%BUILD%"

echo.
echo === 1/2 Empaquetando la aplicacion ===
"%PY%" -m PyInstaller fra.spec --noconfirm --clean --distpath "%BUILD%\dist" --workpath "%BUILD%\work" || goto :error

echo.
echo === 2/2 Generando el instalador ===
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo No se encontro Inno Setup 6. Instalalo desde https://jrsoftware.org/isinfo.php y volve a ejecutar este archivo.
    goto :error
)
"%ISCC%" /DOrigen="%BUILD%\dist\FRA" instalador.iss || goto :error

echo.
echo Listo. El instalador esta en la carpeta Instalador: FRA_Instalador_*.exe
if exist "%BUILD%" rmdir /s /q "%BUILD%"
pause
exit /b 0

:error
echo.
echo Ocurrio un error. Revisa el mensaje de arriba.
pause
exit /b 1
