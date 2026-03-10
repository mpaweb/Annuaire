# Changelog — Annuaire Neoedge Web

## Comment mettre à jour

**Double-cliquez sur `update.bat`** — c'est tout.

Le script s'occupe de :
1. Télécharger les nouveaux fichiers (git pull)
2. Mettre à jour les dépendances Python
3. Migrer la base de données si nécessaire
4. Proposer de relancer l'application

---

## v1.2 — Thème, Logo, Sauvegardes améliorées

**Fichiers modifiés :**
- `app/models.py` — nouveaux modèles Backup et AppSetting, champ theme sur User
- `app/routes/admin.py` — routes logo, thème, historique sauvegardes, restauration
- `app/static/css/app.css` — variables CSS thème clair/sombre/système
- `app/static/js/app.js` — logique thème, logo, sauvegardes
- `app/templates/index.html` — sélecteur thème, zone logo, tableau sauvegardes

**Nouveautés :**
- Thème System / Light / Dark avec persistance par utilisateur
- Upload de logo (PNG, JPG, SVG, WEBP) avec drag & drop
- Historique des sauvegardes avec téléchargement et restauration
- Sauvegarde de sécurité automatique avant chaque restauration
- Scripts update.bat / setup.bat / start.bat

**Migration base requise :** oui (nouvelles tables `backups` et `app_settings`)

---

## v1.1 — Version initiale

- Contacts et ROC (CRUD complet)
- Export PDF / Excel / CSV
- Scanner de doublons
- Gestion des utilisateurs et droits (admin/editor/viewer)
- Logs d'audit
- Migration SQLite → PostgreSQL
