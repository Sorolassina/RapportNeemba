
import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, Form, APIRouter, Body
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import json
import time

from app.storage import save_upload, load_context, save_context
from app.analysis import analyze_excel
from app.templates.default import with_defaults
from reportlab_report import generate_reportlab
from app.versionning import get_app_version, asset_v

# ──────────────────────────────────────────────────────────────────────────────
# Chargement du .env (zéro dépendance) — DOIT s'exécuter avant tout le reste
# pour que ROOT_PATH / APP_VERSION / PORT / SECRET_KEY soient disponibles
# au moment où FastAPI est instancié.
# ──────────────────────────────────────────────────────────────────────────────
def _load_dotenv_once() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def _normalize_root_path(value: str) -> str:
    """Normalise ROOT_PATH : "" si vide, sinon "/xxx" sans slash final."""
    rp = (value or "").strip()
    if not rp:
        return ""
    if not rp.startswith("/"):
        rp = "/" + rp
    return rp.rstrip("/")


_load_dotenv_once()
ROOT_PATH = _normalize_root_path(os.environ.get("ROOT_PATH", ""))
os.environ["ROOT_PATH"] = ROOT_PATH  # version normalisée pour les autres modules

LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..', 'logs', 'log-sderr.log'))
PYTHON_LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..', 'logs', 'log-python.log'))

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(PYTHON_LOG_PATH), exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    encoding='utf-8',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.FileHandler(PYTHON_LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


app = FastAPI(title="NEMBA GROUP – Générateur de rapports de formation")
APP_VERSION = get_app_version()
print(f"DEBUG - Démarrage nemba-report version {APP_VERSION} (ROOT_PATH={ROOT_PATH or '/'})")

# Chemins absolus dérivés de __file__ : robustes contre le cwd du process
_APP_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _APP_DIR / "static"
_TEMPLATES_DIR = _APP_DIR / "templates"

# ──────────────────────────────────────────────────────────────────────────────
# ROOT_PATH (préfixe d'URL) lu depuis l'environnement. Si défini (ex.
# "/neembacoaching"), TOUTES les routes et le mount static sont préfixés
# en conséquence, ce qui permet à cloudflared (ou tout reverse proxy)
# d'exposer l'app sous ce préfixe sans rewrite, et à un accès local direct
# (http://127.0.0.1:8000/neembacoaching/...) de fonctionner aussi.
# Si ROOT_PATH est vide, l'app se comporte normalement à la racine.
# ──────────────────────────────────────────────────────────────────────────────
app.mount(
    f"{ROOT_PATH}/static" if ROOT_PATH else "/static",
    StaticFiles(directory=str(_STATIC_DIR)),
    name="static",
)
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals["asset_version"] = APP_VERSION  # usage direct: {{ asset_version }}
templates.env.globals["asset_v"] = asset_v  # cache-bust par fichier: {{ asset_v('css/tailwind.css') }}
templates.env.globals["root_path"] = ROOT_PATH  # préfixe d'URL pour les liens absolus

# Toutes les routes applicatives passent par ce router préfixé pour qu'elles
# soient automatiquement servies sous ROOT_PATH si défini.
router = APIRouter(prefix=ROOT_PATH)

# Cache des sessions actives pour éviter les conflits
_active_sessions = {}
_session_timeout = 3600  # 1 heure


@router.get("/version", response_class=PlainTextResponse)
def version():
    return APP_VERSION


def generate_secure_session():
    """Génère une session sécurisée avec timestamp."""
    session_id = str(uuid.uuid4())
    _active_sessions[session_id] = time.time()
    return session_id

def cleanup_expired_sessions():
    """Nettoie les sessions expirées."""
    current_time = time.time()
    expired_sessions = [
        sid for sid, timestamp in _active_sessions.items()
        if current_time - timestamp > _session_timeout
    ]
    for sid in expired_sessions:
        del _active_sessions[sid]
        print(f"DEBUG - Session expirée nettoyée: {sid}")

# ------------------ Health Check ------------------

@router.get("/health")
@router.head("/health")
async def health_check():
    return {"status": "ok", "service": "nemba-report"}

# ------------------ Web UI ------------------
@router.get("/", response_class=HTMLResponse)
@router.head("/")
async def intro(request: Request):
    """Page d'animation d'entrée (~4,5 s) puis redirection vers /home."""
    home_url = (ROOT_PATH or "") + "/home"
    return templates.TemplateResponse(
        "intro.html",
        {"request": request, "home_url": home_url},
    )

@router.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    """Page d'accueil (landing Neemba Academy)."""
    return templates.TemplateResponse("home.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Tableaux de bord Power BI."""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/rapport", response_class=HTMLResponse)
async def wizard(request: Request):
    """Générateur de rapports de formation (wizard 6 étapes)."""
    cleanup_expired_sessions()

    sid = request.cookies.get("sid") or generate_secure_session()
    resp = templates.TemplateResponse("wizard.html", {"request": request})
    resp.set_cookie(
        "sid", sid,
        httponly=True,
        samesite="Lax",
        path=ROOT_PATH or "/",
    )
    return resp

# ------------------ Uploads ------------------
@router.post("/upload")
async def upload(request: Request, file: UploadFile):
    sid = request.cookies.get("sid")
    if not sid:
        sid = str(uuid.uuid4())
    try:
        path = save_upload(sid, file)
        return {"ok": True, "path": path}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

# ------------------ Analyse ------------------
@router.post("/analyze")
async def analyze(request: Request, payload: str = Form(...)):
    sid = request.cookies.get("sid")
    data = json.loads(payload)
    excel_path = data.get("excel_path")
    from app.analysis import _to_disk_path
    disk_path = _to_disk_path(excel_path)
    logging.info(f"ANALYZE: sid={sid}, excel_path={excel_path}, disk_path={disk_path}")
    if not os.path.exists(disk_path):
        logging.warning(f"ANALYZE: Fichier non trouvé sur le disque: {disk_path}")
        return {"ok": False, "error": f"Fichier non trouvé: {disk_path}"}
    kpis = analyze_excel(excel_path, sid) if excel_path else {}

    if kpis.get("error"):
        return {"ok": False, "error": kpis["error"]}

    ctx = {**data, **kpis}
    save_context(sid, ctx)
    return {"ok": True, "kpis": kpis}

# ------------------ Prévisualisation ------------------
@router.get("/preview", response_class=HTMLResponse)
async def preview(request: Request):
    sid = request.cookies.get("sid")
    ctx = load_context(sid)
    ctx = with_defaults(ctx)
    return templates.TemplateResponse("report.html", {"request": request, **ctx})

# ------------------ Mode d'emploi ------------------
@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})

