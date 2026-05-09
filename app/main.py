
import os
import logging
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
from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uuid, json, os, time

from app.storage import get_session_dir, save_upload, load_context, save_context
from app.analysis import analyze_excel
from app.pdf import render_pdf
from app.templates.default import with_defaults
from reportlab_report import generate_reportlab
from app.versionning import get_app_version

app = FastAPI(root_path="/neembacoaching",title="NEMBA GROUP – Générateur de rapports de formation")
APP_VERSION = get_app_version()
print(f"DEBUG - Démarrage nemba-report version {APP_VERSION}")
# Assure que ROOT_PATH est défini pour les templates et les URLs statiques
os.environ["ROOT_PATH"] = app.root_path or ""
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["asset_version"] = APP_VERSION  #usage direct: {{ asset_version }}
#Cache des sessions actives pour éviter les conflits
_active_sessions = {}
_session_timeout = 3600  # 1 heure

@app.get("/version", response_class=PlainTextResponse)
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

@app.get("/health")
@app.head("/health")
async def health_check():
    return {"status": "ok", "service": "nemba-report"}

# ------------------ Web UI ------------------
@app.get("/home", response_class=HTMLResponse)
@app.get("/")
@app.head("/")
async def wizard(request: Request):
    # Nettoyer les sessions expirées
    cleanup_expired_sessions()
    
    # Générer une session sécurisée
    sid = request.cookies.get("sid") or generate_secure_session()
    resp = templates.TemplateResponse("wizard.html", {"request": request})
    #resp.set_cookie("sid", sid, httponly=True, samesite="Lax")
    resp.set_cookie(
    "sid", sid,
    httponly=True,
    samesite="Lax",
    path=app.root_path or "/"   # <- clé !
)
    return resp

# ------------------ Uploads ------------------
@app.post("/upload")
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
@app.post("/analyze")
async def analyze(request: Request, payload: str = Form(...)):
    sid = request.cookies.get("sid")
    data = json.loads(payload)
    excel_path = data.get("excel_path")
    import logging
    from app.analysis import _to_disk_path
    disk_path = _to_disk_path(excel_path)
    logging.info(f"ANALYZE: sid={sid}, excel_path={excel_path}, disk_path={disk_path}")
    if not os.path.exists(disk_path):
        logging.warning(f"ANALYZE: Fichier non trouvé sur le disque: {disk_path}")
        return {"ok": False, "error": f"Fichier non trouvé: {disk_path}"}
    # Toujours passer le chemin web original à l'analyse (pas le chemin disque)
    kpis = analyze_excel(excel_path, sid) if excel_path else {}
    
    # Vérifier si l'analyse a retourné une erreur
    if kpis.get("error"):
        return {"ok": False, "error": kpis["error"]}
    
    ctx = {**data, **kpis}
    save_context(sid, ctx)
    return {"ok": True, "kpis": kpis}

# ------------------ Prévisualisation ------------------
# dans la route preview
@app.get("/preview", response_class=HTMLResponse)
async def preview(request: Request):
    sid = request.cookies.get("sid")
    ctx = load_context(sid)
    ctx = with_defaults(ctx)  # <-- important
    return templates.TemplateResponse("report.html", {"request": request, **ctx})

# ------------------ Mode d'emploi ------------------
@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})

# ------------------ Guide de déploiement ------------------
@app.get("/deployment", response_class=HTMLResponse)
async def deployment_page(request: Request):
    return templates.TemplateResponse("deployment.html", {"request": request})

# ------------------ Génération PDF ------------------
"""@app.post("/generate")
async def generate(request: Request):
    sid = request.cookies.get("sid")
    pdf_path = render_pdf("report.html", sid)
    return FileResponse(pdf_path, media_type="application/pdf", filename="rapport_nemba.pdf")"""

from fastapi.responses import JSONResponse
from fastapi import Body

@app.post("/preview-excel")
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

@app.post("/generate-reportlab")
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


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
