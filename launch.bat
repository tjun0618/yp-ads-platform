@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo YP Affiliate 管理台
echo ================================================
echo.

:: 关闭旧的 ads_manager 进程
echo 正在关闭旧进程...
taskkill /F /FI "WINDOWTITLE eq YP Ads Platform*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq ads_manager*" >nul 2>&1

:: 通过端口 5055 查找并关闭进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5055 ^| findstr LISTENING') do (
    echo 关闭端口 5055 的进程 PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

:: 等待端口释放
timeout /t 2 /nobreak >nul

echo 正在启动服务...
echo.
python -X utf8 ads_manager.py
pause
