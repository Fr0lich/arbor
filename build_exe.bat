@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ===================================================
echo     ARBOR - MUSEUM OBJECT VISUALIZER
echo         Executable Build Pipeline
echo ===================================================
echo.

:: 1. Detect Python / Virtual Environment
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [INFO] Using virtual environment Python: .venv
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    echo [INFO] Using virtual environment Python: venv
) else (
    echo [INFO] Using system Python from PATH
)

:: Verify Python executable
"%PYTHON_EXE%" --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found or is not accessible.
    echo Please ensure Python is installed and added to PATH, or activate your virtual environment.
    goto :build_failed
)

:: Verify PyInstaller is installed
"%PYTHON_EXE%" -m PyInstaller --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller is not installed in the active environment.
    echo Please install it using: "%PYTHON_EXE%" -m pip install pyinstaller
    goto :build_failed
)

:: 2. Clean old build artifacts
echo.
echo [1/3] Cleaning previous build artifacts...
if exist "build" (
    rmdir /s /q "build" 2>nul
)
if exist "dist" (
    rmdir /s /q "dist" 2>nul
)

:: 3. Run PyInstaller build
echo.
echo [2/3] Building Arbor.exe via PyInstaller...
"%PYTHON_EXE%" -m PyInstaller --clean -y main.spec
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PyInstaller build failed with exit code %ERRORLEVEL%.
    goto :build_failed
)

:: 4. Copy external resources to dist folder
echo.
echo [3/3] Copying external configuration and data resources...
if exist "tutorials.json" (
    copy /Y "tutorials.json" "dist\tutorials.json" >nul
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] Failed to copy tutorials.json to dist.
    ) else (
        echo   - tutorials.json copied
    )
) else (
    echo [WARNING] tutorials.json not found in root.
)

if exist "ignored_words.json" (
    copy /Y "ignored_words.json" "dist\ignored_words.json" >nul
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] Failed to copy ignored_words.json to dist.
    ) else (
        echo   - ignored_words.json copied
    )
) else (
    echo [WARNING] ignored_words.json not found in root.
)

echo.
echo ===================================================
echo               BUILD SUCCESSFUL
echo ===================================================
echo.
echo Executable is ready at:
echo   %cd%\dist\Arbor.exe
echo.
pause
exit /b 0

:build_failed
echo.
echo ===================================================
echo                 BUILD FAILED
echo ===================================================
echo Please inspect the error messages above.
echo.
pause
exit /b 1