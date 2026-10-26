@echo off
chcp 65001 >nul
echo =======================================================
echo   ECHOMUSIQA BOT - FONDA ISHGA TUSHIRILMOQDA
echo =======================================================

:: Avval eskisini to'xtatamiz
taskkill /FI "WINDOWTITLE eq EchoMusicBot*" /T /F >nul 2>&1

:: Yangi oynada botni ishga tushirish
start "EchoMusicBot" cmd /k "chcp 65001 >nul && python bot.py"

echo.
echo [MUVAFFAQIYATLI] Bot yangi oynada ishga tushirildi!
echo To'xtatish uchun stop.bat faylini bosing.
ping 127.0.0.1 -n 2 >nul
