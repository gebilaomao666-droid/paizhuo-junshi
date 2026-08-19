@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist config.json copy /Y config.example.json config.json >nul
echo 正在自动查找 Android ADB 或 iPhone 投屏窗口……
python vision_server.py
pause
