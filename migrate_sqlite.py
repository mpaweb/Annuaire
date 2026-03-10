#!/usr/bin/env python3
"""
Migration SQLite → PostgreSQL
==============================
Utilisation :

  1. Assurez-vous que .env est configuré avec DATABASE_URL (PostgreSQL)
  2. Déchiffrez d'abord votre base : l'annuaire_v96 crée un fichier tmp au démarrage.
     Copiez le fichier SQLite déchiffré sous le nom annuaire.db dans le même dossier.
  3. Lancez : python migrate_sqlite.py --sqlite annuaire.db

Options :
  --sqlite    chemin vers la base SQLite (défaut: annuaire.db)
  --dry-run   affiche ce qui serait importé sans toucher à PostgreSQL
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Dépendances Flask ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from app import create_app, db
from app.models import Contact, Roc


def migrate(sqlite_path: str, dry_run: bool = False) -> None:
    if not Path(sqlite_path).exists():
        print(f"[ERREUR] Fichier introuvable : {sqlite_path}")
        sys.exit(1)

    print(f"[INFO] Connexion à la base SQLite : {sqlite_path}")
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── Contacts ──────────────────────────────────────────────────────────────
    cur.execute("SELECT * FROM contacts WHERE id IS NOT NULL")
    contacts_rows = cur.fetchall()
    print(f"[INFO] {len(contacts_rows)} contact(s) trouvé(s) dans SQLite")

    # ── ROC ───────────────────────────────────────────────────────────────────
    cur.execute("SELECT * FROM rocs WHERE id IS NOT NULL")
    rocs_rows = cur.fetchall()
    print(f"[INFO] {len(rocs_rows)} ROC(s) trouvé(s) dans SQLite")
    conn.close()

    if dry_run:
        print("[DRY-RUN] Aucune modification effectuée.")
        _preview_contacts(contacts_rows[:5])
        return

    app = create_app()
    with app.app_context():
        # Vider les tables cibles (si migration fraîche)
        existing_c = Contact.query.count()
        existing_r = Roc.query.count()
        if existing_c > 0 or existing_r > 0:
            ans = input(
                f"[ATTENTION] La base PostgreSQL contient déjà {existing_c} contact(s) "
                f"et {existing_r} ROC(s).\n"
                "Voulez-vous les supprimer avant d'importer ? (oui/non) : "
            ).strip().lower()
            if ans == "oui":
                Contact.query.delete()
                Roc.query.delete()
                db.session.commit()
                print("[INFO] Tables vidées.")
            else:
                print("[INFO] Import annulé.")
                return

        # ── Importer contacts ─────────────────────────────────────────────────
        cols_c = _get_columns(contacts_rows)
        imported_c = 0
        for row in contacts_rows:
            c = Contact(
                societe    = _get(row, cols_c, "societe",    ""),
                nom        = _get(row, cols_c, "nom",        ""),
                prenom     = _get(row, cols_c, "prenom",     ""),
                fonction   = _get(row, cols_c, "fonction",   ""),
                email      = _get(row, cols_c, "email",      ""),
                telephone  = _get(row, cols_c, "telephone",  ""),
                telephone2 = _get(row, cols_c, "telephone2", ""),
                notes      = _get(row, cols_c, "notes",      ""),
                updated_by = "migration",
            )
            db.session.add(c)
            imported_c += 1

        # ── Importer ROC ──────────────────────────────────────────────────────
        cols_r = _get_columns(rocs_rows)
        imported_r = 0
        for row in rocs_rows:
            r = Roc(
                nom_client               = _get(row, cols_r, "nom_client",               ""),
                roc                      = _get(row, cols_r, "roc",                      ""),
                trinity                  = _get(row, cols_r, "trinity",                  ""),
                infogerance              = _get(row, cols_r, "infogerance",              ""),
                astreinte                = _get(row, cols_r, "astreinte",                ""),
                type_contrat             = _get(row, cols_r, "type_contrat",             ""),
                date_anniversaire_contrat= _get(row, cols_r, "date_anniversaire_contrat",""),
                updated_by               = "migration",
            )
            db.session.add(r)
            imported_r += 1

        db.session.commit()
        print(f"[OK] {imported_c} contact(s) importé(s).")
        print(f"[OK] {imported_r} ROC(s) importé(s).")
        print("[OK] Migration terminée avec succès !")


def _get_columns(rows) -> list[str]:
    if not rows:
        return []
    return [description[0] for description in rows[0].keys()]


def _get(row, cols, key, default=""):
    try:
        val = row[key]
        return str(val).strip() if val is not None else default
    except (KeyError, IndexError):
        return default


def _preview_contacts(rows) -> None:
    print("\n[APERÇU] 5 premiers contacts :")
    for row in rows:
        keys = row.keys()
        print(f"  • {row['societe'] if 'societe' in keys else '?'} / "
              f"{row['nom'] if 'nom' in keys else '?'} "
              f"{row['prenom'] if 'prenom' in keys else '?'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migration SQLite → PostgreSQL")
    parser.add_argument("--sqlite",  default="annuaire.db",
                        help="Chemin vers la base SQLite source")
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche les données sans importer")
    args = parser.parse_args()
    migrate(args.sqlite, args.dry_run)
