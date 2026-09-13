@echo off
setlocal
cd /d "%~dp0"
if exist ".runtime\python.exe" if exist "data\pip.pyz" (
  ".runtime\python.exe" data\pip.pyz install --target vendor --upgrade --no-build-isolation -r requirements.txt
  goto :done
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m pip install --target vendor -r requirements.txt
  goto :done
)
python -m pip install --target vendor -r requirements.txt
:done
pause
