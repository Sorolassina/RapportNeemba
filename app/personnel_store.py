"""
Tableaux de référence RH qui ne sont PAS rattachés à un technicien en
particulier : Recrutement annuel, Objectifs de certifiés, Cap&Cap, Départs.

Ces données ont été importées une fois depuis le classeur Excel
"01_Suivi_du_personnel_v13.8.xlsm" (onglets Recrutement, Objectif, Cap&Cap,
Départ1), qui est désormais abandonné : ces tableaux sont maintenant gérés
en CRUD complet directement dans l'application (comme les fiches
techniciens dans app/techniciens_store.py, seule source de vérité pour tout
ce qui concerne un technicien précis).

NB : l'onglet "Départ1" du classeur d'origine était lui-même une formule
cassée (#REF!, cf. note historique) pointant vers un fichier externe non
fourni ; la table a donc été réinitialisée vide et se remplit désormais
uniquement depuis l'application.
"""
import json
import uuid
from pathlib import Path
from threading import Lock
from typing import Optional

_PERSONNEL_DIR = Path(__file__).resolve().parent / "data" / "personnel"
_PERSONNEL_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()
_cache: dict = {}

_FILES = {
    "recrutement": _PERSONNEL_DIR / "recrutement.json",
    "objectifs": _PERSONNEL_DIR / "objectifs.json",
    "cap_and_cap": _PERSONNEL_DIR / "cap_and_cap.json",
    "departs": _PERSONNEL_DIR / "departs.json",
}

# Champs éditables pour chaque table (utilisés pour construire les formulaires)
FIELDS = {
    "recrutement": ["Code société", "Effectué", "Prévision", "Validé"],
    "objectifs": [
        "Code société", "Niveau", "Année en cours", "2022", "2023", "2024",
        "2025", "2026", "2027", "2028", "Mini", "Maxi",
        "Résultats 2025", "Résultat 2026",
    ],
    "cap_and_cap": [
        "Pays", "Service", "Niveau", "Année en cours", "2022", "2023",
        "2024", "2025", "2026", "2027", "2028",
    ],
    "departs": [
        "Nom / Prénom", "Mtle", "Code société", "Statut", "Service",
        "Poste harmonisé TCDP", "Type Contrat", "Ancienneté", "Année entrée",
        "Date de sortie", "Raison 1", "Raison 2",
        "Niveau Atelier actuel", "Niveau Atelier Cible",
        "Niveau CDF validé", "Niveau CDF en cours",
    ],
}


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def _load(table: str) -> dict:
    path = _FILES[table]
    mtime = _mtime(path)
    entry = _cache.get(table)
    if entry and entry[0] == mtime:
        return entry[1]
    data = {"headers": FIELDS[table], "records": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    _cache[table] = (mtime, data)
    return data


def _save(table: str, data: dict) -> None:
    with _LOCK:
        _FILES[table].write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _cache.pop(table, None)


def list_table(table: str) -> list:
    return _load(table)["records"]


def save_row(table: str, row: dict) -> dict:
    data = _load(table)
    records = data["records"]
    row_id = row.get("id")
    if row_id:
        for i, r in enumerate(records):
            if r.get("id") == row_id:
                records[i] = {**r, **row}
                _save(table, data)
                return records[i]
    row = {**row, "id": _new_id()}
    records.append(row)
    _save(table, data)
    return row


def delete_row(table: str, row_id: str) -> None:
    data = _load(table)
    data["records"] = [r for r in data["records"] if r.get("id") != row_id]
    _save(table, data)


# ──────────────────────────────────────────────────────────────────────────
# Raccourcis par table (utilisés par app/personnel_analysis.py et les routes)
# ──────────────────────────────────────────────────────────────────────────

def list_departs() -> list:
    return list_table("departs")


def list_recrutement() -> list:
    return list_table("recrutement")


def list_objectifs() -> list:
    return list_table("objectifs")


def list_cap_and_cap() -> list:
    return list_table("cap_and_cap")
