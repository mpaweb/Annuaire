# Guide de déploiement — Annuaire Neoedge Web

## Prérequis sur votre poste Windows

- Python 3.11+ installé
- Git installé
- Un compte GitHub (gratuit)
- Un compte Railway (gratuit) : https://railway.app

---

## Étape 1 — Installer les dépendances localement

Ouvrez un terminal (PowerShell ou CMD) dans le dossier `annuaire-web` :

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Étape 2 — Configurer le fichier .env

Copiez `.env.example` en `.env` et adaptez :

```powershell
copy .env.example .env
```

Éditez `.env` :

```
SECRET_KEY=une-longue-chaine-aleatoire-ici
DATABASE_URL=postgresql://user:password@localhost:5432/annuaire
FLASK_ENV=development
ADMIN_USERNAME=admin
ADMIN_PASSWORD=VotreMotDePasseSecurise
ADMIN_EMAIL=votre@email.fr
```

> Pour générer une SECRET_KEY :
> `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Étape 3 — Tester en local (optionnel)

Pour tester sans PostgreSQL, utilisez SQLite (déjà configuré si DATABASE_URL pointe vers sqlite) :

```powershell
python -c "from app import create_app; create_app()"
flask --app "app:create_app()" run --debug
```

Accédez à http://localhost:5000 et connectez-vous avec admin / votre mot de passe.

---

## Étape 4 — Migrer votre base SQLite existante

1. Lancez une dernière fois `annuaire_v96.py` pour qu'il déchiffre la base.
2. Le fichier temporaire déchiffré est dans le dossier TEMP de Windows.
   Ou : modifiez `annuaire_v96.py` pour exporter en clair via `Sauvegarder` → copie locale.
3. Placez ce fichier `.db` dans le dossier `annuaire-web/` sous le nom `annuaire.db`.
4. Lancez la migration :

```powershell
# D'abord configurer DATABASE_URL dans .env vers votre PostgreSQL
python migrate_sqlite.py --dry-run    # aperçu sans modifier
python migrate_sqlite.py              # migration réelle
```

---

## Étape 5 — Déployer sur Railway

### 5a — Créer le dépôt GitHub

```powershell
git init
git add .
git commit -m "Initial commit — Annuaire Neoedge Web"
```

Créez un dépôt sur https://github.com/new (privé recommandé), puis :

```powershell
git remote add origin https://github.com/VOTRE_NOM/annuaire-web.git
git push -u origin main
```

### 5b — Créer le projet sur Railway

1. Allez sur https://railway.app → **New Project**
2. Choisissez **Deploy from GitHub repo** → sélectionnez votre dépôt
3. Railway détecte automatiquement Python via `Procfile`

### 5c — Ajouter PostgreSQL

Dans votre projet Railway :
1. Cliquez **+ New** → **Database** → **PostgreSQL**
2. Railway crée automatiquement la variable `DATABASE_URL`

### 5d — Configurer les variables d'environnement

Dans Railway → votre service → **Variables**, ajoutez :

| Clé | Valeur |
|-----|--------|
| `SECRET_KEY` | votre clé secrète (32+ caractères) |
| `ADMIN_USERNAME` | admin |
| `ADMIN_PASSWORD` | votre mot de passe admin |
| `ADMIN_EMAIL` | votre email |
| `FLASK_ENV` | production |

> `DATABASE_URL` est ajoutée automatiquement par Railway via le service PostgreSQL.

### 5e — Déployer

Railway redémarre automatiquement à chaque push Git.
Le premier déploiement prend ~2 minutes.

Votre application sera accessible sur une URL du type :
`https://annuaire-web-production.up.railway.app`

---

## Étape 6 — Migrer les données vers Railway PostgreSQL

Après le premier déploiement, Railway expose un port PostgreSQL accessible depuis l'extérieur.

Dans Railway → votre service PostgreSQL → **Connect** → copiez la **Public URL**.

Mettez à jour votre `.env` local avec cette URL, puis :

```powershell
python migrate_sqlite.py
```

---

## Gestion des utilisateurs

Connectez-vous avec le compte admin, allez dans **🗄️ Administration** → **Utilisateurs**.

Rôles disponibles :
- **admin** : accès complet, gestion des utilisateurs, logs, sauvegardes
- **editor** : lecture + création + modification + suppression des données
- **viewer** : lecture seule (pas de modification possible)

---

## Mises à jour

Pour déployer une mise à jour :

```powershell
git add .
git commit -m "Description de la mise à jour"
git push
```

Railway redéploie automatiquement en quelques secondes.

---

## Sauvegarde

- **Automatique** : Railway propose des sauvegardes PostgreSQL dans son interface
- **Manuelle** : Administration → **💾 Sauvegarde JSON** (télécharge un fichier JSON complet)
- **Planifiée** : configurable dans Railway (snapshots quotidiens)
