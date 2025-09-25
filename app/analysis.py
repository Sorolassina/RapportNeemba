import os
import pandas as pd
from .charts import build_grouped_bars, build_deltas
from .storage import get_session_dir

# --- Helpers root_path -------------------------------------------------
def _root_path() -> str:
    """
    Récupère le root_path pour les URLs web.
    - Lecture depuis la variable d'environnement ROOT_PATH si définie (ex: "/neembacoaching")
    - Sinon "", c.-à-d. racine.
    """
    rp = os.environ.get("ROOT_PATH", "").strip()
    if rp and not rp.startswith("/"):
        rp = "/" + rp
    return rp.rstrip("/")  # "/neembacoaching" ou ""

def web_static(rel_path: str) -> str:
    """
    Construit une URL web vers /static/... en respectant le root_path.
    Exemple: web_static("uploads/sid/bars.png") -> "/neembacoaching/static/uploads/sid/bars.png"
    """
    rp = _root_path()
    rel = rel_path.lstrip("/")
    return f"{rp}/static/{rel}"

def _to_disk_path(web_path: str) -> str:
    """
    Mappe un chemin web (avec ou sans root_path) vers le chemin disque.
    Accepte:
      - "/static/…"
      - "/neembacoaching/static/…"
      - "static/…"
    Retourne: "app/static/…"
    Si ce n'est pas un chemin statique reconnu, renvoie tel quel.
    """
    if not web_path:
        return ""

    p = web_path.strip().lstrip("/").replace("\\", "/")  # normalise
    # Cherche le segment "static/" dans le chemin
    idx = p.find("static/")
    if idx == -1:
        # rien à mapper: retourne le chemin tel quel (peut être un chemin absolu disque)
        return web_path

    # Extrait la partie après "static/"
    after_static = p[idx + len("static/") :]
    # Construit le chemin disque sous app/static/...
    return os.path.join("app", "static", after_static.replace("/", os.sep))

# --- IO ----------------------------------------------------------------
def _read_any(path: str) -> pd.DataFrame:
    p = (path or "").lower()
    if p.endswith(".xlsx") or p.endswith(".xls"):
        return pd.read_excel(path)
    # CSV: on tente ";" puis ","
    try:
        return pd.read_csv(path, sep=";")
    except Exception:
        return pd.read_csv(path, sep=",")

# --- Analyse -----------------------------------------------------------
def analyze_excel(excel_web_path: str, sid: str) -> dict:
    """
    Analyse un fichier Excel/CSV uploadé (chemin web vers disque),
    calcule quelques KPI et génère deux graphes.
    Renvoie un payload prêt à être consommé par le front (URLs web root_path aware).
    """
    # Map web -> disque (supporte /neembacoaching/static/... et /static/...)
    disk_path = _to_disk_path(excel_web_path)
    if not os.path.exists(disk_path):
        raise FileNotFoundError(f"Fichier introuvable: {disk_path}")

    df = _read_any(disk_path)
    df.columns = [c.strip().lower() for c in df.columns]

    # Heuristique: détection des colonnes
    col_name = next((c for c in ["stagiaire", "stagaire", "participant", "nom"] if c in df.columns), None)
    col_in   = next((c for c in ["test_in", "in", "pretest", "avant"] if c in df.columns), None)
    col_out  = next((c for c in ["test_out", "out", "posttest", "apres", "après"] if c in df.columns), None)

    if not all([col_name, col_in, col_out]):
        # fallback simple: les 3 premières colonnes
        cols = list(df.columns)[:3]
        if len(cols) < 3:
            raise ValueError("Fichier insuffisant: moins de 3 colonnes détectées.")
        col_name, col_in, col_out = cols[0], cols[1], cols[2]

    df = df[[col_name, col_in, col_out]].dropna()
    df.columns = ["stagiaire", "in", "out"]
    df["in"] = pd.to_numeric(df["in"], errors="coerce")
    df["out"] = pd.to_numeric(df["out"], errors="coerce")
    df = df.dropna()

    # KPI
    moy_in = round(df["in"].mean(), 1) if not df.empty else 0.0
    moy_out = round(df["out"].mean(), 1) if not df.empty else 0.0
    evolution = round(moy_out - moy_in, 1)
    df["delta"] = df["out"] - df["in"]
    top_plus = df.sort_values("delta", ascending=False).head(3)
    top_moins = df.sort_values("delta", ascending=True).head(3)

    # Fichiers charts
    session_dir = get_session_dir(sid)  # ex: app/static/uploads/<sid>
    os.makedirs(session_dir, exist_ok=True)
    bars_disk = os.path.join(session_dir, "bars.png")
    deltas_disk = os.path.join(session_dir, "deltas.png")

    # URLs web (root_path aware)
    bars_web = web_static(f"uploads/{sid}/bars.png")
    deltas_web = web_static(f"uploads/{sid}/deltas.png")

    # Génération des graphes
    build_grouped_bars(df, bars_disk)
    build_deltas(df, deltas_disk)

    interp = "baisse de performance après la formation" if evolution < 0 else "amélioration après la formation"
    trend_pct = round((evolution / (moy_in if moy_in else 1)) * 100, 1) if moy_in else evolution

    return {
        "kpi": {
            "moy_in": moy_in,
            "moy_out": moy_out,
            "evolution": evolution,
            "evolution_pct": trend_pct,
            "interpretation": interp,
        },
        "top_plus": top_plus.to_dict(orient="records"),
        "top_moins": top_moins.to_dict(orient="records"),
        "charts": {"bars": bars_web, "deltas": deltas_web},
        "table": df.to_dict(orient="records"),
    }

def _detect_mapping(columns: list[str]) -> dict:
    cols = [c.strip().lower() for c in columns]
    name_col = next((c for c in ["stagiaire","stagaire","participant","nom"] if c in cols), None)
    in_col   = next((c for c in ["test_in","in","pretest","avant"] if c in cols), None)
    out_col  = next((c for c in ["test_out","out","posttest","apres","après"] if c in cols), None)
    return {"name": name_col, "in": in_col, "out": out_col}

def preview_excel(excel_web_path: str, limit: int = 10) -> dict:
    """
    Renvoie un aperçu (colonnes + 10 premières lignes) sans calculer les KPI.
    Accepte des chemins web avec ou sans root_path (*/static/...).
    """
    if not excel_web_path:
        return {"columns": [], "rows": [], "mapping": {}}

    disk_path = _to_disk_path(excel_web_path)

    if not os.path.exists(disk_path):
        return {
            "columns": [], "rows": [], "mapping": {},
            "error": f"Fichier introuvable: {disk_path}"
        }

    df = _read_any(disk_path)
    df.columns = [c.strip() for c in df.columns]
    mapping = _detect_mapping(list(df.columns))

    missing = []
    if not mapping.get("name"): missing.append("nom du stagiaire")
    if not mapping.get("in"):   missing.append("test d'entrée")
    if not mapping.get("out"):  missing.append("test de sortie")

    warning_message = None
    if missing:
        warning_message = f"⚠️ Colonnes manquantes détectées : {', '.join(missing)}. Cela peut affecter la qualité des analyses."

    sample = df.head(limit).fillna("").astype(str)
    return {
        "columns": list(sample.columns),
        "rows": sample.to_dict(orient="records"),
        "mapping": mapping,
        "warning": warning_message,
    }
