"""
Stockage pour le module Ressources (médiathèque de supports de formation) :
métadonnées en JSON (même principe que les autres stores du projet) et
fichiers physiques dans app/static/uploads/ressources/{id}/ — sous
app/static car ces supports sont destinés à être consultés/téléchargés
directement via une URL, contrairement aux données des autres modules.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import UploadFile

_APP_DIR = Path(__file__).resolve().parent
_DATA_DIR = _APP_DIR / "data" / "ressources"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_UPLOAD_ROOT = _APP_DIR / "static" / "uploads" / "ressources"
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()
_FILE = _DATA_DIR / "ressources.json"

CATEGORIES = [
    "hydraulique", "moteur", "electrique", "transmission",
    "train_roulement", "climatisation", "securite", "onboarding", "autre",
]
CATEGORIE_LABELS = {
    "hydraulique": "Hydraulique", "moteur": "Moteur", "electrique": "Électrique",
    "transmission": "Transmission", "train_roulement": "Train roulant",
    "climatisation": "Climatisation", "securite": "Sécurité", "onboarding": "Onboarding",
    "autre": "Autre",
}
NIVEAUX = ["debutant", "intermediaire", "avance"]
NIVEAU_LABELS = {"debutant": "Débutant", "intermediaire": "Intermédiaire", "avance": "Avancé"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> list:
    if not _FILE.exists():
        return []
    try:
        raw = _FILE.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: list) -> None:
    with _LOCK:
        _FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _sanitize(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return name[:120] or "fichier"


def list_ressources(categorie: Optional[str] = None) -> list:
    items = _load()
    if categorie:
        items = [x for x in items if x.get("categorie") == categorie]
    return sorted(items, key=lambda x: x.get("created_at") or "", reverse=True)


def get_ressource(item_id: str) -> Optional[dict]:
    return next((x for x in _load() if x.get("id") == item_id), None)


def save_ressource_file(meta: dict, file: UploadFile) -> dict:
    """Enregistre le fichier physique et ses métadonnées, retourne l'entrée créée."""
    item_id = _new_id()
    item_dir = _UPLOAD_ROOT / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    fname = _sanitize(file.filename or f"support-{item_id}")
    dest = item_dir / fname
    content = file.file.read()
    with open(dest, "wb") as f:
        f.write(content)

    entry = {
        **meta,
        "id": item_id,
        "fichier_nom": fname,
        "fichier_url": f"/static/uploads/ressources/{item_id}/{fname}",
        "taille_octets": len(content),
        "extension": (fname.rsplit(".", 1)[-1].lower() if "." in fname else ""),
        "created_at": _now(),
    }
    items = _load()
    items.append(entry)
    _save(items)
    return entry


def delete_ressource(item_id: str) -> None:
    items = _load()
    entry = next((x for x in items if x.get("id") == item_id), None)
    _save([x for x in items if x.get("id") != item_id])
    if entry:
        item_dir = _UPLOAD_ROOT / item_id
        try:
            if item_dir.exists():
                for f in item_dir.iterdir():
                    f.unlink(missing_ok=True)
                item_dir.rmdir()
        except OSError:
            pass


def icon_for_extension(ext: str) -> str:
    ext = (ext or "").lower()
    if ext == "pdf":
        return "picture_as_pdf"
    if ext in ("ppt", "pptx"):
        return "slideshow"
    if ext in ("doc", "docx"):
        return "description"
    if ext in ("xls", "xlsx", "csv"):
        return "table_chart"
    if ext in ("mp4", "mov", "avi", "mkv", "webm"):
        return "movie"
    if ext in ("jpg", "jpeg", "png", "gif", "webp"):
        return "image"
    if ext in ("zip", "rar", "7z"):
        return "folder_zip"
    return "attach_file"


def repartition_categories(items: Optional[list] = None) -> list:
    data = items if items is not None else _load()
    counts: dict = {}
    for r in data:
        c = r.get("categorie") or "autre"
        counts[c] = counts.get(c, 0) + 1
    return sorted(
        ({"categorie": k, "label": CATEGORIE_LABELS.get(k, k), "nb": v} for k, v in counts.items()),
        key=lambda r: r["nb"], reverse=True,
    )
