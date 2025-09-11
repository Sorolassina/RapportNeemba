import os, json, shutil
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .templates.default import with_defaults
import pdfkit, os

env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

def _load_ctx(sid: str) -> dict:
    ctx_path = os.path.join("app", "static", "uploads", sid, "context.json")
    if not os.path.exists(ctx_path):
        return {}
    return json.load(open(ctx_path, encoding="utf-8"))

def render_pdf(template_name: str, sid: str) -> str:
    tpl = env.get_template(template_name)
    ctx = _load_ctx(sid)
    ctx = with_defaults(ctx)  # <-- important
    html_str = tpl.render(**ctx)

    # write tmp html
    session_dir = os.path.join("app", "static", "uploads", sid)
    out_pdf = os.path.join(session_dir, "rapport_nemba.pdf")
    tmp_html = os.path.join(session_dir, "report_tmp.html")
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_str)

    # Try WeasyPrint first
    try:
        from weasyprint import HTML, CSS
        HTML(string=html_str, base_url=".").write_pdf(out_pdf, stylesheets=[CSS("app/static/css/style.css")])
        return out_pdf
    except Exception:
        pass

    # Fallback to pdfkit (wkhtmltopdf)
    try:
        
        cmd = os.environ.get("WKHTMLTOPDF_CMD")
        cfg = pdfkit.configuration(wkhtmltopdf=cmd) if cmd else None
        pdfkit.from_string(html_str, out_pdf, configuration=cfg, options={
            "enable-local-file-access": None,
            "page-size": "A4",
            "margin-top": "10mm",
            "margin-right": "10mm",
            "margin-bottom": "12mm",
            "margin-left": "10mm",
            "print-media-type": None,
        })
        return out_pdf
    except Exception as e:
        # last resort: just dump HTML (for debug)
        with open(os.path.join(session_dir, "rapport_nemba.html"), "w", encoding="utf-8") as f:
            f.write(html_str)
        raise RuntimeError("Impossible de générer le PDF. Installez WeasyPrint ou wkhtmltopdf et réessayez.") from e
