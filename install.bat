@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
echo [worktop] Installing into "%~dp0"

REM --- prefer uv (fast; many setups already have it) ---
where uv >nul 2>nul
if not errorlevel 1 (
  echo [worktop] Using uv
  uv venv .venv || ( echo [worktop] ERROR: uv venv failed & exit /b 1 )
  uv pip install -r requirements.txt --python ".venv\Scripts\python.exe" || ( echo [worktop] ERROR: uv pip install failed & exit /b 1 )
  goto :done
)

REM --- else the py launcher ---
where py >nul 2>nul
if not errorlevel 1 (
  echo [worktop] Using py launcher
  py -m venv .venv || ( echo [worktop] ERROR: venv creation failed & exit /b 1 )
  goto :pipinstall
)

REM --- else a real python on PATH (reject the Microsoft Store stub, which fails to run code) ---
python -c "import sys" >nul 2>nul
if not errorlevel 1 (
  echo [worktop] Using python
  python -m venv .venv || ( echo [worktop] ERROR: venv creation failed & exit /b 1 )
  goto :pipinstall
)

echo [worktop] ERROR: no usable Python found (tried uv, py, python).
echo [worktop] Install uv (https://docs.astral.sh/uv) or Python 3.9+ from python.org, then re-run.
exit /b 1

:pipinstall
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || ( echo [worktop] ERROR: pip install failed & exit /b 1 )

:done
echo.
echo [worktop] Installed OK.
echo.
echo   Launch the ball (run from your PROJECT folder so state lands there):
echo       "%~dp0worktop-launch.bat"
echo.
echo   Agent call convention (working directory = the project root):
echo       "%~dp0.venv\Scripts\python.exe" "%~dp0worktop.py" task "Title" --id ^<lane^>
echo.
echo   Wire a project's CLAUDE.md with the agent conventions (run from that project):
echo       "%~dp0worktop-wire.bat"
echo.
echo   Agent conventions: "%~dp0AGENTS.md"   ^|  decision hook + more: README.md
endlocal
