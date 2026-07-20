"""
Stockage léger (fichiers JSON) pour le module Techniciens :
fiche technicien, test de recrutement, journal de tâches quotidiennes
(intégration des 6 premiers mois), suivi périodique.

Même principe que app/academie_store.py : pas de base de données,
fichiers hors de app/static pour ne jamais être exposés publiquement.
"""
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent / "data" / "techniciens"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()

_FILES = {
    "techniciens": _DATA_DIR / "techniciens.json",
    "tests": _DATA_DIR / "tests_recrutement.json",
    "taches": _DATA_DIR / "taches_quotidiennes.json",
    "suivis": _DATA_DIR / "suivis.json",
}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(name: str) -> list:
    p = _FILES[name]
    if not p.exists():
        return []
    try:
        raw = p.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(name: str, items: list) -> None:
    p = _FILES[name]
    with _LOCK:
        p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


# ──────────────────────────────────────────────────────────────────────────
# Fiche technicien
# ──────────────────────────────────────────────────────────────────────────

def list_techniciens() -> list:
    return sorted(_load("techniciens"), key=lambda x: (x.get("nom") or "").lower())


def get_technicien(item_id: str) -> Optional[dict]:
    return next((x for x in _load("techniciens") if x.get("id") == item_id), None)


def save_technicien(data: dict) -> dict:
    items = _load("techniciens")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("techniciens", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("techniciens", items)
    return data


def delete_technicien(item_id: str) -> None:
    _save("techniciens", [x for x in _load("techniciens") if x.get("id") != item_id])
    _save("tests", [x for x in _load("tests") if x.get("technicien_id") != item_id])
    _save("taches", [x for x in _load("taches") if x.get("technicien_id") != item_id])
    _save("suivis", [x for x in _load("suivis") if x.get("technicien_id") != item_id])


# ──────────────────────────────────────────────────────────────────────────
# Test de recrutement
# ──────────────────────────────────────────────────────────────────────────

def list_tests(technicien_id: Optional[str] = None) -> list:
    items = _load("tests")
    if technicien_id:
        items = [x for x in items if x.get("technicien_id") == technicien_id]
    return sorted(items, key=lambda x: x.get("date") or "", reverse=True)


def save_test(data: dict) -> dict:
    items = _load("tests")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("tests", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("tests", items)
    return data


def delete_test(item_id: str) -> None:
    _save("tests", [x for x in _load("tests") if x.get("id") != item_id])


# ──────────────────────────────────────────────────────────────────────────
# Journal de tâches quotidiennes (intégration 6 premiers mois)
# ──────────────────────────────────────────────────────────────────────────

def list_taches(technicien_id: Optional[str] = None) -> list:
    items = _load("taches")
    if technicien_id:
        items = [x for x in items if x.get("technicien_id") == technicien_id]
    return sorted(items, key=lambda x: x.get("date") or "", reverse=True)


def save_tache(data: dict) -> dict:
    items = _load("taches")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("taches", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("taches", items)
    return data


def delete_tache(item_id: str) -> None:
    _save("taches", [x for x in _load("taches") if x.get("id") != item_id])


def semaine_integration(date_embauche: Optional[str], date_tache: Optional[str]) -> Optional[int]:
    """Numéro de semaine d'intégration (1 à ~26) à partir de la date d'embauche."""
    if not date_embauche or not date_tache:
        return None
    try:
        d0 = date.fromisoformat(date_embauche[:10])
        d1 = date.fromisoformat(date_tache[:10])
    except ValueError:
        return None
    delta = (d1 - d0).days
    if delta < 0:
        return None
    return (delta // 7) + 1


# ──────────────────────────────────────────────────────────────────────────
# Suivi périodique du technicien
# ──────────────────────────────────────────────────────────────────────────

def list_suivis(technicien_id: Optional[str] = None) -> list:
    items = _load("suivis")
    if technicien_id:
        items = [x for x in items if x.get("technicien_id") == technicien_id]
    return sorted(items, key=lambda x: x.get("date") or "", reverse=True)


def save_suivi(data: dict) -> dict:
    items = _load("suivis")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("suivis", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("suivis", items)
    return data


def delete_suivi(item_id: str) -> None:
    _save("suivis", [x for x in _load("suivis") if x.get("id") != item_id])
