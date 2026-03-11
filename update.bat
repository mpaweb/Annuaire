@echo off
title Mise a jour - Annuaire Neoedge

echo.
echo ================================================
echo   Mise a jour - Annuaire Neoedge
echo ================================================
echo.

if not exist "app\__init__.py" (
    echo [ERREUR] Lancez ce script depuis le dossier WEB.
    pause
    exit /b 1
)

git --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Git non installe.
    echo          Telechargez-le sur https://git-scm.com/download/win
    pause
    exit /b 1
)

if not exist "venv\Scripts\activate.bat" (
    echo [ERREUR] Environnement virtuel introuvable.
    echo          Lancez d'abord setup.bat
    pause
    exit /b 1
)

echo [1/5] Activation de l'environnement virtuel...
call venv\Scripts\activate.bat
echo       OK

echo [2/5] Sauvegarde des modifications locales...
git diff --quiet
if errorlevel 1 (
    echo       Modifications locales detectees, sauvegarde en cours...
    git stash push -m "Sauvegarde avant mise a jour %DATE% %TIME%"
    echo       OK
) else (
    echo       Aucune modification locale.
)

echo [3/5] Telechargement de la derniere version...
REM Detecter la branche active (master ou main)
git rev-parse --verify master >nul 2>&1
if errorlevel 1 (
    git pull origin main
) else (
    git pull origin master
)
if errorlevel 1 (
    echo [ERREUR] git pull a echoue.
    echo          Verifiez votre connexion et : git remote -v
    pause
    exit /b 1
)
echo       OK

echo [4/5] Mise a jour des dependances...
pip install -r requirements.txt -q -q
if errorlevel 1 (
    echo [AVERTISSEMENT] Certaines dependances n'ont pas pu etre mises a jour.
) else (
    echo       OK
)

echo [5/5] Verification de la base de donnees...
python -c "from app import create_app, db; app=create_app(); print('  Tables OK')"
if errorlevel 1 (
    echo [ERREUR] Echec verification. Verifiez votre .env.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Mise a jour terminee avec succes !
echo ================================================
echo.
echo Derniers commits :
git log --oneline -5
echo.

set /p RELAUNCH=Relancer l'application maintenant ? (oui/non) : 
if /i "%RELAUNCH%"=="oui" (
    echo.
    echo Lancement sur http://127.0.0.1:5000
    start /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"
    flask --app "app:create_app()" run --host 127.0.0.1 --port 5000
) else (
    echo.
    echo Pour lancer manuellement : double-clic sur start.bat
    echo.
    pause
)
