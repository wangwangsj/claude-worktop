@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo [worktop] Installing into "%~dp0"

REM --- locate a Python interpreter ---
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE ( where python >nul 2>nul && set "PYEXE=python" )
if not defined PYEXE (
  echo [worktop] ERROR: Python not found on PATH. Install Python 3.9+ from python.org and re-run.
  exit /b 1
)
echo [worktop] Using interpreter: %PYEXE%

REM --- create the virtualenv ---
%PYEXE% -m venv .venv
if errorlevel 1 ( echo [worktop] ERROR: failed to create .venv & exit /b 1 )

REM --- install dependencies ---
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo [worktop] ERROR: pip install failed & exit /b 1 )

echo.
echo [worktop] Installed OK.
echo.
echo   Launch the ball (run from your PROJECT folder so state lands in that project):
echo       "%~dp0worktop-launch.bat"
echo.
echo   Agent call convention (run with the project folder as the working directory):
echo       "%~dp0.venv\Scripts\python.exe" "%~dp0worktop.py" task "Title" --id ^<lane^>
echo.
echo   See README.md for the Claude Code settings.json hook and agent instructions.
endlocal
