@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 关闭端口 5055 的进程（静默执行）
(for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5055 ^| findstr LISTENING 2^>nul') do taskkill /F /PID %%a >nul 2>&1) 2>nul

:: 等待端口释放
ping -n 3 127.0.0.1 >nul 2>&1

:: 启动服务（隐藏窗口）
start /min "" python -X utf8 ads_manager.py
