# app/versioning.py
import os
import subprocess
from datetime import datetime
from pathlib import Path

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def get_app_version() -> str:
    # 1) Priorité à une variable d'env posée au déploiement
    v = os.environ.get("APP_VERSION")
    if v:
        return v.strip()

    # 2) Sinon, court SHA git si dispo
    try:
        v = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        if v:
            return v
    except Exception:
        pass

    # 3) Sinon, timestamp (pratique en dev)
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def asset_v(path: str) -> str:
    """Cache-bust version pour un asset statique (basée sur son mtime).

    Usage dans Jinja :  href="{{ url_for('static', path='css/tailwind.css') }}?v={{ asset_v('css/tailwind.css') }}"

    Avantages vs asset_version global :
    - Invalidation automatique à chaque rebuild (pas besoin de commit ni de
      redémarrer le serveur si on est en mode --reload).
    - Granularité par fichier : changer le CSS ne réinvalide pas le JS, etc.

    Fallback sur la version applicative si le fichier est absent.
    """
    file_path = _STATIC_DIR / path
    try:
        return str(int(file_path.stat().st_mtime))
    except (OSError, ValueError):
        return get_app_version()
