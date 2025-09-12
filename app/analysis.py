import pandas as pd, os
from .charts import build_grouped_bars, build_deltas
from .storage import get_session_dir


def _to_disk_path(web_path: str) -> str:
    """
    Mappe un chemin web /static/... vers le chemin disque app/static/...
    Laisse passer tel quel si ce n'est pas un chemin /static.
    """
    if not web_path:
        return ""
    p = web_path.lstrip("/")  # enlève le "/" initial
    if p.startswith("static/"):
        return os.path.join("app", p).replace("/", os.sep)
    return web_path

def _read_any(path: str) -> pd.DataFrame:
    p = path.lower()
    if p.endswith(".xlsx") or p.endswith(".xls"):
        return pd.read_excel(path)
    # try ; or , separators for csv
    try:
        return pd.read_csv(path, sep=";")
    except Exception:
        return pd.read_csv(path, sep=",")

def analyze_excel(excel_web_path: str, sid: str):
    # excel_web_path is like /static/uploads/{sid}/file.xlsx -> map to disk
    disk_path = _to_disk_path(excel_web_path)  # static is served from project root
    df = _read_any(disk_path)
    df.columns = [c.strip().lower() for c in df.columns]

    # attempt to find columns
    col_name = None
    for cand in ["stagiaire", "stagaire", "participant", "nom"]:
        if cand in df.columns:
            col_name = cand; break
    col_in = None
    for cand in ["test_in", "in", "pretest", "avant"]:
        if cand in df.columns:
            col_in = cand; break
    col_out = None
    for cand in ["test_out", "out", "posttest", "apres", "après"]:
        if cand in df.columns:
            col_out = cand; break

    if not all([col_name, col_in, col_out]):
        # fallback: take first 3 cols
        cols = list(df.columns)[:3]
        col_name, col_in, col_out = cols[0], cols[1], cols[2]

    df = df[[col_name, col_in, col_out]].dropna()
    df.columns = ["stagiaire", "in", "out"]
    df["in"] = pd.to_numeric(df["in"], errors="coerce")
    df["out"] = pd.to_numeric(df["out"], errors="coerce")
    df = df.dropna()

    # KPIs
    moy_in = round(df["in"].mean(), 1)
    moy_out = round(df["out"].mean(), 1)
    evolution = round(moy_out - moy_in, 1)
    df["delta"] = df["out"] - df["in"]
    top_plus = df.sort_values("delta", ascending=False).head(3)
    top_moins = df.sort_values("delta", ascending=True).head(3)

    session_dir = get_session_dir(sid)
    bars_disk = os.path.join(session_dir, "bars.png")
    deltas_disk = os.path.join(session_dir, "deltas.png")

    bars_web = "/static/uploads/{}/bars.png".format(sid)
    deltas_web = "/static/uploads/{}/deltas.png".format(sid)

    build_grouped_bars(df, bars_disk)
    build_deltas(df, deltas_disk)

    interp = "baisse de performance après la formation" if evolution < 0 else "amélioration après la formation"
    trend_pct = round((evolution / (moy_in if moy_in else 1)) * 100, 1) if moy_in else evolution

    return {
        "kpi": {"moy_in": moy_in, "moy_out": moy_out, "evolution": evolution, "evolution_pct": trend_pct, "interpretation": interp},
        "top_plus": top_plus.to_dict(orient="records"),
        "top_moins": top_moins.to_dict(orient="records"),
        "charts": {"bars": bars_web, "deltas": deltas_web},
        "table": df.to_dict(orient="records")
    }

def _detect_mapping(columns: list[str]) -> dict:
    cols = [c.strip().lower() for c in columns]
    name_col = next((c for c in ["stagiaire","stagaire","participant","nom"] if c in cols), None)
    in_col   = next((c for c in ["test_in","in","pretest","avant"] if c in cols), None)
    out_col  = next((c for c in ["test_out","out","posttest","apres","après"] if c in cols), None)
    return {"name": name_col, "in": in_col, "out": out_col}

def preview_excel(excel_web_path: str, limit: int = 10) -> dict:
    """Renvoie un aperçu (colonnes + 10 premières lignes) sans calculer les KPI."""
    if not excel_web_path:
        return {"columns": [], "rows": [], "mapping": {}}
    disk_path = _to_disk_path(excel_web_path)  # /static/... -> chemin disque relatif
    
    if not os.path.exists(disk_path):
        return {"columns": [], "rows": [], "mapping": {}, "error": f"Fichier introuvable: {disk_path}"}

    df = _read_any(disk_path)
    df.columns = [c.strip() for c in df.columns]
    mapping = _detect_mapping(list(df.columns))
    
    # Vérifier si toutes les colonnes attendues sont trouvées
    missing_columns = []
    if not mapping.get("name"):
        missing_columns.append("nom du stagiaire")
    if not mapping.get("in"):
        missing_columns.append("test d'entrée")
    if not mapping.get("out"):
        missing_columns.append("test de sortie")
    
    warning_message = None
    if missing_columns:
        warning_message = f"⚠️ Colonnes manquantes détectées : {', '.join(missing_columns)}. Cela peut affecter la qualité des analyses."
    
    sample = df.head(limit).fillna("").astype(str)
    return {
        "columns": list(sample.columns),
        "rows": sample.to_dict(orient="records"),
        "mapping": mapping,
        "warning": warning_message
    }
