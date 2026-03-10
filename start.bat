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
echo   Annuaire Neoedge - http://localhost:5000
echo   Ctrl+C pour arreter.
echo.

start "" http://localhost:5000
flask --app "app:create_app()" run
