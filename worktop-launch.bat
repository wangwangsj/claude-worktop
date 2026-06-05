@echo off
REM Launch the Worktop GLOBAL ball (one window for all projects; state in ~/.worktop).
REM Windowless: a uv-venv's pythonw.exe is a trampoline that spawns a CONSOLE child
REM (pops a terminal), so launch the base interpreter's real pythonw.exe directly and
REM point PYTHONPATH at the venv's packages. Falls back to the venv pythonw if needed.
setlocal enabledelayedexpansion
set "HERE=%~dp0"
set "BASE="
for /f "tokens=2 delims==" %%h in ('findstr /b /c:"home" "%HERE%.venv\pyvenv.cfg" 2^>nul') do set "BASE=%%h"
for /f "tokens=* delims= " %%a in ("!BASE!") do set "BASE=%%a"
set "PYTHONPATH=%HERE%.venv\Lib\site-packages"
if exist "!BASE!\pythonw.exe" (
  start "" "!BASE!\pythonw.exe" "%HERE%gui.pyw"
) else (
  start "" "%HERE%.venv\Scripts\pythonw.exe" "%HERE%gui.pyw"
)
endlocal
