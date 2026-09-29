@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup Windows.cmd first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -B verify_data.py
if errorlevel 1 echo Verification failed. Check the error above.
pause
