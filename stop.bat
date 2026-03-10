@echo off
title Arret - Annuaire Neoedge

echo.
echo ================================================
echo   Arret - Annuaire Neoedge
echo ================================================
echo.

echo Recherche du processus Flask en cours...

:: Chercher le process flask sur le port 5000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    set PID=%%a
)

if not defined PID (
    echo Aucune application trouvee sur le port 5000.
    echo L'application est peut-etre deja arretee.
    echo.
    pause
    exit /b 0
)

echo Application trouvee - PID : %PID%
echo.
set /p CONFIRM=Confirmer l'arret ? (oui/non) : 
if /i not "%CONFIRM%"=="oui" (
    echo Annule.
    pause
    exit /b 0
)

echo Arret en cours...
taskkill /PID %PID% /F >nul 2>&1

if errorlevel 1 (
    echo [ERREUR] Impossible d'arreter le processus %PID%.
    echo          Essayez manuellement : taskkill /PID %PID% /F
) else (
    echo Application arretee avec succes.
)

echo.
pause
