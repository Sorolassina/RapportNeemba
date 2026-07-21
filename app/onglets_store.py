"""
CRUD générique pour tous les onglets des deux classeurs Excel qui n'ont pas
de store dédié plus riche (Base 1 / Base 2 / Recrutement / Objectif /
Cap&Cap / Départ1 sont gérés dans app/personnel_store.py et
app/techniciens_store.py — OJT (1) et le Référentiel de compétences aussi).

Chaque onglet restant (calculs, historiques, extractions par marque/machine,
etc.) est traité de la même façon : une liste d'enregistrements identifiés
par un "id", éditable directement dans l'application (création,
modification, suppression) — plus de vue Excel en lecture seule : ce sont de
vraies données manipulables, comme le reste de l'application.

Données générées par scripts/import_remaining_sheets.py.
"""
import json
import uuid
from pathlib import Path
from threading import Lock
from typing import Optional

_BASE_DIR = Path(__file__).resolve().parent / "data" / "onglets"

_LOCK = Lock()
_cache: dict = {}

FICHIERS = {
    "personnel": {"dir": _BASE_DIR / "personnel", "label": "01 — Suivi du personnel"},
    "tutorat": {"dir": _BASE_DIR / "tutorat", "label": "02 — Suivi du tutorat"},
}


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def _sheet_path(fichier: str, sheet_file: str) -> Optional[Path]:
    if fichier not in FICHIERS:
        return None
    return FICHIERS[fichier]["dir"] / sheet_file


def list_fichiers() -> list:
    return [{"cle": cle, "label": v["label"]} for cle, v in FICHIERS.items()]


def get_index(fichier: str) -> Optional[dict]:
    if fichier not in FICHIERS:
        return None
    path = FICHIERS[fichier]["dir"] / "_index.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load(fichier: str, sheet_file: str) -> Optional[dict]:
    path = _sheet_path(fichier, sheet_file)
    if not path or not path.exists():
        return None
    key = (fichier, sheet_file)
    mtime = _mtime(path)
    entry = _cache.get(key)
    if entry and entry[0] == mtime:
        return entry[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    _cache[key] = (mtime, data)
    return data


def _save(fichier: str, sheet_file: str, data: dict) -> None:
    path = _sheet_path(fichier, sheet_file)
    with _LOCK:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _cache.pop((fichier, sheet_file), None)


def get_sheet(fichier: str, sheet_file: str) -> Optional[dict]:
    return _load(fichier, sheet_file)


def list_rows(fichier: str, sheet_file: str) -> list:
    data = _load(fichier, sheet_file)
    return data["records"] if data else []


def get_headers(fichier: str, sheet_file: str) -> list:
    data = _load(fichier, sheet_file)
    return data["headers"] if data else []


def save_row(fichier: str, sheet_file: str, row: dict) -> Optional[dict]:
    data = _load(fichier, sheet_file)
    if data is None:
        return None
    records = data["records"]
    row_id = row.get("id")
    if row_id:
        for i, r in enumerate(records):
            if r.get("id") == row_id:
                records[i] = {**r, **row}
                _save(fichier, sheet_file, data)
                return records[i]
    row = {**row, "id": _new_id()}
    records.append(row)
    _save(fichier, sheet_file, data)
    return row


def delete_row(fichier: str, sheet_file: str, row_id: str) -> None:
    data = _load(fichier, sheet_file)
    if data is None:
        return
    data["records"] = [r for r in data["records"] if r.get("id") != row_id]
    _save(fichier, sheet_file, data)
