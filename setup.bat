@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r requirements.txt
if not exist config.json copy /Y config.example.json config.json >nul
echo.
echo 安装完成。确认 adb devices 能看到手机后，运行 calibrate.py。
pause
