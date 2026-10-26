@echo off
chcp 65001 > nul
echo ========================================================
echo   EchoMusiqa Botni GitHub-ga Yuklash (Push)
echo ========================================================
echo.
echo Repozitoriy: https://github.com/zuxizayniddinov2-maker/musiqa-bot.git
echo Tarmoq: main
echo.
echo Brauzerda ochilgan GitHub oynasidan "Authorize" ni bosing...
echo.
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo   [MUVAFFAQIYATLI] Loyiha GitHub-ga to'liq yuklandi!
    echo ========================================================
) else (
    echo ========================================================
    echo   [XATOLIK] Yuklash amalga oshmadi.
    echo   Iltimos, GitHub token yoki profilingizni tekshiring.
    echo ========================================================
)
echo.
pause
