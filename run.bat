@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist config.json copy /Y config.example.json config.json >nul
python vision_server.py
pause
