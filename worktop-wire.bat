@echo off
REM Wire the CURRENT project to use Worktop — appends agent conventions to .\CLAUDE.md.
REM Run this from your project's root folder.
"%~dp0.venv\Scripts\python.exe" "%~dp0worktop_wire.py" "%CD%"
