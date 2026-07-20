
import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, Form, APIRouter, Body
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uuid
import json
import time
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from app.storage import save_upload, load_context, save_context
from app.analysis import analyze_excel
from app.templates.default import with_defaults
from reportlab_report import generate_reportlab
from app.versionning import get_app_version, asset_v
from app import academie_store
from app import techniciens_store
from app import terrain_store
from app import ressources_store
from app import rapports_store
from app import dashboard_store

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


app = FastAPI(title="LiuGong Academy – Générateur de rapports de formation")
APP_VERSION = get_app_version()
print(f"DEBUG - Démarrage liugong-academy version {APP_VERSION} (ROOT_PATH={ROOT_PATH or '/'})")

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


def _toast_redirect(url: str, message: str, toast_type: str = "success", status_code: int = 303) -> RedirectResponse:
    """RedirectResponse enrichi d'un toast (?toast=...&toast_type=...) lu et affiché
    côté client par base_v2.html au chargement de la page, puis retiré de l'URL.
    Préserve les paramètres de requête déjà présents (ex. ?mois=2026-07)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["toast"] = message
    query["toast_type"] = toast_type
    new_query = urlencode(query)
    new_url = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    return RedirectResponse(url=new_url, status_code=status_code)


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
    return {"status": "ok", "service": "liugong-academy"}

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
    """Page d'accueil (landing LiuGong Academy)."""
    return templates.TemplateResponse("home.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Tableau de bord : KPI et graphiques calculés en direct depuis les modules."""
    data = dashboard_store.get_dashboard_data()
    return templates.TemplateResponse("dashboard.html", {"request": request, "data": data})

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

# ------------------ Rapports & Pilotage ------------------
@router.get("/rapports", response_class=HTMLResponse)
async def rapports_hub(request: Request, mois: str = None):
    mois = mois or datetime.now().strftime("%Y-%m")
    data = rapports_store.get_monthly_activity(mois)
    synthese = rapports_store.get_synthese(mois)
    historique = [h for h in rapports_store.list_syntheses() if h.get("mois") != mois]
    return templates.TemplateResponse(
        "rapports_hub.html",
        {"request": request, "mois": mois, "data": data, "synthese": synthese, "historique": historique},
    )

@router.post("/rapports/synthese")
async def rapports_synthese_save(request: Request):
    form = await request.form()
    mois = form.get("mois") or datetime.now().strftime("%Y-%m")
    rapports_store.save_synthese(
        mois,
        (form.get("faits_marquants") or "").strip(),
        (form.get("actions_prochain_mois") or "").strip(),
    )
    return _toast_redirect(f"{ROOT_PATH}/rapports?mois={mois}", "Synthèse enregistrée")

# ------------------ Ressources : Médiathèque ------------------
def _human_size(n: int) -> str:
    n = n or 0
    for unit in ["o", "Ko", "Mo", "Go"]:
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"

@router.get("/ressources", response_class=HTMLResponse)
async def ressources_hub(request: Request, categorie: str = None):
    raw_items = ressources_store.list_ressources(categorie)
    items = [
        {
            **it,
            "taille_str": _human_size(it.get("taille_octets", 0)),
            "icon": ressources_store.icon_for_extension(it.get("extension")),
        }
        for it in raw_items
    ]
    total = len(ressources_store.list_ressources())
    return templates.TemplateResponse(
        "ressources_hub.html",
        {
            "request": request, "items": items, "total": total,
            "current_categorie": categorie,
            "categories": ressources_store.CATEGORIES,
            "categorie_labels": ressources_store.CATEGORIE_LABELS,
            "niveaux": ressources_store.NIVEAUX,
            "niveau_labels": ressources_store.NIVEAU_LABELS,
        },
    )

@router.post("/ressources/upload")
async def ressources_upload(
    request: Request,
    titre: str = Form(...),
    description: str = Form(""),
    categorie: str = Form("autre"),
    niveau: str = Form("debutant"),
    type_formation: str = Form("client"),
    fichier: UploadFile = None,
):
    if fichier is not None:
        meta = {
            "titre": titre.strip(),
            "description": description.strip(),
            "categorie": categorie,
            "niveau": niveau,
            "type_formation": type_formation,
        }
        ressources_store.save_ressource_file(meta, fichier)
    return _toast_redirect(f"{ROOT_PATH}/ressources", "Support ajouté à la médiathèque")

@router.post("/ressources/{item_id}/delete")
async def ressources_delete(item_id: str):
    ressources_store.delete_ressource(item_id)
    return _toast_redirect(f"{ROOT_PATH}/ressources", "Support supprimé", "info")

# ------------------ Terrain & SAV : Hub ------------------
@router.get("/terrain", response_class=HTMLResponse)
async def terrain_hub(request: Request):
    depannages = terrain_store.list_depannages()
    audits = terrain_store.list_audits()
    repartition = terrain_store.repartition_pannes(depannages)
    nb_besoin_formation = len([d for d in depannages if d.get("necessite_formation")])
    return templates.TemplateResponse(
        "terrain_hub.html",
        {
            "request": request,
            "nb_depannages": len(depannages),
            "nb_audits": len(audits),
            "nb_besoin_formation": nb_besoin_formation,
            "repartition": repartition[:6],
        },
    )

# ------------------ Terrain & SAV : Rapports de dépannage ------------------
@router.get("/terrain/depannage", response_class=HTMLResponse)
async def terrain_depannage(request: Request, edit: str = None):
    items = terrain_store.list_depannages()
    edit_item = terrain_store.get_depannage(edit) if edit else None
    return templates.TemplateResponse(
        "terrain_depannage.html",
        {"request": request, "items": items, "edit_item": edit_item},
    )

@router.post("/terrain/depannage/save")
async def terrain_depannage_save(request: Request):
    form = await request.form()
    data = {
        "id": form.get("id") or None,
        "date": form.get("date") or "",
        "concessionnaire": (form.get("concessionnaire") or "").strip(),
        "technicien_intervenant": (form.get("technicien_intervenant") or "").strip(),
        "engin": (form.get("engin") or "").strip(),
        "numero_serie": (form.get("numero_serie") or "").strip(),
        "systeme_concerne": form.get("systeme_concerne") or "autre",
        "description_panne": (form.get("description_panne") or "").strip(),
        "diagnostic": (form.get("diagnostic") or "").strip(),
        "intervention_realisee": (form.get("intervention_realisee") or "").strip(),
        "pieces_remplacees": (form.get("pieces_remplacees") or "").strip(),
        "duree_heures": form.get("duree_heures") or "",
        "statut": form.get("statut") or "resolu",
        "necessite_formation": form.get("necessite_formation") == "1",
        "notes": (form.get("notes") or "").strip(),
    }
    if not data["id"]:
        data.pop("id")
    terrain_store.save_depannage(data)
    return _toast_redirect(f"{ROOT_PATH}/terrain/depannage", "Fiche de dépannage enregistrée")

@router.post("/terrain/depannage/{item_id}/delete")
async def terrain_depannage_delete(item_id: str):
    terrain_store.delete_depannage(item_id)
    return _toast_redirect(f"{ROOT_PATH}/terrain/depannage", "Fiche de dépannage supprimée", "info")

# ------------------ Terrain & SAV : Audit des besoins trimestriel ------------------
@router.get("/terrain/audit-besoins", response_class=HTMLResponse)
async def terrain_audit(request: Request, edit: str = None):
    items = terrain_store.list_audits()
    edit_item = terrain_store.get_audit(edit) if edit else None
    return templates.TemplateResponse(
        "terrain_audit.html",
        {"request": request, "items": items, "edit_item": edit_item},
    )

@router.post("/terrain/audit-besoins/save")
async def terrain_audit_save(request: Request):
    form = await request.form()
    data = {
        "id": form.get("id") or None,
        "trimestre": form.get("trimestre") or "",
        "date_appel": form.get("date_appel") or "",
        "concessionnaire": (form.get("concessionnaire") or "").strip(),
        "interlocuteur": (form.get("interlocuteur") or "").strip(),
        "pannes_recurrentes": (form.get("pannes_recurrentes") or "").strip(),
        "besoins_formation_identifies": (form.get("besoins_formation_identifies") or "").strip(),
        "niveau_urgence": form.get("niveau_urgence") or "moyen",
        "suivi_prevu": (form.get("suivi_prevu") or "").strip(),
        "commentaire": (form.get("commentaire") or "").strip(),
    }
    if not data["id"]:
        data.pop("id")
    terrain_store.save_audit(data)
    return _toast_redirect(f"{ROOT_PATH}/terrain/audit-besoins", "Audit enregistré")

@router.post("/terrain/audit-besoins/{item_id}/delete")
async def terrain_audit_delete(item_id: str):
    terrain_store.delete_audit(item_id)
    return _toast_redirect(f"{ROOT_PATH}/terrain/audit-besoins", "Audit supprimé", "info")

# ------------------ Techniciens : Hub ------------------
@router.get("/techniciens", response_class=HTMLResponse)
async def techniciens_hub(request: Request):
    items = techniciens_store.list_techniciens()
    return templates.TemplateResponse("techniciens_hub.html", {"request": request, "items": items})

@router.post("/techniciens/save")
async def techniciens_save(request: Request):
    form = await request.form()
    data = {
        "id": form.get("id") or None,
        "nom": (form.get("nom") or "").strip(),
        "prenom": (form.get("prenom") or "").strip(),
        "concessionnaire": (form.get("concessionnaire") or "").strip(),
        "poste": (form.get("poste") or "").strip(),
        "telephone": (form.get("telephone") or "").strip(),
        "date_embauche": form.get("date_embauche") or "",
        "statut": form.get("statut") or "candidat",
        "notes": (form.get("notes") or "").strip(),
    }
    if not data["id"]:
        data.pop("id")
    tech = techniciens_store.save_technicien(data)
    return _toast_redirect(f"{ROOT_PATH}/techniciens/{tech['id']}", "Technicien enregistré")

@router.post("/techniciens/{item_id}/delete")
async def techniciens_delete(item_id: str):
    techniciens_store.delete_technicien(item_id)
    return _toast_redirect(f"{ROOT_PATH}/techniciens", "Technicien supprimé", "info")

# ------------------ Techniciens : Profil (détail) ------------------
@router.get("/techniciens/{item_id}", response_class=HTMLResponse)
async def techniciens_detail(request: Request, item_id: str, edit_test: str = None, edit_suivi: str = None):
    tech = techniciens_store.get_technicien(item_id)
    if not tech:
        return _toast_redirect(f"{ROOT_PATH}/techniciens", "Technicien introuvable", "error")
    tests = techniciens_store.list_tests(item_id)
    taches = techniciens_store.list_taches(item_id)
    suivis = techniciens_store.list_suivis(item_id)

    taches_par_semaine = {}
    for t in taches:
        sem = techniciens_store.semaine_integration(tech.get("date_embauche"), t.get("date"))
        t["semaine"] = sem
        key = sem if sem is not None else "?"
        taches_par_semaine.setdefault(key, []).append(t)
    semaines_triees = sorted(taches_par_semaine.keys(), key=lambda k: (k == "?", k), reverse=True)

    return templates.TemplateResponse(
        "technicien_detail.html",
        {
            "request": request, "tech": tech, "tests": tests, "suivis": suivis,
            "taches_par_semaine": taches_par_semaine, "semaines_triees": semaines_triees,
            "edit_test": next((t for t in tests if t["id"] == edit_test), None) if edit_test else None,
            "edit_suivi": next((s for s in suivis if s["id"] == edit_suivi), None) if edit_suivi else None,
        },
    )

@router.post("/techniciens/{item_id}/test/save")
async def techniciens_test_save(request: Request, item_id: str):
    form = await request.form()
    data = {
        "id": form.get("id") or None,
        "technicien_id": item_id,
        "date": form.get("date") or "",
        "note_theorique": form.get("note_theorique") or "",
        "note_pratique": form.get("note_pratique") or "",
        "note_comportementale": form.get("note_comportementale") or "",
        "decision": form.get("decision") or "en_attente",
        "commentaire": (form.get("commentaire") or "").strip(),
    }
    if not data["id"]:
        data.pop("id")
    techniciens_store.save_test(data)
    return _toast_redirect(f"{ROOT_PATH}/techniciens/{item_id}#test", "Test de recrutement enregistré")

@router.post("/techniciens/{item_id}/test/{test_id}/delete")
async def techniciens_test_delete(item_id: str, test_id: str):
    techniciens_store.delete_test(test_id)
    return _toast_redirect(f"{ROOT_PATH}/techniciens/{item_id}#test", "Test supprimé", "info")

@router.post("/techniciens/{item_id}/tache/save")
async def techniciens_tache_save(request: Request, item_id: str):
    form = await request.form()
    data = {
        "technicien_id": item_id,
        "date": form.get("date") or "",
        "tache": (form.get("tache") or "").strip(),
        "statut": form.get("statut") or "fait",
        "commentaire": (form.get("commentaire") or "").strip(),
    }
    techniciens_store.save_tache(data)
    return _toast_redirect(f"{ROOT_PATH}/techniciens/{item_id}#integration", "Tâche enregistrée")

@router.post("/techniciens/{item_id}/tache/{tache_id}/delete")
async def techniciens_tache_delete(item_id: str, tache_id: str):
    techniciens_store.delete_tache(tache_id)
    return _toast_redirect(f"{ROOT_PATH}/techniciens/{item_id}#integration", "Tâche supprimée", "info")

@router.post("/techniciens/{item_id}/suivi/save")
async def techniciens_suivi_save(request: Request, item_id: str):
    form = await request.form()
    data = {
        "id": form.get("id") or None,
        "technicien_id": item_id,
        "date": form.get("date") or "",
        "evaluation": form.get("evaluation") or "",
        "points_forts": (form.get("points_forts") or "").strip(),
        "axes_progres": (form.get("axes_progres") or "").strip(),
        "actions": (form.get("actions") or "").strip(),
        "prochain_rdv": form.get("prochain_rdv") or "",
    }
    if not data["id"]:
        data.pop("id")
    techniciens_store.save_suivi(data)
    return _toast_redirect(f"{ROOT_PATH}/techniciens/{item_id}#suivi", "Suivi enregistré")

@router.post("/techniciens/{item_id}/suivi/{suivi_id}/delete")
async def techniciens_suivi_delete(item_id: str, suivi_id: str):
    techniciens_store.delete_suivi(suivi_id)
    return _toast_redirect(f"{ROOT_PATH}/techniciens/{item_id}#suivi", "Suivi supprimé", "info")

# ------------------ Académie : Hub ------------------
@router.get("/academie", response_class=HTMLResponse)
async def academie_hub(request: Request):
    planning_items = academie_store.list_planning()
    questionnaires = academie_store.list_questionnaires()
    total_reponses = len(academie_store.list_reponses())
    return templates.TemplateResponse(
        "academie_hub.html",
        {
            "request": request,
            "nb_planning": len(planning_items),
            "nb_evaluations": len(academie_store.list_evaluations()),
            "nb_questionnaires_actifs": len([q for q in questionnaires if q.get("actif", True)]),
            "nb_reponses": total_reponses,
        },
    )

# ------------------ Académie : Planning annuel ------------------
@router.get("/academie/planning", response_class=HTMLResponse)
async def academie_planning(request: Request, edit: str = None, granularite: str = None):
    items = academie_store.list_planning()
    edit_item = academie_store.get_planning(edit) if edit else None
    valid_granularites = {"semaine", "mois", "trimestre", "semestre", "annee"}
    granularite = granularite if granularite in valid_granularites else "trimestre"
    gantt = academie_store.compute_gantt(items, granularite)
    return templates.TemplateResponse(
        "academie_planning.html",
        {"request": request, "items": items, "edit_item": edit_item, "gantt": gantt},
    )

@router.post("/academie/planning/save")
async def academie_planning_save(request: Request):
    form = await request.form()
    data = {
        "id": form.get("id") or None,
        "titre": (form.get("titre") or "").strip(),
        "type_session": form.get("type_session") or "client",
        "client_nom": (form.get("client_nom") or "").strip(),
        "lieu": (form.get("lieu") or "").strip(),
        "formateur": (form.get("formateur") or "").strip(),
        "date_debut": form.get("date_debut") or "",
        "date_fin": form.get("date_fin") or "",
        "participants_prevus": form.get("participants_prevus") or "",
        "statut": form.get("statut") or "planifie",
        "notes": (form.get("notes") or "").strip(),
    }
    if not data["id"]:
        data.pop("id")
    academie_store.save_planning_item(data)
    return _toast_redirect(f"{ROOT_PATH}/academie/planning", "Session de formation enregistrée")

@router.post("/academie/planning/{item_id}/delete")
async def academie_planning_delete(item_id: str):
    academie_store.delete_planning_item(item_id)
    return _toast_redirect(f"{ROOT_PATH}/academie/planning", "Session supprimée", "info")

# ------------------ Académie : Évaluation de la formation (côté formateur) ------------------
@router.get("/academie/evaluation", response_class=HTMLResponse)
async def academie_evaluation(request: Request, edit: str = None):
    items = academie_store.list_evaluations()
    edit_item = academie_store.get_evaluation(edit) if edit else None
    planning_items = academie_store.list_planning()
    return templates.TemplateResponse(
        "academie_evaluation.html",
        {"request": request, "items": items, "edit_item": edit_item, "planning_items": planning_items},
    )

@router.post("/academie/evaluation/save")
async def academie_evaluation_save(request: Request):
    form = await request.form()
    data = {
        "id": form.get("id") or None,
        "planning_id": form.get("planning_id") or "",
        "titre_formation": (form.get("titre_formation") or "").strip(),
        "date": form.get("date") or "",
        "note_contenu": form.get("note_contenu") or "",
        "note_pedagogie": form.get("note_pedagogie") or "",
        "note_logistique": form.get("note_logistique") or "",
        "note_participation": form.get("note_participation") or "",
        "points_forts": (form.get("points_forts") or "").strip(),
        "points_ameliorer": (form.get("points_ameliorer") or "").strip(),
        "recommandations": (form.get("recommandations") or "").strip(),
    }
    if not data["id"]:
        data.pop("id")
    academie_store.save_evaluation(data)
    return _toast_redirect(f"{ROOT_PATH}/academie/evaluation", "Évaluation enregistrée")

@router.post("/academie/evaluation/{item_id}/delete")
async def academie_evaluation_delete(item_id: str):
    academie_store.delete_evaluation(item_id)
    return _toast_redirect(f"{ROOT_PATH}/academie/evaluation", "Évaluation supprimée", "info")

# ------------------ Académie : Questionnaire QR code (gestion) ------------------
def _public_link(request: Request, token: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}{ROOT_PATH}/q/{token}"

def _qr_image_url(link: str) -> str:
    from urllib.parse import quote
    return f"https://api.qrserver.com/v1/create-qr-code/?size=220x220&data={quote(link, safe='')}"

@router.get("/academie/questionnaire", response_class=HTMLResponse)
async def academie_questionnaire(request: Request):
    planning_items = academie_store.list_planning()
    raw_items = academie_store.list_questionnaires()
    items = []
    for it in raw_items:
        link = _public_link(request, it["token"])
        items.append({
            **it,
            "public_link": link,
            "qr_image_url": _qr_image_url(link),
            "nb_reponses": len(academie_store.list_reponses(it["token"])),
        })
    return templates.TemplateResponse(
        "academie_questionnaire.html",
        {"request": request, "items": items, "planning_items": planning_items},
    )

@router.post("/academie/questionnaire/create")
async def academie_questionnaire_create(request: Request):
    form = await request.form()
    data = {
        "planning_id": form.get("planning_id") or "",
        "titre_formation": (form.get("titre_formation") or "").strip(),
    }
    academie_store.create_questionnaire(data)
    return _toast_redirect(f"{ROOT_PATH}/academie/questionnaire", "Questionnaire QR créé")

@router.post("/academie/questionnaire/{token}/toggle")
async def academie_questionnaire_toggle(token: str):
    q = academie_store.get_questionnaire(token)
    if q:
        academie_store.set_questionnaire_actif(token, not q.get("actif", True))
    return _toast_redirect(f"{ROOT_PATH}/academie/questionnaire", "Statut mis à jour")

@router.post("/academie/questionnaire/{token}/delete")
async def academie_questionnaire_delete(token: str):
    academie_store.delete_questionnaire(token)
    return _toast_redirect(f"{ROOT_PATH}/academie/questionnaire", "Questionnaire supprimé", "info")

# ------------------ Académie : Questionnaire QR code (page publique stagiaire) ------------------
@router.get("/q/{token}", response_class=HTMLResponse)
async def questionnaire_public(request: Request, token: str, merci: int = 0):
    questionnaire = academie_store.get_questionnaire(token)
    return templates.TemplateResponse(
        "questionnaire_public.html",
        {"request": request, "questionnaire": questionnaire, "merci": bool(merci)},
    )

@router.post("/q/{token}/submit")
async def questionnaire_public_submit(request: Request, token: str):
    questionnaire = academie_store.get_questionnaire(token)
    if questionnaire and questionnaire.get("actif", True):
        form = await request.form()
        data = {
            "note_contenu": form.get("note_contenu") or "",
            "note_pedagogie": form.get("note_pedagogie") or "",
            "note_logistique": form.get("note_logistique") or "",
            "utile_travail": form.get("utile_travail") or "",
            "recommanderiez": form.get("recommanderiez") or "",
            "points_forts": (form.get("points_forts") or "").strip(),
            "suggestions": (form.get("suggestions") or "").strip(),
        }
        academie_store.add_reponse(token, data)
    return RedirectResponse(url=f"{ROOT_PATH}/q/{token}?merci=1", status_code=303)

# ------------------ Académie : Statistiques QR + plan d'action mensuel ------------------
def _dist(reponses: list, field: str, options: list) -> dict:
    total = len(reponses)
    counts = {opt: 0 for opt in options}
    for r in reponses:
        v = r.get(field)
        if v in counts:
            counts[v] += 1
    pct = {opt: (round(counts[opt] / total * 100) if total else 0) for opt in options}
    return {"counts": counts, "pct": pct}

def _compute_stats(reponses: list) -> dict:
    note_options = ["passable", "assez-bien", "bien", "tres-bien"]
    utile_options = ["non", "plutot-non", "plutot-oui", "oui"]
    reco_options = ["non", "oui"]

    stats = {
        "total": len(reponses),
        "note_contenu": _dist(reponses, "note_contenu", note_options),
        "note_pedagogie": _dist(reponses, "note_pedagogie", note_options),
        "note_logistique": _dist(reponses, "note_logistique", note_options),
        "utile_travail": _dist(reponses, "utile_travail", utile_options),
        "recommanderiez": _dist(reponses, "recommanderiez", reco_options),
    }

    good, total_notes = 0, 0
    for field in ["note_contenu", "note_pedagogie", "note_logistique"]:
        for r in reponses:
            v = r.get(field)
            if v:
                total_notes += 1
                if v in ("bien", "tres-bien"):
                    good += 1
    stats["taux_satisfaction"] = round(good / total_notes * 100) if total_notes else 0
    stats["taux_recommandation"] = stats["recommanderiez"]["pct"].get("oui", 0)

    monthly = defaultdict(list)
    for r in reponses:
        monthly[(r.get("date") or "")[:7]].append(r)
    trend = []
    for mois in sorted(m for m in monthly if m):
        rs = monthly[mois]
        g, tn = 0, 0
        for field in ["note_contenu", "note_pedagogie", "note_logistique"]:
            for r in rs:
                v = r.get(field)
                if v:
                    tn += 1
                    if v in ("bien", "tres-bien"):
                        g += 1
        trend.append({"mois": mois, "nb": len(rs), "taux_satisfaction": round(g / tn * 100) if tn else 0})
    stats["trend"] = trend

    stats["commentaires"] = [
        {"points_forts": r.get("points_forts"), "suggestions": r.get("suggestions"), "date": r.get("date")}
        for r in reponses if r.get("points_forts") or r.get("suggestions")
    ][:15]
    return stats

@router.get("/academie/statistiques", response_class=HTMLResponse)
async def academie_statistiques(request: Request, token: str = None, mois: str = None):
    reponses = academie_store.list_reponses(token)
    stats = _compute_stats(reponses)
    selected_q = academie_store.get_questionnaire(token) if token else None
    current_mois = mois or datetime.now().strftime("%Y-%m")
    plan = academie_store.get_plan_action(current_mois)
    return templates.TemplateResponse(
        "academie_statistiques.html",
        {
            "request": request, "stats": stats, "selected_q": selected_q,
            "current_mois": current_mois, "plan": plan,
        },
    )

@router.post("/academie/statistiques/plan-action")
async def academie_statistiques_plan_action(request: Request):
    form = await request.form()
    mois = form.get("mois") or datetime.now().strftime("%Y-%m")
    texte = (form.get("texte") or "").strip()
    academie_store.save_plan_action(mois, texte)
    return _toast_redirect(f"{ROOT_PATH}/academie/statistiques?mois={mois}", "Plan d'action enregistré")

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
