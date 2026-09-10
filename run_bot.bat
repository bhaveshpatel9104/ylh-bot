@echo off
title YouLikeHits Points Bot - RUNNING
color 0A
mode con: cols=70 lines=35

echo ============================================================
echo       YouLikeHits YouTube Likes Bot
echo       Account: patelbhavesh9130@gmail.com
echo ============================================================
echo.
echo  Bot shuru ho raha hai...
echo  Points continuously earn hote rahenge!
echo.
echo  Band karne ke liye: is window ko close karo
echo  Ya yahan click karke Ctrl+C dabao
echo ============================================================
echo.

cd /d "%~dp0"

:restart
python bot.py

echo.
echo [!] Bot band ho gaya - 15 second mein restart hoga...
timeout /t 15 /nobreak
goto restart
