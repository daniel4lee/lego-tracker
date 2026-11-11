@echo off
chcp 65001 > nul
title LEGO 套組更新
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ===================================================
echo   LEGO 星戰套組更新：Rebrickable 新套組 + 官方美金定價 + 匯率
echo   （手動改過 sets.js 的 price 會自動保留）
echo ===================================================
echo.

python update_sets.py
if errorlevel 1 (
    echo.
    echo [錯誤] 更新失敗，請看上方訊息
    pause
    exit /b 1
)

echo.
git status --short
echo.
set /p PUSH=要推上 GitHub（網站約 1 分鐘後更新）嗎？[y/N] 
if /i not "%PUSH%"=="y" (
    echo 沒有推送，檔案已更新在本機。
    pause
    exit /b 0
)

git add sets.js index.html
git commit -m "Update sets data"
git push
if errorlevel 1 (
    echo.
    echo [錯誤] 推送失敗，請看上方訊息
    pause
    exit /b 1
)

echo.
echo [完成] 這個視窗 10 秒後自動關閉
timeout /t 10
