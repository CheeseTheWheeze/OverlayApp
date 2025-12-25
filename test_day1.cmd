@echo off
setlocal
set ROOT_DIR=%~dp0
set EXE=%ROOT_DIR%dist\GrapplingOverlay\GrapplingOverlay.exe

if exist "%EXE%" (
  echo Running packaged app...
  "%EXE%" --test-mode --headless
) else (
  echo Packaged app not found. Falling back to source run...
  python -m apps.windows.main --test-mode --headless
)

if errorlevel 1 goto error

python -m pytest tests/test_schema_validation.py
if errorlevel 1 goto error

echo Day-1 test passed.
goto end

:error
echo Day-1 test failed. See logs for details.

:end
pause
