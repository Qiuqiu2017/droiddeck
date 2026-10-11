@echo off
rem DroidDeck - build a Windows package (run on Windows)
setlocal
cd /d "%~dp0"

python -m pip install --upgrade pip
python -m pip install "PySide6>=6.5" pyinstaller
if errorlevel 1 goto :err

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm --clean packaging\droiddeck.spec
if errorlevel 1 goto :err

powershell -NoProfile -Command "Compress-Archive -Path dist\droiddeck -DestinationPath droiddeck-windows-x86_64.zip -Force"
echo.
echo Build complete: droiddeck-windows-x86_64.zip
goto :eof

:err
echo.
echo Build failed.
exit /b 1
