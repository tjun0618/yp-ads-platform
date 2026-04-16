@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo YP Affiliate 管理台
echo ================================================
echo.
echo 正在启动服务...
echo.
python -X utf8 ads_manager.py
pause
