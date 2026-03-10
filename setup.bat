@echo off
title Installation - Annuaire Neoedge

echo.
echo ================================================
echo   Installation initiale - Annuaire Neoedge
echo ================================================
echo.

if not exist "app\__init__.py" (
    echo [ERREUR] Lancez ce script depuis le dossier annuaire-web.
    pause
    exit /b 1
)

echo [1/6] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python non trouve.
    echo          Telechargez Python 3.11+ sur https://python.org
    pause
    exit /b 1
)
python --version
echo       OK

echo [2/6] Verification de Git...
git --version >nul 2>&1
if errorlevel 1 (
    echo [AVERTISSEMENT] Git non trouve. Les mises a jour auto ne fonctionneront pas.
    echo                 Telechargez Git sur https://git-scm.com/download/win
) else (
    git --version
    echo       OK
)

echo [3/6] Creation de l'environnement virtuel...
if exist "venv\" (
    echo       Deja present, on continue.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer le venv.
        pause
        exit /b 1
    )
    echo       OK
)

echo [4/6] Installation des dependances...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERREUR] Installation des dependances echouee.
    pause
    exit /b 1
)
echo       OK

echo [5/6] Configuration...
if exist ".env" (
    echo       Fichier .env deja present.
) else (
    copy .env.example .env >nul
    echo       Fichier .env cree depuis .env.example.
    echo.
    echo   IMPORTANT : Ouvrez .env et modifiez :
    echo     - SECRET_KEY   (cle aleatoire)
    echo     - ADMIN_PASSWORD   (votre mot de passe)
    echo.
    echo   Pour generer une SECRET_KEY :
    echo   python -c "import secrets; print(secrets.token_hex(32))"
    echo.
    pause
)

echo [6/6] Initialisation de la base de donnees...
python -c "from app import create_app, db; app=create_app(); print('  Base OK')"
if errorlevel 1 (
    echo [ERREUR] Echec init base. Verifiez votre .env.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Installation terminee avec succes !
echo ================================================
echo.
echo   Lancer l'appli   : double-clic sur start.bat
echo   Mettre a jour    : double-clic sur update.bat
echo.
pause
