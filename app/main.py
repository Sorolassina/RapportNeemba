from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uuid, json, os, time

from .storage import get_session_dir, save_upload, load_context, save_context
from .analysis import analyze_excel
from .pdf import render_pdf
from .templates.default import with_defaults
from reportlab_report import generate_reportlab


app = FastAPI(title="NEMBA GROUP – Générateur de rapports de formation")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Cache des sessions actives pour éviter les conflits
_active_sessions = {}
_session_timeout = 3600  # 1 heure

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
@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def wizard(request: Request):
    # Nettoyer les sessions expirées
    cleanup_expired_sessions()
    
    # Générer une session sécurisée
    sid = request.cookies.get("sid") or generate_secure_session()
    resp = templates.TemplateResponse("wizard.html", {"request": request})
    resp.set_cookie("sid", sid, httponly=True, samesite="Lax")
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
    kpis = analyze_excel(excel_path, sid) if excel_path else {}
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

# ------------------ Génération PDF ------------------
@app.post("/generate")
async def generate(request: Request):
    sid = request.cookies.get("sid")
    pdf_path = render_pdf("report.html", sid)
    return FileResponse(pdf_path, media_type="application/pdf", filename="rapport_nemba.pdf")

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
    
    out = generate_reportlab(sid)
    # Extraire le nom du fichier du chemin complet
    filename = os.path.basename(out)
    return FileResponse(out, media_type="application/pdf", filename=filename)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
