# app/versioning.py
import os
import subprocess
from datetime import datetime

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
