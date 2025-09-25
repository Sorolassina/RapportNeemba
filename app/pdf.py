import os
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .templates.default import with_defaults
import pdfkit

# Racine projet = dossier qui contient "app"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "app" / "templates"
STATIC_DIR = PROJECT_ROOT / "app" / "static"
STATIC_URI = STATIC_DIR.resolve().as_uri()  # ex: file:///C:/.../app/static

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

def _load_ctx(sid: str) -> dict:
    ctx_path = PROJECT_ROOT / "app" / "static" / "uploads" / sid / "context.json"
    if not ctx_path.exists():
        return {}
    with ctx_path.open(encoding="utf-8") as f:
        return json.load(f)

def _ensure_session_dir(sid: str) -> Path:
    session_dir = PROJECT_ROOT / "app" / "static" / "uploads" / sid
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def _root_path() -> str:
    """Root path FastAPI (ex: '/neembacoaching'), sinon ''."""
    rp = os.environ.get("ROOT_PATH", "").strip()
    if rp and not rp.startswith("/"):
        rp = "/" + rp
    return rp.rstrip("/")

def _patch_static_urls(html: str) -> str:
    """
    Remplace les URLs web '/static/...'
    et '/<root_path>/static/...' par des URI 'file:///.../app/static/...'
    pour que WeasyPrint / wkhtmltopdf résolvent correctement les assets.
    """
    rp = _root_path()
    # ordre : on remplace d'abord la version avec root_path pour ne pas doubler
    if rp:
        html = html.replace(f'{rp}/static/', f'{STATIC_URI}/')
    # puis la forme sans root_path
    html = html.replace('/static/', f'{STATIC_URI}/')
    return html

def render_pdf(template_name: str, sid: str) -> str:
    tpl = env.get_template(template_name)
    ctx = with_defaults(_load_ctx(sid))

    # Rendu HTML (templates peuvent contenir des url_for('static', ...))
    html_str = tpl.render(**ctx)

    # Assure le dossier
    session_dir = _ensure_session_dir(sid)
    out_pdf = session_dir / "rapport_nemba.pdf"
    tmp_html = session_dir / "report_tmp.html"

    # Patch des URLs /static → file://... pour les moteurs PDF
    html_for_pdf = _patch_static_urls(html_str)

    # Sauvegarde du HTML (utile debug)
    tmp_html.write_text(html_for_pdf, encoding="utf-8")

    # --- Tentative 1 : WeasyPrint (recommandé, surtout Linux/macOS) ---
    try:
        from weasyprint import HTML, CSS
        # base_url = PROJECT_ROOT pour que les chemins relatifs (s'il en reste) soient résolus
        HTML(string=html_for_pdf, base_url=str(PROJECT_ROOT)).write_pdf(
            str(out_pdf),
            stylesheets=[CSS(str(STATIC_DIR / "css" / "style.css"))],
        )
        return str(out_pdf)
    except Exception:
        # On ne log pas l'erreur ici volontairement : on tente wkhtmltopdf ensuite
        pass

    # --- Tentative 2 : wkhtmltopdf (Windows friendly) ---
    try:
        # Si wkhtmltopdf n'est pas dans le PATH, définir WKHTMLTOPDF_CMD dans l'env
        # ex (Windows) : C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe
        wk_cmd = os.environ.get("WKHTMLTOPDF_CMD")
        cfg = pdfkit.configuration(wkhtmltopdf=wk_cmd) if wk_cmd else None

        # Important: wkhtmltopdf attend un fichier ou une URL ; ici on a une string.
        # 'enable-local-file-access' doit être "" (valeur vide) et non None, pour être activé.
        options = {
            "enable-local-file-access": "",  # permet file:// et chemins locaux
            "page-size": "A4",
            "margin-top": "10mm",
            "margin-right": "10mm",
            "margin-bottom": "12mm",
            "margin-left": "10mm",
            "print-media-type": "",  # applique @media print
        }

        pdfkit.from_string(html_for_pdf, str(out_pdf), configuration=cfg, options=options)
        return str(out_pdf)
    except Exception as e:
        # Dernier recours : dump l'HTML pour inspection et lever une erreur claire
        (session_dir / "rapport_nemba.html").write_text(html_str, encoding="utf-8")
        raise RuntimeError(
            "Impossible de générer le PDF. Installez WeasyPrint ou wkhtmltopdf, "
            "et vérifiez les chemins des assets (CSS/Images)."
        ) from e
