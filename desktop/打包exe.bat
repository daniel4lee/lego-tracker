@echo off
chcp 65001 > nul
title 打包 LEGO 追蹤器 exe
cd /d "%~dp0"

echo ===================================================
echo   打包 LEGO 追蹤器桌面版（完成後放到桌面）
echo ===================================================
echo.

if not exist .venv (
    echo 第一次執行，建立打包環境…
    python -m venv .venv
)
.venv\Scripts\python -m pip install -q --disable-pip-version-check pywebview pyinstaller
if errorlevel 1 goto :fail

.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name "LEGO追蹤器" --icon icon.ico lego_tracker_app.py
if errorlevel 1 goto :fail

copy /y "dist\LEGO追蹤器.exe" "%USERPROFILE%\Desktop\LEGO追蹤器.exe" > nul
echo.
echo [完成] 已放到桌面：LEGO追蹤器.exe
timeout /t 10
exit /b 0

:fail
echo.
echo [錯誤] 打包失敗，請看上方訊息
pause
exit /b 1
