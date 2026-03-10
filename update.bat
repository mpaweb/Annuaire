@echo off
title Mise a jour - Annuaire Neoedge

echo.
echo ================================================
echo   Mise a jour - Annuaire Neoedge
echo ================================================
echo.

if not exist "app\__init__.py" (
    echo [ERREUR] Lancez ce script depuis le dossier annuaire-web.
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
if errorlevel 1 (
    echo [ERREUR] Impossible d'activer le venv.
    pause
    exit /b 1
)
echo       OK

echo [2/5] Sauvegarde des modifications locales...
git diff --quiet
if errorlevel 1 (
    echo       Modifications locales detectees, sauvegarde en cours...
    git stash push -m "Sauvegarde avant mise a jour %DATE% %TIME%"
    echo       OK - sauvegardees avec git stash
) else (
    echo       Aucune modification locale.
)

echo [3/5] Telechargement de la derniere version...
git pull origin main
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

echo [5/5] Migration de la base de donnees...
python -c "from app import create_app, db; app=create_app(); print('  Tables OK')"
if errorlevel 1 (
    echo [ERREUR] Migration echouee. Verifiez votre .env.
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
    echo Lancement sur http://localhost:5000
    echo Ctrl+C pour arreter.
    echo.
    flask --app "app:create_app()" run
) else (
    echo.
    echo Pour lancer manuellement : double-clic sur start.bat
    echo.
    pause
)
