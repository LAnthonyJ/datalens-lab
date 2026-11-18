@echo off
setlocal
set "PYTHONUTF8=1"
if exist "%~dp0.venv-lowmem\Scripts\python.exe" (
    "%~dp0.venv-lowmem\Scripts\python.exe" "%~dp0demo.py" --device cpu %*
) else (
    "%~dp0.venv\Scripts\python.exe" "%~dp0demo.py" --device cuda %*
)
exit /b %errorlevel%
