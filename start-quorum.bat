@echo off
setlocal
pushd "%~dp0" || exit /b 1

if not exist "app\.venv\Scripts\python.exe" (
    echo Quorum's Python environment is missing. Follow the Windows setup in README.md.
    popd
    pause
    exit /b 1
)

echo Starting Quorum at http://127.0.0.1:8766/
echo Keep this window open while using Quorum. Press Ctrl+C to stop the server.
powershell.exe -NoLogo -NoProfile -Command "$ErrorActionPreference = 'Stop'; . '.\scripts\env.ps1'; & '.\app\.venv\Scripts\python.exe' '.\scripts\memory_lab.py'; exit $LASTEXITCODE"
set "server_exit=%ERRORLEVEL%"
popd

if not "%server_exit%"=="0" (
    echo Quorum stopped with an error. If it is already running, open http://127.0.0.1:8766/.
    pause
)
exit /b %server_exit%
