"""
Stockage léger (fichiers JSON) pour le module Terrain & SAV :
fiches de rapport de dépannage et audits des besoins trimestriels
par concessionnaire.

Même principe que app/academie_store.py : pas de base de données,
fichiers hors de app/static pour ne jamais être exposés publiquement.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent / "data" / "terrain"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()

_FILES = {
    "depannages": _DATA_DIR / "depannages.json",
    "audits": _DATA_DIR / "audits_besoins.json",
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
# Fiches de rapport de dépannage
# ──────────────────────────────────────────────────────────────────────────

def list_depannages() -> list:
    return sorted(_load("depannages"), key=lambda x: x.get("date") or "", reverse=True)


def get_depannage(item_id: str) -> Optional[dict]:
    return next((x for x in _load("depannages") if x.get("id") == item_id), None)


def save_depannage(data: dict) -> dict:
    items = _load("depannages")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("depannages", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("depannages", items)
    return data


def delete_depannage(item_id: str) -> None:
    _save("depannages", [x for x in _load("depannages") if x.get("id") != item_id])


def repartition_pannes(depannages: Optional[list] = None) -> list:
    """Répartition des interventions par système concerné, triée décroissant."""
    items = depannages if depannages is not None else _load("depannages")
    counts: dict = {}
    for d in items:
        sys_ = d.get("systeme_concerne") or "Non renseigné"
        counts[sys_] = counts.get(sys_, 0) + 1
    total = len(items)
    rows = [
        {"systeme": k, "nb": v, "pct": round(v / total * 100) if total else 0}
        for k, v in counts.items()
    ]
    return sorted(rows, key=lambda r: r["nb"], reverse=True)


# ──────────────────────────────────────────────────────────────────────────
# Audit des besoins trimestriel
# ──────────────────────────────────────────────────────────────────────────

def list_audits() -> list:
    return sorted(_load("audits"), key=lambda x: x.get("date_appel") or "", reverse=True)


def get_audit(item_id: str) -> Optional[dict]:
    return next((x for x in _load("audits") if x.get("id") == item_id), None)


def save_audit(data: dict) -> dict:
    items = _load("audits")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("audits", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("audits", items)
    return data


def delete_audit(item_id: str) -> None:
    _save("audits", [x for x in _load("audits") if x.get("id") != item_id])
