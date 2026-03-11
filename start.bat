@echo off
title Annuaire Neoedge

if not exist "venv\Scripts\activate.bat" (
    echo [ERREUR] Environnement virtuel introuvable.
    echo          Lancez d'abord setup.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM Verifier que flask-limiter est installe, sinon l'installer automatiquement
python -c "import flask_limiter" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Nouvelles dependances detectees, installation en cours...
    pip install -r requirements.txt -q
    echo       Dependances mises a jour.
    echo.
)

echo.
echo   Annuaire Neoedge - http://127.0.0.1:5000
echo   Ctrl+C pour arreter.
echo.

REM Ouvrir le navigateur apres 3 secondes (temps de demarrage Flask)
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"

REM Lancer Flask (bloque jusqu'a Ctrl+C)
flask --app "app:create_app()" run --host 127.0.0.1 --port 5000
