@echo off
title Annuaire Neoedge

if not exist "venv\Scripts\activate.bat" (
    echo [ERREUR] Environnement virtuel introuvable.
    echo          Lancez d'abord setup.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo.
echo   Annuaire Neoedge - http://127.0.0.1:5000
echo   Ctrl+C pour arreter.
echo.

REM Ouvrir le navigateur apres 3 secondes (le temps que Flask demarre)
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"

REM Lancer Flask (bloque jusqu'a Ctrl+C)
flask --app "app:create_app()" run --host 127.0.0.1 --port 5000
