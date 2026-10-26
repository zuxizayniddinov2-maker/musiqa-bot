@echo off
chcp 65001 >nul
echo =======================================================
echo   ECHOMUSIQA BOT - TO'XTATILMOQDA...
echo =======================================================

taskkill /FI "WINDOWTITLE eq EchoMusicBot*" /T /F >nul 2>&1
python stop.py

echo.
echo [MUVAFFAQIYATLI] Bot to'xtatildi!
ping 127.0.0.1 -n 2 >nul
