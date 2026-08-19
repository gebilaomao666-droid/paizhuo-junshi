@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -m pip install -r requirements.txt
if not exist config.json copy /Y config.example.json config.json >nul
echo.
echo 安装完成。
echo Android：确认 adb devices 能看到手机。
echo iPhone：打开 AirPlay 接收窗口，并从控制中心选择“屏幕镜像”。
echo 接着运行 python calibrate.py。
pause
