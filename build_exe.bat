@echo off
cd /d "%~dp0"

echo ===============================
echo   BUILDING OBJECTPROGRAM EXE
echo ===============================

echo.
echo Cleaning old build...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo.
echo Building EXE...
python -m PyInstaller --clean -y main.spec

echo.
echo Copying external resources...
copy /Y tutorials.json dist\tutorials.json
copy /Y ignored_words.json dist\ignored_words.json

echo.
echo ===============================
echo        BUILD COMPLETE
echo ===============================
echo.

echo EXE is located in:
echo %cd%\dist\main.exe

pause