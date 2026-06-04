@echo off
REM Launch the Worktop ball for the CURRENT project.
REM Run this from your project folder — state goes to ".\.worktop\".
REM Override the location by setting WORKTOP_STATE before launching.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0gui.pyw"
