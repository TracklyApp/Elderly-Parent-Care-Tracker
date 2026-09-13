@echo off
setlocal
cd /d "%~dp0"
if exist ".runtime\python.exe" (
  ".runtime\python.exe" server.py
  goto :end
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 server.py
  goto :end
)
if exist "C:\Program Files\Inkscape\bin\python.exe" (
  "C:\Program Files\Inkscape\bin\python.exe" server.py
  goto :end
)
where python >nul 2>nul
if not errorlevel 1 (
  python server.py
  goto :end
)
echo Install Python 3.10 or later, then run this file again.
:end
pause