# ------------------ Guide de déploiement ------------------
@router.get("/deployment", response_class=HTMLResponse)
async def deployment_page(request: Request):
    return templates.TemplateResponse("deployment.html", {"request": request})

# ------------------ Génération PDF ------------------
@router.post("/preview-excel")
async def preview_excel_route(payload: dict = Body(...)):
    from .analysis import preview_excel
    excel_path = payload.get("excel_path")
    try:
        data = preview_excel(excel_path, limit=10)
        if data.get("error"):
            return JSONResponse({"ok": False, **data}, status_code=400)
        return {"ok": True, **data}
    except FileNotFoundError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"Lecture impossible: {e}"}, status_code=400)

@router.post("/generate-reportlab")
async def generate_reportlab_pdf(request: Request):
    sid = request.cookies.get("sid")
    print(f"DEBUG - generate_reportlab_pdf appelée avec sid: {sid}")
    
    # Récupérer les données JSON du body de la requête
    try:
        data = await request.json()
        # Sauvegarder les données dans le fichier context.json
        context_path = f"app/static/uploads/{sid}/context.json"
        os.makedirs(os.path.dirname(context_path), exist_ok=True)
        with open(context_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"DEBUG - Données sauvegardées pour {sid}: {data}")
        
        # Vérifier que le fichier a été écrit
        if os.path.exists(context_path):
            print(f"DEBUG - Fichier context.json créé avec succès")
        else:
            print(f"DEBUG - ERREUR: Fichier context.json non créé")
            
    except Exception as e:
        print(f"Erreur lors de la récupération des données: {e}")
    
    try:
        print(f"DEBUG - Début génération PDF dans main.py...")
        out = generate_reportlab(sid)
        print(f"DEBUG - PDF généré avec succès dans main.py: {out}")
        
        if not out:
            return JSONResponse({"error": "Erreur lors de la génération du PDF"}, status_code=500)
            
        # Extraire le nom du fichier du chemin complet
        filename = os.path.basename(out)
        print(f"DEBUG - Nom du fichier généré: {filename}")
        
        # Créer la réponse avec le bon header Content-Disposition
        response = FileResponse(out, media_type="application/pdf", filename=filename)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        print(f"DEBUG - ERREUR dans main.py: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"Erreur lors de la génération du PDF: {str(e)}"}, status_code=500)


# Enregistrement final du routeur (après définition de toutes les routes).
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
