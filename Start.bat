@echo off
mode con cols=55 lines=15
title Soundplantage Tools - miniDexed Studio

echo.                                                    
echo     +=============================================+
echo     ^|                                             ^|
echo     ^|     SOUNDPLANTAGE - DREAMDEXED STUDIO       ^|
echo     ^|                                             ^|
echo     ^|       THE SEED MANAGER (C) 2026             ^|
echo     ^|                                             ^|
echo     ^|     [LOADING.......................]        ^|
echo     ^|                                             ^|
echo     +=============================================+
echo.
start "" pythonw Main.py
timeout /t 2 /nobreak >nul

exit