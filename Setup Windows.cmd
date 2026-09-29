@echo off
setlocal
cd /d "%~dp0"
set "LOOKUP_PYTHON="
set "LOOKUP_PYTHON_ARGS="

rem Reuse a working environment without recreating it.
call :try_python "%~dp0.venv\Scripts\python.exe"
if defined LOOKUP_PYTHON goto install

rem The optional py launcher is only one of several ways to find Python.
if defined HORTA_PYTHON call :try_python "%HORTA_PYTHON%"
call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try_python "%ProgramFiles%\Python312\python.exe"
call :try_python "python"
call :try_python "py" "-3.12"
if not defined LOOKUP_PYTHON goto missing_python

echo Using "%LOOKUP_PYTHON%" %LOOKUP_PYTHON_ARGS%
"%LOOKUP_PYTHON%" %LOOKUP_PYTHON_ARGS% -m venv .venv
if errorlevel 1 goto environment_failed

:install
echo Installing Horta Lookup dependencies...
".venv\Scripts\python.exe" -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 goto dependencies_failed
".venv\Scripts\python.exe" -c "import numpy, PIL, plotly, tkinter"
if errorlevel 1 goto dependencies_failed
echo.
echo Setup complete. Open Start lookup.cmd.
if /i not "%~1"=="--no-pause" pause
exit /b 0

:missing_python
echo.
echo Python 3.12 with Tcl/Tk was not found.
echo Install Python 3.12 from https://www.python.org/downloads/windows/
echo The py launcher is optional. You can also set HORTA_PYTHON to python.exe's full path.
goto failed

:environment_failed
echo.
echo Could not create the local Python environment. Check the error above and folder write access.
goto failed

:dependencies_failed
echo.
echo Python was found, but dependency setup failed. Check the error above and your internet connection.
goto failed

:failed
if /i not "%~1"=="--no-pause" pause
exit /b 1

:try_python
if defined LOOKUP_PYTHON exit /b 0
"%~1" %~2 -c "import sys, venv, tkinter; raise SystemExit(sys.version_info[:2] != (3, 12))" >nul 2>&1
if errorlevel 1 exit /b 0
set "LOOKUP_PYTHON=%~1"
set "LOOKUP_PYTHON_ARGS=%~2"
exit /b 0
