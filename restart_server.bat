@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 关闭端口 5055 的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5055 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: 等待端口释放
timeout /t 2 /nobreak >nul

:: 启动服务
start "YP Ads Platform" python -X utf8 ads_manager.py
