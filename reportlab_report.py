# app/reportlab_report.py
import os, json, datetime, time, glob, uuid, threading
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import Color, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Conversion SVG -> PNG (si dispo) ---
try:
    import cairosvg
    HAS_CAIROSVG = True
except Exception:
    HAS_CAIROSVG = False

# ------------------ CONFIGS PIXEL-PERF ------------------
# Polices (place tes .ttf ici, ou garde Helvetica par défaut)
FONTS_DIR = "app/static/fonts"
FONT_TITLE_TTF = os.path.join(FONTS_DIR, "NembaDisplay.ttf")  # ex: Montserrat-ExtraBold.ttf
FONT_TEXT_TTF  = os.path.join(FONTS_DIR, "NembaSans.ttf")     # ex: Montserrat-Regular.ttf
FONT_TITLE = "NembaDisplay"
FONT_TEXT  = "NembaSans"

# Layout A4 paysage (toutes les pages utilisent ces métriques, style couverture)
LND = {
    "header_top_mm": 7,     # texte haut-centre
    "footer_bot_mm": 7,     # pied de page
    "logo_inset_mm": 12,    # marge latérale logos
    "logo_h_mm": 12,        # hauteur logos
    "brand_y_mm": 30,       # Y du 'Neemba Academy' (depuis le haut)
    "dots_y_mm": 36,        # Y des 3 pastilles (depuis le haut)
    "title_y_mm": 115,      # (utilisé pour la couverture)
    "subtitle_y_mm": 70,    # (utilisé pour la couverture)
    "spectrum_y_mm": 18,    # Y barre dégradée (depuis le bas)
    "spectrum_h_mm": 4,     # hauteur barre
    "spectrum_lr_mm": 12    # marges gauche/droite de la barre
}

# Couleurs UI
COLORS = {
    "panel_bg":  "#F7F8FA",
    "panel_bd":  "#E5E7EB",
    "muted":     "#6B7280",
    "title":     "#2b2f38",
    "chip_bg":   "#EEF2FF",
    "chip_txt":  "#1F2937",
}
DEV_GRID = False  # mettre True pour afficher une grille de calibration (mm)

# --------------------------------------------------------
ROOT = os.path.join("app", "static", "uploads")

# Verrous pour éviter les conflits entre utilisateurs
_session_locks = {}
_lock_manager = threading.Lock()

def _generate_secure_session_id():
    """Génère un ID de session unique et sécurisé."""
    return str(uuid.uuid4())

def _get_session_lock(session_id):
    """Récupère ou crée un verrou pour une session donnée."""
    with _lock_manager:
        if session_id not in _session_locks:
            _session_locks[session_id] = threading.Lock()
        return _session_locks[session_id]

def _cleanup_session_lock(session_id):
    """Nettoie le verrou d'une session après utilisation."""
    with _lock_manager:
        if session_id in _session_locks:
            del _session_locks[session_id]

def _cleanup_old_files():
    """
    Nettoie automatiquement les fichiers temporaires anciens dans le dossier uploads.
    Supprime les fichiers de plus de 24 heures pour éviter l'accumulation.
    PROTECTION : Ne supprime que les fichiers de sa propre session pour éviter les conflits.
    """
    try:
        upload_dir = ROOT
        if not os.path.exists(upload_dir):
            return
        
        current_time = time.time()
        max_age_hours = 24  # Supprimer les fichiers de plus de 24h
        max_age_seconds = max_age_hours * 3600
        
        deleted_count = 0
        deleted_size = 0
        
        # Parcourir tous les sous-dossiers de sessions
        for session_dir in os.listdir(upload_dir):
            session_path = os.path.join(upload_dir, session_dir)
            if not os.path.isdir(session_path):
                continue
                
            # Vérifier que le dossier de session est assez ancien (sécurité)
            try:
                session_age = current_time - os.path.getmtime(session_path)
                if session_age < max_age_seconds:
                    continue  # Ne pas toucher aux sessions récentes
            except:
                continue
                
            # Parcourir tous les fichiers dans le dossier de session
            for filename in os.listdir(session_path):
                file_path = os.path.join(session_path, filename)
                if not os.path.isfile(file_path):
                    continue
                
                # Vérifier l'âge du fichier
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        deleted_size += file_size
                        print(f"DEBUG - Fichier supprimé: {file_path}")
                except Exception as e:
                    print(f"DEBUG - Erreur suppression {file_path}: {e}")
        
        # Supprimer les dossiers de session vides (avec vérification d'âge)
        for session_dir in os.listdir(upload_dir):
            session_path = os.path.join(upload_dir, session_dir)
            if os.path.isdir(session_path) and not os.listdir(session_path):
                try:
                    session_age = current_time - os.path.getmtime(session_path)
                    if session_age > max_age_seconds:  # Seulement les anciens dossiers vides
                        os.rmdir(session_path)
                        print(f"DEBUG - Dossier vide supprimé: {session_path}")
                except Exception as e:
                    print(f"DEBUG - Erreur suppression dossier {session_path}: {e}")
        
        if deleted_count > 0:
            print(f"DEBUG - Nettoyage terminé: {deleted_count} fichiers supprimés ({deleted_size/1024/1024:.1f} MB)")
            
    except Exception as e:
        print(f"DEBUG - Erreur lors du nettoyage: {e}")

def _pt(mm_val: float) -> float:
    return mm_val * mm

def _register_fonts():
    """Enregistre les polices TTF si présentes, sinon fallback Helvetica."""
    global FONT_TITLE, FONT_TEXT
    try:
        if os.path.exists(FONT_TITLE_TTF):
            pdfmetrics.registerFont(TTFont(FONT_TITLE, FONT_TITLE_TTF))
        else:
            raise FileNotFoundError
    except Exception:
        FONT_TITLE = "Helvetica-Bold"
    try:
        if os.path.exists(FONT_TEXT_TTF):
            pdfmetrics.registerFont(TTFont(FONT_TEXT, FONT_TEXT_TTF))
        else:
            raise FileNotFoundError
    except Exception:
        FONT_TEXT = "Helvetica"

def _ctx_path(sid: str) -> str:
    return os.path.join(ROOT, sid, "context.json")

def _load_ctx(sid: str) -> dict:
    p = _ctx_path(sid)
    if not os.path.exists(p): 
        print(f"DEBUG - Fichier contexte non trouvé: {p}")
        return {}
    
    try:
        with open(p, encoding="utf-8") as f:
            ctx = json.load(f)
        print(f"DEBUG - Contexte chargé depuis: {p}")
        print(f"DEBUG - Contenu du contexte: {ctx}")
        return ctx
    except Exception as e:
        print(f"DEBUG - Erreur chargement contexte: {e}")
        return {}

def _web_to_disk(p: str | None) -> str | None:
    if not p: return None
    p = p.lstrip("/")
    return os.path.join("app", p) if p.startswith("static/") else p

def _resolve_image_for_reportlab(src_path: str | None, session_dir: str) -> str:
    """
    - Accepte PNG/JPG/GIF directement.
    - Si SVG: convertit en PNG (si cairosvg dispo), sinon fallback vers un logo PNG.
    - Retourne toujours un chemin lisible par reportlab.
    """
    fallback = os.path.join("app", "static", "img", "branding", "nemba_logo.jpg")
    p = _web_to_disk(src_path) if src_path else None
    if not p or not os.path.exists(p):
        return fallback

    ext = os.path.splitext(p)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"):
        return p

    if ext == ".svg":
        if HAS_CAIROSVG:
            os.makedirs(session_dir, exist_ok=True)
            out_png = os.path.join(session_dir, f"tmp_{os.path.basename(p)}.png")
            try:
                cairosvg.svg2png(url=p, write_to=out_png)
                return out_png
            except Exception:
                pass  # fallback ci-dessous
        return fallback

    return fallback

def _draw_text(c: canvas.Canvas, x, y, txt, size=12, color="#000", font=None, center=False):
    c.setFillColor(HexColor(color))
    c.setFont(font or FONT_TEXT, size)
    (c.drawCentredString if center else c.drawString)(x, y, txt or "")

def _clip_rect(c, x, y_top, w, h):
    """
    Limite le dessin à un rectangle (x, y_top, w, h).
    y_top = coordonnée du bord SUPÉRIEUR.
    """
    p = c.beginPath()
    p.rect(x, y_top - h, w, h)  # ReportLab utilise (x, y_bas)
    c.clipPath(p, stroke=0, fill=0)

def _wrap_lines(c, text, width, size, font=None):
    font = font or FONT_TEXT
    words = (text or "").split()
    lines, line = [], ""
    
    for w in words:
        test = (line + " " + w).strip()
        if c.stringWidth(test, font, size) <= width:
            line = test
        else:
            if line: 
                lines.append(line)
                line = ""
            
            # Vérifier si le mot seul est trop long
            if c.stringWidth(w, font, size) > width:
                # Couper le mot caractère par caractère
                current_word = ""
                for char in w:
                    test_char = current_word + char
                    if c.stringWidth(test_char, font, size) <= width:
                        current_word = test_char
                    else:
                        if current_word:
                            lines.append(current_word)
                        current_word = char
                line = current_word
            else:
                line = w
    
    if line: lines.append(line)
    return lines

def _draw_three_dots(c: canvas.Canvas, center_x, y):
    cols = ["#ff5a36", "#ffb703", "#13c04a"]
    r = _pt(2.2); gap = _pt(6)
    x0 = center_x - (r*2 + gap)
    for i, col in enumerate(cols):
        c.setFillColor(HexColor(col))
        c.circle(x0 + i*(2*r + gap), y, r, fill=1, stroke=0)

def _lerp(a, b, t): return a + (b-a)*t

def _draw_spectrum_bar(c: canvas.Canvas, x, y, w, h):
    """Dégradé avec bouts arrondis (vert → jaune → orange → rouge)."""
    stops = [(0.00, (0x13,0xC0,0x4A)),
             (0.35, (0xFF,0xD4,0x00)),
             (0.60, (0xFF,0x9F,0x1A)),
             (1.00, (0xE0,0x16,0x16))]
    rx = x + h/2.0
    rw = max(1.0, w - h)
    steps = int(rw/1.5)
    for i in range(steps):
        t = i/(steps-1)
        for s in range(len(stops)-1):
            t0, c0 = stops[s]; t1, c1 = stops[s+1]
            if t0 <= t <= t1:
                u = (t - t0)/(t1 - t0) if t1 > t0 else 0
                r = int(_lerp(c0[0], c1[0], u))
                g = int(_lerp(c0[1], c1[1], u))
                b = int(_lerp(c0[2], c1[2], u))
                c.setFillColor(Color(r/255.0, g/255.0, b/255.0))
                break
        xi = rx + (i/steps)*rw
        c.rect(xi, y, rw/steps + 1, h, stroke=0, fill=1)
    # extrémités arrondies
    start_rgb = stops[0][1]; end_rgb = stops[-1][1]
    c.setFillColor(Color(start_rgb[0]/255.0, start_rgb[1]/255.0, start_rgb[2]/255.0))
    c.circle(x + h/2.0, y + h/2.0, h/2.0, stroke=0, fill=1)
    c.setFillColor(Color(end_rgb[0]/255.0, end_rgb[1]/255.0, end_rgb[2]/255.0))
    c.circle(x + w - h/2.0, y + h/2.0, h/2.0, stroke=0, fill=1)

def _draw_grid_mm(c: canvas.Canvas, step_mm=5):
    """Grille de calibration (5 mm) – DEV_GRID=True pour activer."""
    W, H = c._pagesize
    c.setLineWidth(0.1)
    for x in range(0, int(W/mm)+1, step_mm):
        px = _pt(x)
        c.setStrokeColor(HexColor("#e5e7eb") if (x//step_mm)%2 else HexColor("#cfd4dc"))
        c.line(px, 0, px, H)
    for y in range(0, int(H/mm)+1, step_mm):
        py = _pt(y)
        c.setStrokeColor(HexColor("#e5e7eb") if (y//step_mm)%2 else HexColor("#cfd4dc"))
        c.line(0, py, W, py)

def _draw_header_footer_text(c: canvas.Canvas, page_num=None, text_top="Rapport de formation Neemba",
                             text_left="Confidentiel", text_mid=None, top_mm=7, bot_mm=7):
    """Texte d’en-tête/pied (au-dessus/au-dessous du style graphique)."""
    W, H = c._pagesize
    _draw_text(c, W/2.0, H - _pt(top_mm), text_top, size=9, color="#2b2f38", font=FONT_TEXT, center=True)
    _draw_text(c, _pt(8), _pt(bot_mm), text_left, size=9, color="#555", font=FONT_TEXT)
    if text_mid:
        _draw_text(c, W/2.0, _pt(bot_mm), text_mid, size=9, color="#555", font=FONT_TEXT, center=True)
    if page_num is not None:
        _draw_text(c, W - _pt(20), _pt(bot_mm), f"Page {page_num}", size=9, color="#555", font=FONT_TEXT)

def _brand_header(c: canvas.Canvas, ctx: dict, metrics: dict, brand_size=22,label="Neemba Academy"):
    """Dessine logos gauche/droite + 'Neemba Academy' + 3 pastilles (paysage)."""
    W, H = c._pagesize
    left_src  = ctx.get("cover", {}).get("logo_left_path") or "/static/img/branding/nemba_logo.jpg"
    right_src = ctx.get("cover", {}).get("logo_right_path") or ctx.get("client", {}).get("logo_path") or "/static/img/branding/nemba_logo.jpg"
    session_dir = os.path.join(ROOT, ctx.get("_sid","_"))
    left_logo  = _resolve_image_for_reportlab(left_src,  session_dir)
    right_logo = _resolve_image_for_reportlab(right_src, session_dir)

    # logos
    y_top = H - _pt(metrics["brand_y_mm"] - (metrics["logo_h_mm"]/2.0))
    if left_logo and os.path.exists(left_logo):
        c.drawImage(left_logo, _pt(metrics["logo_inset_mm"]), y_top-_pt(metrics["logo_h_mm"]),
                    width=_pt(26), height=_pt(metrics["logo_h_mm"]),
                    preserveAspectRatio=True, mask='auto')
    if right_logo and os.path.exists(right_logo):
        c.drawImage(right_logo, W - _pt(metrics["logo_inset_mm"] + 26), y_top-_pt(metrics["logo_h_mm"]),
                    width=_pt(26), height=_pt(metrics["logo_h_mm"]),
                    preserveAspectRatio=True, mask='auto')

    # marque + 3 pastilles
    _draw_text(c, W/2.0, H - _pt(metrics["brand_y_mm"]), label,
               size=brand_size, color="#2b2f38", font=FONT_TITLE, center=True)
    _draw_three_dots(c, W/2.0, H - _pt(metrics["dots_y_mm"]))

def _spectrum_footer(c: canvas.Canvas, metrics: dict):
    """Barre dégradée arc-en-ciel au-dessus du pied."""
    W, _ = c._pagesize
    sx = _pt(metrics["spectrum_lr_mm"])
    sw = W - _pt(metrics["spectrum_lr_mm"]*2)
    sy = _pt(metrics["spectrum_y_mm"])
    sh = _pt(metrics["spectrum_h_mm"])
    _draw_spectrum_bar(c, sx, sy, sw, sh)

def _neumo_panel(c, x, y, w, h, title=None):
    """Carte style neumorphism (ombre douce bas-droite, lumière haut-gauche). x,y = coin SUPÉRIEUR GAUCHE."""
    off = _pt(1.2)
    rad = _pt(3)
    # ombre (derrière)
    c.setFillColor(HexColor("#d1d5db"))
    c.roundRect(x+off, y-h-off, w, h, rad, stroke=0, fill=1)
    # lumière (derrière)
    c.setFillColor(HexColor("#ffffff"))
    c.roundRect(x-off, y-h+off, w, h, rad, stroke=0, fill=1)
    # carte
    c.setFillColor(HexColor("#F7F8FA"))
    c.setStrokeColor(HexColor("#e5e7eb"))
    c.setLineWidth(0.6)
    c.roundRect(x, y-h, w, h, rad, stroke=1, fill=1)
    if title:
        _draw_text(c, x + _pt(6), y - _pt(8), title.upper(), size=12, color="#2b2f38", font=FONT_TITLE)

def _draw_kv(c, x, y, w, label, value, lab_w_mm=28, gap_mm=2, line_h_mm=7, size=11):
    """Ligne 'Label : Valeur' avec wrap automatique. Retourne le nouveau y."""
    lab = (label or "").strip()
    # si label vide → pas de largeur réservée ni d'écart
    lab_w = _pt(lab_w_mm if lab else 0)
    gap   = _pt(gap_mm   if lab else 0)
    line_h = _pt(line_h_mm)

    # DEBUG: Afficher les largeurs réelles
    if lab:
        actual_label_width = c.stringWidth(lab, FONT_TEXT, size)
        print(f"Label '{lab}': réservé={lab_w:.1f}pt, réel={actual_label_width:.1f}pt")
        if actual_label_width > lab_w:
            print(f"  ⚠️  Label déborde de {actual_label_width - lab_w:.1f}pt !")

    if lab:
        _draw_text(c, x, y, lab, size=size, color="#6B7280", font=FONT_TEXT)

    max_w = w - lab_w - gap
    text = (value or "").strip()
    lines = _wrap_lines(c, text, max_w, size, font=FONT_TEXT)
    vx = x + lab_w + gap
    vy = y
    for ln in (lines or [""]):
        _draw_text(c, vx, vy, ln, size=size, color="#000", font=FONT_TEXT)
        vy -= line_h
    used = max(1, len(lines))
    return y - line_h*used

def _draw_chip(c, x, y, text, padx_mm=3.5, pady_mm=1.8):
    """Étiquette arrondie (période, participants)."""
    from reportlab.lib.colors import HexColor
    padx = _pt(padx_mm); pady = _pt(pady_mm)
    txt_w = c.stringWidth(text, FONT_TEXT, 10)
    w = txt_w + 2*padx; h = _pt(6)
    c.setFillColor(HexColor("#EEF2FF"))
    c.setStrokeColor(HexColor("#E5E7EB"))
    c.setLineWidth(0.6)
    try:
        c.roundRect(x, y-h, w, h, _pt(2), stroke=1, fill=1)
    except Exception:
        c.rect(x, y-h, w, h, stroke=1, fill=1)
    _draw_text(c, x+padx, y - h + _pt(1.5), text, size=10, color="#1F2937", font=FONT_TEXT)


def _draw_image_contain(c, session_id, src_path, x, y_top, w, h, pad_mm=2):
    """
    Dessine une image à l’intérieur d’un cadre (w x h) en conservant le ratio,
    centrée, avec un padding. (x, y_top) = coin SUPÉRIEUR GAUCHE du cadre.
    """
    p = _resolve_image_for_reportlab(src_path, os.path.join(ROOT, session_id))
    if not (p and os.path.exists(p)):
        return
    pad = _pt(pad_mm)
    box_w = max(1, w - 2*pad)
    box_h = max(1, h - 2*pad)

    from PIL import Image
    try:
        img = Image.open(p)
        iw, ih = img.size
        ratio = min(box_w/iw, box_h/ih)
        tw, th = iw*ratio, ih*ratio
        # coordonnées ReportLab (anchor='sw')
        x_draw = x + pad + (box_w - tw)/2.0
        y_draw = (y_top - h) + pad + (box_h - th)/2.0
        c.drawImage(p, x_draw, y_draw, width=tw, height=th, preserveAspectRatio=True, mask='auto', anchor='sw')
    except Exception:
        # fallback simple: on tente un drawImage stretch
        c.drawImage(p, x + pad, (y_top - h) + pad, width=box_w, height=box_h, preserveAspectRatio=True, mask='auto', anchor='sw')

def _neumo_subpanel(c, x, y, w, h, title=None):
    """Sous-panel doux (neumorphism light)."""
    off = _pt(0.8); rad = _pt(2.5)
    c.setFillColor(HexColor("#dfe3ea"))
    c.roundRect(x+off, y-h-off, w, h, rad, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.roundRect(x-off, y-h+off, w, h, rad, stroke=0, fill=1)
    c.setFillColor(HexColor("#FAFBFC"))
    c.setStrokeColor(HexColor("#e6e9ef"))
    c.setLineWidth(0.5)
    c.roundRect(x, y-h, w, h, rad, stroke=1, fill=1)
    if title:
        _draw_text(c, x + _pt(4), y - _pt(6), title, size=11, color="#374151", font=FONT_TEXT)

class Box:
    """Conteneur 'parent' façon HTML : gère cadre, padding et écriture verticale."""
    def __init__(self, c, x, y, w, h, padding_mm=6):
        self.c = c
        self.x, self.y, self.w, self.h = x, y, w, h
        self.pad = _pt(padding_mm)
        # curseur texte (sous le titre de carte)
        self.cursor_y = y - _pt(18)

    def neumo(self, title=None):
        _neumo_panel(self.c, self.x, self.y, self.w, self.h, title=title)

    def kv(self, label, value, lab_w_mm=28, size=11):
        """Ligne 'Label : Valeur' dans la box, avec wrap."""
        self.cursor_y = _draw_kv(
            self.c, self.x + self.pad, self.cursor_y,
            self.w - 2*self.pad, label, value,
            lab_w_mm=lab_w_mm, size=size
        )

    """def chips(self, items, y_from_bottom_mm=16):
        Affiche une rangée de chips en bas de la box.
        y = self.y - self.h + _pt(y_from_bottom_mm)
        x = self.x + self.pad
        for t in items:
            if not t: continue
            _draw_chip(self.c, x, y, t)
            x += self.c.stringWidth(t, FONT_TEXT, 10) + _pt(3.5*2 + 10)"""

def _draw_value(c, x, y, w, text, size=12, color="#111827", font=FONT_TEXT, line_h_mm=7, gap_mm=1.5):
    """Dessine un texte 'value' avec wrap dans une largeur w, et renvoie le nouveau y."""
    lines = _wrap_lines(c, text or "", w, size, font=font)
    for ln in (lines or [""]):
        _draw_text(c, x, y, ln, size=size, color=color, font=font)
        y -= _pt(line_h_mm)
    return y - _pt(gap_mm)
# ========================= CLASSE PRINCIPALE =========================
class NembaReportLab:
    """
    Générateur PDF NEMBA (ReportLab), imitation précise :
    - TOUTES les pages en A4 paysage au design de la couverture :
      logos extrémités, 'Neemba Academy' + pastilles, barre dégradée en bas,
      en-tête/pied uniformes.
    """
    def __init__(self, sid: str, out_path: str):
        _register_fonts()
        self.sid = sid
        self.out_path = out_path
        self.session_lock = _get_session_lock(sid)  # Verrou pour cette session
        self.ctx = _load_ctx(sid) or {}
        self.ctx["_sid"] = sid
        self.c = canvas.Canvas(out_path, pagesize=landscape(A4))
        self.W, self.H = self.c._pagesize
        self.today = datetime.date.today().strftime("%d/%m/%Y")

    # ------------- DÉMARRER UNE PAGE PAYSAGE -------------
    def _start_landscape(self, page_num, brand_size=22, brand_label="Neemba Academy"):
        self.c.setPageSize(landscape(A4))
        self.W, self.H = self.c._pagesize
        if DEV_GRID: _draw_grid_mm(self.c)
        _draw_header_footer_text(self.c, page_num=page_num, text_mid=self.today,
                                top_mm=LND["header_top_mm"], bot_mm=LND["footer_bot_mm"])
        _brand_header(self.c, self.ctx, LND, brand_size=brand_size, label=brand_label)
        _spectrum_footer(self.c, LND)

    # ------------- COUVERTURE (paysage) -------------
    def cover(self):
        """
        Génère la page de couverture du rapport.
        Affiche le titre principal, sous-titre, logos et éléments de branding.
        Style : Titre très grand (72pt), sous-titre (36pt), logos latéraux.
        """
        # Page 1 : même style, mais avec Titre/Sous-titre centraux très grands
        self._start_landscape(page_num=1, brand_size=30)
        machine = self.ctx.get("machine", {})
        c, W, H = self.c, self.W, self.H
        title = self.ctx.get("cover",{}).get("title") or "Rapport  de  Formation"
        subtitle = self.ctx.get("cover",{}).get("subtitle") or machine.get("model", "")or machine.get("name", "")
        _draw_text(c, W/2.0, H - _pt(LND["title_y_mm"]), title,
                   size=72, color="#3b424c", font=FONT_TITLE, center=True)
        _draw_text(c, W/2.0, H - _pt(LND["subtitle_y_mm"]), subtitle,
                   size=36, color="#000", font=FONT_TITLE, center=True)
        c.showPage()

    # ------------- PAGES DE CONTENU (paysage) -------------
    def presentation(self, n):
        """
        Génère la page de présentation avec informations client, machine et formateur.
        
        STRUCTURE :
        - Grand box Client (haut) : 4 sous-boxes
          * Photo machine (18%)
          * Infos machine : Nom, Modèle, Type, Série (32%)
          * Logo client (18%)
          * Infos client : Nom, Téléphone, Email, Pays, Adresse (32%)
        - Séparateur arc-en-ciel
        - Grand box Formateur (bas) : 2 sous-boxes
          * Photo formateur (35%)
          * Infos formateur : Nom, Téléphone, Email, Spécialité, Lieu, Participants, Période (65%)
        """
        # Bandeau “Présentation” + style global (logos, pastilles, barre)
        self._start_landscape(n, brand_label="Présentation")
        c, W, H = self.c, self.W, self.H

        margin = _pt(12)
        top_y  = H - _pt(50)

        # ---- PARAMÈTRES CALÉS POUR TENIR DANS LA PAGE ----
        CLIENT_H_MM      = 52   # hauteur du grand box Client
        SEP_GAP_MM       = 8    # espace entre Client et séparateur arc-en-ciel
        AFTER_SEP_GAP_MM = 8    # espace entre séparateur et box Formateur
        TRAINER_H_MM     = 60   # hauteur du grand box Formateur augmentée

        client_h  = _pt(CLIENT_H_MM)
        trainer_h = _pt(TRAINER_H_MM)

        # ================== GRAND BOX "CLIENT" (HAUT) ==================
        _neumo_panel(c, margin, top_y, W - 2*margin, client_h, title="")

        # CLIP pour empêcher tout débordement hors du box Client
        c.saveState()
        _clip_rect(c, margin, top_y, W - 2*margin, client_h)

        # zone intérieure Client
        inner_x = margin + _pt(8)
        inner_w = (W - 2*margin) - _pt(16)
        inner_y = top_y
        inner_h = client_h - _pt(8)
        grid_gap = _pt(8)

        # 4 mini-box horizontales
        # 4 mini-box horizontales avec proportions optimisées
        avail = inner_w - 3*grid_gap
        # 1)photoMach  2)infosMach  3)photoClient 4)infosClient
        r1, r2, r3, r4 = 0.18, 0.32, 0.18, 0.32  # Rééquilibré pour plus d'espace aux infos
        w1, w2, w3, w4 = r1*avail, r2*avail, r3*avail, r4*avail

        x1 = inner_x
        x2 = x1 + w1 + grid_gap
        x3 = x2 + w2 + grid_gap
        x4 = x3 + w3 + grid_gap

        col_h = inner_h - _pt(5)

        client  = self.ctx.get("client", {})
        trainer = self.ctx.get("trainer", {})
        machine = self.ctx.get("machine", {})

        # ---- 1) PHOTO MACHINE ----
        inner_yPM=inner_y- _pt(8) 
        # inner_yPM : Pour remonter la photo machine : réduis ces offsets (ex. 14 → 10).
        # Pour descendre : augmente (ex. 14 → 18).

        _neumo_subpanel(c, x1, inner_yPM, w1, col_h, title="")
        _draw_image_contain(c, self.sid, machine.get("photo_path"),
                            x1 , inner_yPM- _pt(1) ,
                            w1 , col_h , pad_mm=2)
        # ---- 2) INFOS MACHINE ----
        _neumo_subpanel(c, x2, inner_y - _pt(8), w2, col_h, title="")

        kv_x = x2 + _pt(8)
        kv_y = inner_y - _pt(16)  # Position de départ plus claire
        kv_w = w2 - _pt(16)

        # Informations machine avec labels appropriés - TEST VISUEL
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Nom :", machine.get("name", ""), lab_w_mm=18, gap_mm=1)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Modèle :", machine.get("model", ""), lab_w_mm=18, gap_mm=1)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Type :", machine.get("type", ""), lab_w_mm=18, gap_mm=1)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Série :", machine.get("serial", ""), lab_w_mm=18, gap_mm=1)

        # ---- 3) PHOTO CLIENT ----
        # inner_y
        inner_yPC=inner_y- _pt(8)
        # inner_yPC : Pour remonter la photo client : réduis ces offsets (ex. 14 → 10).
        # Pour descendre : augmente (ex. 14 → 18).
        _neumo_subpanel(c, x3, inner_yPC, w3, col_h, title="")
        photo_client_src = client.get("photo_path") or client.get("logo_path")
        _draw_image_contain(c, self.sid, photo_client_src,
                            x3 , inner_yPC- _pt(1) ,
                            w3 , col_h , pad_mm=2)

        # ---- 4) INFOS CLIENT ----
        _neumo_subpanel(c, x4, inner_y - _pt(8), w4, col_h, title="")
        kv_x = x4 + _pt(6)  # Padding réduit pour plus d'espace
        kv_y = inner_y - _pt(16)  # Position de départ ajustée
        kv_w = w4 - _pt(12)  # Largeur ajustée
        
        # Informations client avec espacement optimisé
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Nom :", client.get("name", ""), lab_w_mm=18, gap_mm=1, line_h_mm=6)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Tél. :", client.get("phone", ""), lab_w_mm=18, gap_mm=1,line_h_mm=6)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Email :", client.get("email", ""), lab_w_mm=18, gap_mm=1,line_h_mm=6)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Pays :", client.get("country", ""), lab_w_mm=18, gap_mm=1,line_h_mm=6)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Adresse :", client.get("address", ""), lab_w_mm=18, gap_mm=1,line_h_mm=6)

        c.restoreState()  # fin du clip Client

        # ================== SÉPARATEUR ARC-EN-CIEL ==================
        sep_y = top_y - client_h - _pt(SEP_GAP_MM)
        _draw_spectrum_bar(c, margin, sep_y, W - 2*margin, _pt(4))

        # ================== GRAND BOX "FORMATEUR" (BAS) ==================
        bot_y = sep_y - _pt(AFTER_SEP_GAP_MM)
        _neumo_panel(c, margin, bot_y, W - 2*margin, trainer_h, title="")

        # CLIP pour empêcher tout débordement hors du box Formateur
        c.saveState()
        _clip_rect(c, margin, bot_y, W - 2*margin, trainer_h)

        inner_x = margin + _pt(6)  # Padding réduit pour plus d'espace
        inner_w = (W - 2*margin) - _pt(12)  # Plus d'espace utilisable
        inner_y = bot_y
        inner_h = trainer_h - _pt(12)  # Hauteur optimisée
        gap = _pt(10)  # Espacement légèrement augmenté

        # 2 sous-boxes horizontales avec proportions optimisées
        photo_ratio = 0.35  # 35% pour la photo
        info_ratio = 0.65   # 65% pour les informations
        col_w_photo = (inner_w - gap) * photo_ratio
        col_w_info = (inner_w - gap) * info_ratio
        col_h = inner_h - _pt(8)  # Hauteur maximisée

        trainer = self.ctx.get("trainer", {})

        # 1) PHOTO FORMATEUR (gauche) - Box plus grand et centré
        left_x = inner_x
        _neumo_subpanel(c, left_x, inner_y - _pt(10), col_w_photo, col_h, title="")
        _draw_image_contain(
            c, self.sid, trainer.get("photo_path"),
            left_x + _pt(2), inner_y - _pt(12),  # Position centrée verticalement
            col_w_photo - _pt(4), col_h - _pt(4), pad_mm=1  # Image plus grande et centrée
        )

        # 2) INFORMATIONS FORMATEUR (droite) - Box plus grand avec plus d'informations
        right_x = inner_x + col_w_photo + gap
        _neumo_subpanel(c, right_x, inner_y - _pt(10), col_w_info, col_h, title="")

        kv_x = right_x + _pt(6)  # Padding optimisé
        kv_y = inner_y - _pt(16)  # Position descendue pour éviter d'être trop haut
        kv_w = col_w_info - _pt(12)  # Largeur maximisée

        # Informations formateur essentielles avec espacement optimisé
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Nom & Prénoms :", trainer.get("fullname", ""), line_h_mm=5,gap_mm=3)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Contacts :", trainer.get("contacts", ""), line_h_mm=5,gap_mm=3)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Lieu :", trainer.get("place", ""), line_h_mm=5,gap_mm=3)
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Participants :", str(trainer.get("participants_count", "")), line_h_mm=5,gap_mm=3)
        period_txt = f"Du : {trainer.get('start_date', '')} au : {trainer.get('end_date', '')}".strip()
        kv_y = _draw_kv(c, kv_x, kv_y, kv_w, "Période :", period_txt, line_h_mm=5,gap_mm=3)

        c.restoreState()  # fin du clip Formateur

        c.showPage()


    def list_page(self, title, items, n, numbered=False):
        """
        Génère une page de liste générique (utilisée pour Sommaire et Objectifs).
        
        PARAMÈTRES :
        - title : Titre de la page (ex: "Sommaire", "Objectifs")
        - items : Liste des éléments à afficher
        - n : Numéro de page
        - numbered : True pour numérotation (1. 2. 3.), False pour puces (• • •)
        
        FONCTIONNALITÉS :
        - Pagination automatique si le contenu dépasse la page
        - Retour à la ligne automatique pour les textes longs
        - Style uniforme avec tous les autres éléments
        """
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # ========== TITRE DE LA PAGE ==========
        # Position X: _pt(20) = 20mm depuis la gauche
        # Position Y: H - _pt(52) = 52mm depuis le haut de la page
        # H = hauteur totale de la page paysage A4
        
        # Titre en gras et taille 30 pour Sommaire et Objectifs
        if title in ["Sommaire", "Objectifs"]:
            _draw_text(c, _pt(20), H - _pt(52), title, size=30, font=FONT_TITLE)  # Titre principal en gras
        else:
            # Titre normal pour les autres pages
            _draw_text(c, _pt(20), H - _pt(42), title, size=20, font=FONT_TEXT)  # Titre standard
        
        # ========== IMAGES DÉCORATIVES ==========
        # Images affichées à droite du titre pour illustrer la section
        
        # Image pour la page Sommaire
        if title == "Sommaire":
            img_path = os.path.join("app", "static", "img","report", "IMG-Som.png")
            if os.path.exists(img_path):
                # Positionnement de l'image IMG-Som
                img_x = W - _pt(110)  # Position X: 80mm depuis la droite (W = largeur totale)
                img_y = H - _pt(20)  # Position Y: 50mm depuis le haut
                img_w = _pt(200)      # Largeur: 60mm
                img_h = _pt(200)      # Hauteur: 40mm
                
                try:
                    # Dessin de l'image avec préservation du ratio
                    c.drawImage(img_path, img_x, img_y - img_h, 
                              width=img_w, height=img_h, 
                              preserveAspectRatio=True, mask='auto', anchor='sw')
                except Exception as e:
                    print(f"Erreur lors du chargement de l'image IMG-Som: {e}")
        
        # Image pour la page Objectifs
        if title == "Objectifs":
            img_path = os.path.join("app", "static", "img","report", "IMG-Objectif.png")
            if os.path.exists(img_path):
                # Positionnement de l'image IMG-Objectif
                img_x = W - _pt(120)  # Position X: 120mm depuis la droite
                img_y = H - _pt(50)  # Position Y: 50mm depuis le haut
                img_w = _pt(120)      # Largeur: 120mm
                img_h = _pt(120)      # Hauteur: 120mm
                
                try:
                    # Dessin de l'image avec préservation du ratio
                    c.drawImage(img_path, img_x, img_y - img_h, 
                              width=img_w, height=img_h, 
                              preserveAspectRatio=True, mask='auto', anchor='sw')
                    
                    # ========== TEXTE CENTRÉ SUR L'IMAGE ==========
                    # Calcul du centre de l'image pour positionner le texte
                    center_x = img_x + (img_w / 2)  # Centre horizontal de l'image
                    center_y = img_y - (img_h / 2)   # Centre vertical de l'image
                    
                    # Texte à afficher au centre de l'image
                    machine = self.ctx.get("machine", {})
                    text_to_display = machine.get("model", "") or machine.get("name", "")
                    
                    # Dessin du texte centré sur l'image
                    _draw_text(c, center_x, center_y, text_to_display, 
                             size=16, color="#0a0a0a", font=FONT_TITLE, center=True)
                    
                except Exception as e:
                    print(f"Erreur lors du chargement de l'image IMG-Objectif: {e}")
        
        # ========== CONTENU DE LA LISTE ==========
        # Position de départ du contenu : 80mm depuis le haut (descendu pour éviter confusion avec titre)
        y = H - _pt(70)  # Y initial pour la première ligne de contenu
        
        # Calcul de la largeur disponible pour le texte (s'arrête avant l'image)
        # L'image commence à W - _pt(110), donc le texte doit s'arrêter avant
        text_width = W - _pt(130)  # Largeur disponible pour le texte (130mm de marge droite)
        
        # Debug : afficher les données reçues
        print(f"DEBUG - Page: {title}, Items: {items}")
        print(f"DEBUG - Type items: {type(items)}, Length: {len(items) if items else 0}")
        
        # Vérification si des données existent
        if not items or len(items) == 0:
            # Affichage d'un message informatif si aucune donnée du wizard
            if title == "Sommaire":
                info_text = "Les sections du rapport seront générées automatiquement"
            elif title == "Objectifs":
                info_text = "Veuillez renseigner les objectifs dans le wizard"
            else:
                info_text = f"Aucun élément disponible pour {title.lower()}"
            
            c.setFont(FONT_TEXT, 20)
            c.drawString(_pt(20), y, info_text)
            y -= _pt(10)
        
        # Parcours de tous les éléments de la liste
        for i, it in enumerate(items or []):
            # Formatage de la ligne selon le type (numéroté ou à puces)
            line = (f"{i+1}. " if numbered else "• ") + str(it)
            
            # Gestion du retour à la ligne automatique pour les textes longs
            for ln in _wrap_lines(c, line, text_width, 20, font=FONT_TEXT):
                # Dessin de chaque ligne de texte
                c.setFont(FONT_TEXT, 20); c.drawString(_pt(20), y, ln); y -= _pt(10)
                
                # Vérification si on dépasse le bas de page
                if y < _pt(28):  # Si moins de 28mm depuis le bas
                    # Nouvelle page automatique
                    c.showPage(); n += 1; self._start_landscape(n); y = self.H - _pt(70)
        
        # Fin de page
        c.showPage()

    def planning(self, n):
        """
        Génère la page de planning avec diagramme de Gantt hebdomadaire.
        
        STRUCTURE :
        - Titre : "1. Contenu & Planning" (gras, taille 30)
        - Image décorative IMG-Planning.png
        - Diagramme de Gantt avec colonnes : TASKS | LUNDI | MARDI | MERCREDI | JEUDI | VENDREDI
        - Barres colorées pour représenter la durée des tâches
        - Pagination automatique si nécessaire
        
        DONNÉES : self.ctx.get("planning", [])
        """
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # ========== TITRE ==========
        # Titre en gras et taille 30 (même format que Sommaire/Objectifs)
        _draw_text(c, _pt(20), H - _pt(52), "1. Contenu & Planning", size=30, font=FONT_TITLE)
        
        # ========== IMAGE DÉCORATIVE ==========
        # Ajout de l'image IMG-Planning.png (même style que Sommaire/Objectifs)
        try:
            img_path = "app/static/img/report/IMG-Planning.png"
            if os.path.exists(img_path):
                img_w, img_h = _pt(80), _pt(60)  # Dimensions de l'image
                img_x = W - _pt(120)  # Position X (120mm depuis la droite)
                img_y = H - _pt(50)  # Position Y (50mm depuis le haut)
                
                # Dessin de l'image
                c.drawImage(img_path, img_x, img_y, width=img_w, height=img_h)
                
                # Texte "PLANNING" centré sur l'image
                _draw_text(c, img_x + img_w/2, img_y + img_h/2, "PLANNING", 
                          size=16, color="#0a0a0a", font=FONT_TITLE, center=True)
                
        except Exception as e:
            print(f"Erreur lors du chargement de l'image IMG-Planning: {e}")
        
        # ========== DIAGRAMME DE GANTT ==========
        planning = self.ctx.get("planning", []) or []
        
        # Vérification si des données existent
        if not planning or len(planning) == 0:
            # Affichage d'un message informatif si aucune donnée du wizard
            info_text = "Veuillez renseigner le planning dans le wizard"
            c.setFont(FONT_TEXT, 20)
            c.drawString(_pt(20), H - _pt(70), info_text)
            c.showPage()
            return
        
        # Configuration du diagramme de Gantt - Une semaine par page
        from datetime import datetime, timedelta
        
        # Calculer les semaines nécessaires basées sur les dates des tâches
        all_dates = []
        for task in planning:
            if task.get("start") and task.get("end"):
                try:
                    start_dt = datetime.strptime(task.get("start"), "%Y-%m-%d")
                    end_dt = datetime.strptime(task.get("end"), "%Y-%m-%d")
                    all_dates.extend([start_dt, end_dt])
                except:
                    pass
        
        if not all_dates:
            # Fallback si aucune date valide
            all_dates = [datetime.strptime("2025-09-11", "%Y-%m-%d")]
        
        # Trouver la première et dernière semaine
        min_date = min(all_dates)
        max_date = max(all_dates)
        
        # Calculer le lundi de la première semaine
        first_monday = min_date - timedelta(days=min_date.weekday())
        last_monday = max_date - timedelta(days=max_date.weekday())
        
        # Générer toutes les semaines nécessaires
        weeks = []
        current_monday = first_monday
        while current_monday <= last_monday:
            week_dates = []
            week_labels = []
            for i in range(7):
                current_date = current_monday + timedelta(days=i)
                week_dates.append(current_date)
                day_name = ["LU", "MA", "ME", "JE", "VE", "SA", "DI"][i]
                day_number = current_date.day
                month_abbr = current_date.strftime("%b")
                week_labels.append(f"{day_name} {day_number} {month_abbr}")
            weeks.append({
                'monday': current_monday,
                'dates': week_dates,
                'labels': week_labels
            })
            current_monday += timedelta(days=7)
        
        print(f"DEBUG - Nombre de semaines: {len(weeks)}")
        print(f"DEBUG - Première semaine: {first_monday.strftime('%Y-%m-%d')}")
        print(f"DEBUG - Dernière semaine: {last_monday.strftime('%Y-%m-%d')}")
        
        # Dessiner chaque semaine sur une page séparée
        for week_index, week in enumerate(weeks):
            if week_index > 0:
                # Nouvelle page pour chaque semaine (sauf la première)
                c.showPage()
                n += 1
                self._start_landscape(n)
                c, W, H = self.c, self.W, self.H
                
                # Retitre pour chaque page
                _draw_text(c, _pt(20), H - _pt(52), f"1. Contenu & Planning - Semaine {week_index + 1}", size=30, font=FONT_TITLE)
                
                # Image décorative pour chaque page
                try:
                    img_path = "app/static/img/report/IMG-Planning.png"
                    if os.path.exists(img_path):
                        img_w, img_h = _pt(80), _pt(60)
                        img_x = W - _pt(120)
                        img_y = H - _pt(50)
                        c.drawImage(img_path, img_x, img_y, width=img_w, height=img_h)
                        _draw_text(c, img_x + img_w/2, img_y + img_h/2, "PLANNING", 
                                  size=16, color="#0a0a0a", font=FONT_TITLE, center=True)
                except Exception as e:
                    print(f"Erreur lors du chargement de l'image IMG-Planning: {e}")
            
            # Configuration pour cette semaine
            start_y = H - _pt(70)
            row_height = _pt(8)
            task_col_width = _pt(80)
            day_col_width = (W - task_col_width - _pt(40)) / 7  # 7 jours par semaine
            
            # Dessin de l'en-tête
            c.setFillColor(HexColor("#f3f4f6"))
            c.rect(_pt(20), start_y - row_height, W - _pt(40), row_height, stroke=0, fill=1)
            
            # Pas de bordures verticales - seulement des traits horizontaux
            c.setStrokeColor(HexColor("#000"))
            c.setLineWidth(1)
            
            # Texte de l'en-tête
            c.setFillColor(HexColor("#000"))
            c.setFont(FONT_TEXT, 10)
            
            # Titre "TASKS"
            c.drawString(_pt(22), start_y - row_height + _pt(2), "TASKS")
            
            # Titres des jours avec dates (cette semaine seulement) - Tout sur une ligne, centrés
            c.setFont(FONT_TEXT, 9)  # Police plus grande pour une semaine
            for i, label in enumerate(week['labels']):
                # Calculer la position X centrée pour cette colonne
                col_start_x = _pt(20) + task_col_width + i * day_col_width
                col_center_x = col_start_x + day_col_width / 2
                
                # Calculer la largeur du texte pour le centrer
                text_width = c.stringWidth(label, FONT_TEXT, 9)
                text_x = col_center_x - text_width / 2
                
                # Dessiner le texte centré
                c.drawString(text_x, start_y - row_height + _pt(2), label)
            
            # Dessin des tâches et barres de Gantt pour cette semaine
            y = start_y - row_height
            colors = [HexColor("#1e40af"), HexColor("#3b82f6"), HexColor("#60a5fa"), HexColor("#93c5fd")]
            
            for i, task in enumerate(planning):
                y -= row_height
                
                # Trait horizontal allant du premier au dernier jour de la semaine
                first_day_x = _pt(20) + task_col_width
                last_day_x = _pt(20) + task_col_width + 7 * day_col_width
                c.line(first_day_x, y, last_day_x, y)
                
                # Nom de la tâche
                task_name = task.get("task", "") or task.get("name", "") or f"Tâche {i+1}"
                c.setFont(FONT_TEXT, 9)
                c.drawString(_pt(22), y + _pt(1), task_name[:30] + "..." if len(task_name) > 30 else task_name)
                
                # Analyse des dates pour déterminer les jours concernés dans cette semaine
                start_date = task.get("start", "")
                end_date = task.get("end", "")
                
                if start_date and end_date:
                    try:
                        # Conversion des dates string en objets datetime
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        
                        # Déterminer quels jours de cette semaine sont concernés
                        affected_days = []
                        
                        # Parcourir chaque jour entre start et end
                        current_date = start_dt
                        while current_date <= end_dt:
                            # Vérifier si cette date fait partie de cette semaine
                            for day_index, week_date in enumerate(week['dates']):
                                if current_date.date() == week_date.date():
                                    affected_days.append(day_index)
                                    break
                            current_date = current_date.replace(day=current_date.day + 1)
                        
                        # Dessiner les barres pour chaque jour concerné
                        color = colors[i % len(colors)]
                        c.setFillColor(color)
                        
                        for day_index in affected_days:
                            # Position de la barre pour ce jour
                            bar_x = _pt(20) + task_col_width + day_index * day_col_width + _pt(1)
                            bar_width = day_col_width - _pt(2)
                            bar_y = y + _pt(1)
                            bar_height = row_height - _pt(2)
                            
                            # Dessiner la barre pour ce jour
                            c.rect(bar_x, bar_y, bar_width, bar_height, stroke=0, fill=1)
                        
                        print(f"DEBUG - Semaine {week_index + 1}, Tâche '{task_name}': {start_date} à {end_date}, Jours: {affected_days}")
                        
                    except Exception as e:
                        print(f"DEBUG - Erreur parsing dates pour '{task_name}': {e}")
        
        c.showPage()

    def _generate_success_rate_chart(self, df, excel_path):
        """
        Génère un graphique de ligne des taux de réussite avec seaborn.
        
        RETOURNE : Chemin vers l'image générée
        """
        try:
            import seaborn as sns
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')  # Backend non-interactif
            
            # Configuration du style
            plt.style.use('default')
            sns.set_palette("husl")
            
            # Préparation des données
            # Chercher les colonnes qui contiennent les données de test
            columns = list(df.columns)
            print(f"DEBUG - Colonnes disponibles: {columns}")
            
            # Essayer de trouver les bonnes colonnes
            nom_col = None
            test_in_col = None
            test_out_col = None
            
            for col in columns:
                col_lower = col.lower()
                if 'nom' in col_lower or 'name' in col_lower or 'stagiaire' in col_lower:
                    nom_col = col
                elif 'test' in col_lower and ('in' in col_lower or 'entrée' in col_lower):
                    test_in_col = col
                elif 'test' in col_lower and ('out' in col_lower or 'sortie' in col_lower):
                    test_out_col = col
            
            # Si pas trouvé, utiliser les premières colonnes
            if not nom_col and len(columns) > 0:
                nom_col = columns[0]
            if not test_in_col and len(columns) > 1:
                test_in_col = columns[1]
            if not test_out_col and len(columns) > 2:
                test_out_col = columns[2]
            
            print(f"DEBUG - Colonnes utilisées - Nom: {nom_col}, Test In: {test_in_col}, Test Out: {test_out_col}")
            
            if not all([nom_col, test_in_col, test_out_col]):
                print("DEBUG - Colonnes manquantes pour le graphique")
                return None
            
            # Préparer les données pour le graphique
            df_plot = df[[nom_col, test_in_col, test_out_col]].copy()
            df_plot.columns = ['Nom', 'Test In', 'Test Out']
            
            # Convertir en format long pour seaborn
            df_long = df_plot.melt(id_vars=['Nom'], var_name='Test', value_name='Taux de réussite')
            
            # Créer le graphique avec une taille plus large pour l'axe X
            plt.figure(figsize=(18, 8))
            
            # Graphique de ligne
            sns.lineplot(data=df_long, x='Nom', y='Taux de réussite', hue='Test', 
                        marker='o', linewidth=1, markersize=8)
            
            # Personnalisation avec polices agrandies
            plt.title('Taux de réussite In/Out', fontsize=20, fontweight='bold', pad=20)
            plt.xlabel('Stagiaires', fontsize=16, fontweight='bold')
            plt.ylabel('Taux de réussite (%)', fontsize=16, fontweight='bold')
            
            # Rotation des labels x pour éviter le chevauchement
            plt.xticks(rotation=45, ha='right', fontsize=14)
            plt.yticks(fontsize=14)
            
            # Limites de l'axe Y
            plt.ylim(0, 120)
            
            # Légende avec police agrandie, centrée en haut
            plt.legend( loc='upper center', bbox_to_anchor=(0.5, 1.05), 
                      ncol=2, fontsize=14, title_fontsize=16)
            
            # Grille horizontale uniquement (pas de lignes verticales)
            plt.grid(True, alpha=0.3, axis='y')
            
            # Enlever les bordures supérieure et droite
            ax = plt.gca()
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # Ajouter des étiquettes sur les points
            for test_type in df_long['Test'].unique():
                test_data = df_long[df_long['Test'] == test_type]
                for _, row in test_data.iterrows():
                    plt.annotate(f'{row["Taux de réussite"]:.0f}%', 
                               (row['Nom'], row['Taux de réussite']),
                               textcoords="offset points", 
                               xytext=(0,10), 
                               ha='center',
                               fontsize=10,
                               fontweight='bold')
            
            # Ajuster la mise en page avec plus d'espace horizontal
            plt.tight_layout()
            plt.subplots_adjust(bottom=0.15, left=0.1, right=0.95, top=0.85)
            
            # Sauvegarder l'image avec un nom unique basé sur le contenu du fichier
            chart_dir = os.path.dirname(excel_path)
            
            # Créer un hash du contenu du fichier pour un nom unique
            import hashlib
            with open(excel_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
            
            chart_filename = f'success_rate_chart_{file_hash}.png'
            chart_path = os.path.join(chart_dir, chart_filename)
            
            print(f"DEBUG - Nom unique du graphique: {chart_filename}")
            
            # Supprimer toutes les anciennes images de graphique
            import glob
            old_charts = glob.glob(os.path.join(chart_dir, 'success_rate_chart_*.png'))
            for old_chart in old_charts:
                try:
                    if old_chart != chart_path:  # Ne pas supprimer la nouvelle
                        os.remove(old_chart)
                        print(f"DEBUG - Ancienne image supprimée: {old_chart}")
                except Exception as e:
                    print(f"DEBUG - Erreur suppression ancienne image: {e}")
            
            plt.savefig(chart_path, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            
            print(f"DEBUG - Graphique sauvegardé: {chart_path}")
            return chart_path
            
        except Exception as e:
            print(f"DEBUG - Erreur génération graphique seaborn: {e}")
            return None

    def _calculate_progression_metrics(self, excel_path):
        """Calcule les métriques de progression depuis le fichier Excel."""
        try:
            import pandas as pd
            
            if not excel_path:
                return {'avg_test_in': 0, 'avg_test_out': 0, 'avg_evolution': 0}
            
            # Convertir le chemin web en chemin local
            local_path = excel_path.lstrip("/")
            if local_path.startswith("static/"):
                local_path = os.path.join("app", local_path)
            
            if not os.path.exists(local_path):
                print(f"DEBUG - Fichier Excel non trouvé: {local_path}")
                return {'avg_test_in': 0, 'avg_test_out': 0, 'avg_evolution': 0}
            
            # Lire le fichier Excel
            df = pd.read_excel(local_path)
            print(f"DEBUG - Métriques calculées depuis: {local_path}")
            print(f"DEBUG - Shape DataFrame métriques: {df.shape}")
            
            # Identifier les colonnes
            columns = df.columns.tolist()
            nom_col = None
            test_in_col = None
            test_out_col = None
            
            for col in columns:
                col_lower = col.lower()
                if 'stagiaire' in col_lower or 'nom' in col_lower:
                    nom_col = col
                elif 'test_in' in col_lower or 'in' in col_lower:
                    test_in_col = col
                elif 'test_out' in col_lower or 'out' in col_lower:
                    test_out_col = col
            
            if not all([nom_col, test_in_col, test_out_col]):
                print("DEBUG - Colonnes manquantes pour les métriques")
                return {'avg_test_in': 0, 'avg_test_out': 0, 'avg_evolution': 0}
            
            # Calculer les métriques
            avg_test_in = df[test_in_col].mean()
            avg_test_out = df[test_out_col].mean()
            avg_evolution = avg_test_out - avg_test_in
            
            metrics = {
                'avg_test_in': round(avg_test_in, 1),
                'avg_test_out': round(avg_test_out, 1),
                'avg_evolution': round(avg_evolution, 1),
                'total_participants': len(df),
                'success_rate_in': round((df[test_in_col] >= 70).mean() * 100, 1),
                'success_rate_out': round((df[test_out_col] >= 70).mean() * 100, 1)
            }
            
            print(f"DEBUG - Métriques calculées: {metrics}")
            return metrics
            
        except Exception as e:
            print(f"DEBUG - Erreur calcul métriques: {e}")
            return {'avg_test_in': 0, 'avg_test_out': 0, 'avg_evolution': 0}

    def _generate_interpretation(self, metrics):
        """Génère une interprétation basée sur les métriques."""
        avg_in = metrics.get('avg_test_in', 0)
        avg_out = metrics.get('avg_test_out', 0)
        evolution = metrics.get('avg_evolution', 0)
        success_rate_out = metrics.get('success_rate_out', 0)
        
        # Générer une phrase unique et compacte
        interpretation_parts = []
        
        # Analyse du niveau initial
        if avg_in >= 80:
            interpretation_parts.append("Un excellent niveau initial")
        elif avg_in >= 70:
            interpretation_parts.append("Un bon niveau initial")
        elif avg_in >= 60:
            interpretation_parts.append("Un niveau initial moyen")
        else:
            interpretation_parts.append("Un niveau initial nécessitant attention")
        
        # Analyse de la progression
        if evolution > 10:
            interpretation_parts.append("progression remarquable")
        elif evolution > 5:
            interpretation_parts.append("bonne progression")
        elif evolution > 0:
            interpretation_parts.append("progression modérée")
        elif evolution == 0:
            interpretation_parts.append("niveau stable")
        else:
            interpretation_parts.append("régression observée")
        
        # Analyse du niveau final
        if avg_out >= 90:
            interpretation_parts.append("niveau final excellent")
        elif avg_out >= 80:
            interpretation_parts.append("niveau final très satisfaisant")
        elif avg_out >= 70:
            interpretation_parts.append("niveau final satisfaisant")
        else:
            interpretation_parts.append("niveau final à améliorer")
        
        # Recommandation
        if success_rate_out >= 80:
            recommendation = "maintenir les méthodes actuelles"
        elif success_rate_out >= 60:
            recommendation = "renforcer le suivi individuel"
        else:
            recommendation = "réviser la méthode pédagogique"
        
        # Construire la phrase unique
        interpretation = f"Cela indique que le groupe avait un {interpretation_parts[0]}. En effet, la formation a généré une {interpretation_parts[1]} avec {interpretation_parts[2]}. Il est donc recommandé de {recommendation}."
        
        return interpretation

    def _wrap_text(self, text, max_width, font_size):
        """Enveloppe le texte pour qu'il tienne dans la largeur donnée."""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if self.c.stringWidth(test_line, FONT_TEXT, font_size) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines

    def _calculate_top_progress(self, excel_path):
        """Calcule les meilleures progressions depuis le fichier Excel."""
        try:
            import pandas as pd
            
            if not excel_path:
                return []
            
            # Convertir le chemin web en chemin local
            local_path = excel_path.lstrip("/")
            if local_path.startswith("static/"):
                local_path = os.path.join("app", local_path)
            
            if not os.path.exists(local_path):
                print(f"DEBUG - Fichier Excel non trouvé pour top progress: {local_path}")
                return []
            
            # Lire le fichier Excel
            df = pd.read_excel(local_path)
            print(f"DEBUG - Top progress calculé depuis: {local_path}")
            
            # Identifier les colonnes
            columns = df.columns.tolist()
            nom_col = None
            test_in_col = None
            test_out_col = None
            
            for col in columns:
                col_lower = col.lower()
                if 'stagiaire' in col_lower or 'nom' in col_lower:
                    nom_col = col
                elif 'test_in' in col_lower or 'in' in col_lower:
                    test_in_col = col
                elif 'test_out' in col_lower or 'out' in col_lower:
                    test_out_col = col
            
            if not all([nom_col, test_in_col, test_out_col]):
                print("DEBUG - Colonnes manquantes pour top progress")
                return []
            
            # Calculer les progressions
            df['progression'] = df[test_out_col] - df[test_in_col]
            
            # Trier par progression décroissante
            top_progress = df.nlargest(3, 'progression')
            
            # Formater les résultats
            results = []
            for _, row in top_progress.iterrows():
                results.append({
                    'name': str(row[nom_col]),
                    'test_in': float(row[test_in_col]),
                    'test_out': float(row[test_out_col]),
                    'progression': float(row['progression'])
                })
            
            print(f"DEBUG - Top progress calculé: {len(results)} participants")
            return results
            
        except Exception as e:
            print(f"DEBUG - Erreur calcul top progress: {e}")
            return []

    def _generate_top_progress_interpretation(self, top_progress):
        """Génère une interprétation des meilleures progressions."""
        if not top_progress:
            return "Aucune donnée de progression disponible."
        
        # Analyser les progressions
        progressions = [p['progression'] for p in top_progress]
        max_progression = max(progressions) if progressions else 0
        avg_progression = sum(progressions) / len(progressions) if progressions else 0
        
        # Générer l'interprétation
        if max_progression >= 40:
            interpretation = "Ces résultats mettent en lumière des progressions exceptionnelles qui témoignent de l'efficacité de la formation et de l'engagement remarquable des participants."
        elif max_progression >= 30:
            interpretation = "Ces résultats mettent en lumière des progressions significatives qui démontrent la qualité de la formation et la motivation des participants."
        elif max_progression >= 20:
            interpretation = "Ces résultats mettent en lumière des progressions notables qui confirment l'impact positif de la formation sur les participants."
        else:
            interpretation = "Ces résultats montrent des progressions modérées qui indiquent un impact positif de la formation."
        
        # Ajouter des recommandations
        if avg_progression >= 30:
            interpretation += " Il est recommandé de valoriser ces réussites et d'utiliser ces cas comme exemples pour motiver l'ensemble du groupe."
        elif avg_progression >= 20:
            interpretation += " Ces performances méritent d'être mises en avant pour encourager les autres participants."
        else:
            interpretation += " Ces résultats encouragent à poursuivre les efforts pédagogiques."
        
        return interpretation

    def _calculate_cases_to_watch(self, excel_path):
        """Calcule les cas à surveiller (plus faibles progressions) depuis le fichier Excel."""
        try:
            import pandas as pd
            
            if not excel_path:
                return []
            
            # Convertir le chemin web en chemin local
            local_path = excel_path.lstrip("/")
            if local_path.startswith("static/"):
                local_path = os.path.join("app", local_path)
            
            if not os.path.exists(local_path):
                print(f"DEBUG - Fichier Excel non trouvé pour cas à surveiller: {local_path}")
                return []
            
            # Lire le fichier Excel
            df = pd.read_excel(local_path)
            print(f"DEBUG - Cas à surveiller calculé depuis: {local_path}")
            
            # Identifier les colonnes
            columns = df.columns.tolist()
            nom_col = None
            test_in_col = None
            test_out_col = None
            
            for col in columns:
                col_lower = col.lower()
                if 'stagiaire' in col_lower or 'nom' in col_lower:
                    nom_col = col
                elif 'test_in' in col_lower or 'in' in col_lower:
                    test_in_col = col
                elif 'test_out' in col_lower or 'out' in col_lower:
                    test_out_col = col
            
            if not all([nom_col, test_in_col, test_out_col]):
                print("DEBUG - Colonnes manquantes pour cas à surveiller")
                return []
            
            # Calculer les progressions
            df['progression'] = df[test_out_col] - df[test_in_col]
            
            # Trier par progression croissante (les plus faibles progressions)
            cases_to_watch = df.nsmallest(3, 'progression')
            
            # Formater les résultats
            results = []
            for _, row in cases_to_watch.iterrows():
                results.append({
                    'name': str(row[nom_col]),
                    'test_in': float(row[test_in_col]),
                    'test_out': float(row[test_out_col]),
                    'progression': float(row['progression'])
                })
            
            print(f"DEBUG - Cas à surveiller calculé: {len(results)} participants")
            return results
            
        except Exception as e:
            print(f"DEBUG - Erreur calcul cas à surveiller: {e}")
            return []

    def _generate_cases_to_watch_interpretation(self, cases_to_watch):
        """Génère une interprétation des cas à surveiller."""
        if not cases_to_watch:
            return "Aucune donnée de progression disponible."
        
        # Analyser les progressions
        progressions = [p['progression'] for p in cases_to_watch]
        min_progression = min(progressions) if progressions else 0
        avg_progression = sum(progressions) / len(progressions) if progressions else 0
        
        # Générer l'interprétation
        if min_progression < 0:
            interpretation = "Ces résultats révèlent des cas préoccupants avec des régressions qui nécessitent une attention immédiate et un accompagnement renforcé."
        elif min_progression < 5:
            interpretation = "Ces résultats mettent en évidence des progressions très faibles qui indiquent des difficultés d'apprentissage nécessitant un suivi personnalisé."
        elif min_progression < 10:
            interpretation = "Ces résultats montrent des progressions limitées qui suggèrent la nécessité d'un accompagnement adapté et d'un renforcement pédagogique."
        else:
            interpretation = "Ces résultats indiquent des progressions modérées qui bénéficieraient d'un suivi renforcé pour optimiser l'apprentissage."
        
        # Ajouter des recommandations
        if min_progression < 0:
            interpretation += " Il est urgent de mettre en place un plan d'accompagnement individuel et de réviser les méthodes pédagogiques pour ces participants."
        elif min_progression < 5:
            interpretation += " Il est recommandé d'intensifier le suivi individuel et d'adapter les méthodes d'apprentissage à leurs besoins spécifiques."
        else:
            interpretation += " Ces participants bénéficieraient d'un accompagnement personnalisé pour améliorer leurs résultats."
        
        return interpretation

    def _generate_general_conclusion(self, metrics, top_progress, cases_to_watch):
        """Génère une conclusion générale basée sur toutes les métriques."""
        if not metrics or not top_progress or not cases_to_watch:
            return "Aucune donnée disponible pour générer une conclusion."
        
        # Extraire les métriques principales
        avg_in = metrics.get('avg_test_in', 0)
        avg_out = metrics.get('avg_test_out', 0)
        evolution = metrics.get('avg_evolution', 0)
        total_participants = metrics.get('total_participants', 0)
        
        # Analyser les progressions extrêmes
        max_progression = max([p['progression'] for p in top_progress]) if top_progress else 0
        min_progression = min([p['progression'] for p in cases_to_watch]) if cases_to_watch else 0
        
        # Premier paragraphe - Vue d'ensemble
        conclusion_parts = []
        
        conclusion_parts.append(f"La formation a fourni une vue complète des résultats obtenus par les participants. Le taux de réussite moyen avant la formation était de {avg_in:.1f}% et après la formation de {avg_out:.1f}%. Cette progression correspond à une amélioration moyenne de {evolution:+.1f} points, indiquant un impact global positif de la formation.")
        
        # Deuxième paragraphe - Cas positifs
        if max_progression > 20:
            conclusion_parts.append(f"Certains stagiaires ont montré des progressions significatives, démontrant une bonne assimilation du contenu. Les meilleures performances atteignent jusqu'à {max_progression:+.0f} points d'amélioration.")
        elif max_progression > 10:
            conclusion_parts.append(f"Plusieurs stagiaires ont montré des progressions notables, témoignant d'une assimilation satisfaisante du contenu.")
        else:
            conclusion_parts.append(f"Les progressions observées sont modérées mais positives, indiquant une assimilation correcte du contenu.")
        
        # Troisième paragraphe - Cas à surveiller
        if min_progression < 0:
            conclusion_parts.append(f"Cependant, d'autres ont montré une baisse de performance, nécessitant une attention particulière et un accompagnement supplémentaire. Certains cas présentent même des régressions jusqu'à {min_progression:+.0f} points.")
        elif min_progression < 5:
            conclusion_parts.append(f"Cependant, certains stagiaires ont montré des progressions très faibles, nécessitant une attention particulière et un accompagnement supplémentaire.")
        else:
            conclusion_parts.append(f"Quelques stagiaires ont montré des progressions limitées, bénéficiant d'un suivi renforcé.")
        
        # Quatrième paragraphe - Recommandations
        if min_progression < 0:
            recommendation = f"Recommandation : Il est urgent de consolider les connaissances acquises par des séances de suivi individualisées, ciblant particulièrement les participants identifiés comme prioritaires, afin d'assurer une progression homogène et durable. Un plan d'accompagnement personnalisé doit être mis en place pour les cas les plus préoccupants."
        elif min_progression < 5:
            recommendation = f"Recommandation : Il est recommandé de consolider les connaissances acquises par des séances de suivi individualisées, ciblant les participants identifiés comme prioritaires, afin d'assurer une progression homogène et durable."
        else:
            recommendation = f"Recommandation : Il est conseillé de consolider les connaissances acquises par des séances de suivi individualisées, ciblant les participants identifiés comme prioritaires, afin d'assurer une progression homogène et durable."
        
        conclusion_parts.append(recommendation)
        
        return '\n\n'.join(conclusion_parts)

    def _draw_success_rate_chart(self, c, x, y, width, height, stagiaires_data):
        """
        Dessine un graphique de ligne montrant les taux de réussite Test In/Out.
        
        STRUCTURE :
        - Axe Y : Taux de réussite (0-120%)
        - Axe X : Noms des stagiaires
        - Ligne verte : Taux de réussite In (%)
        - Ligne rouge : Taux de réussite Out (%)
        - Légende avec couleurs
        """
        # Configuration du graphique
        margin_left = _pt(40)
        margin_bottom = _pt(30)
        margin_top = _pt(20)
        margin_right = _pt(20)
        
        # Zone de dessin du graphique
        chart_area_x = x + margin_left
        chart_area_y = y - height + margin_bottom
        chart_area_width = width - margin_left - margin_right
        chart_area_height = height - margin_top - margin_bottom
        
        # Dessin du cadre du graphique
        c.setStrokeColor(HexColor("#000"))
        c.setLineWidth(1)
        c.rect(chart_area_x, chart_area_y, chart_area_width, chart_area_height)
        
        # Configuration des axes
        y_min, y_max = 0, 120
        y_step = 20
        
        # Dessin de l'axe Y (taux de réussite)
        c.setFont(FONT_TEXT, 10)
        c.drawString(x + _pt(5), chart_area_y + chart_area_height/2, "Taux de réussite")
        
        # Graduations de l'axe Y
        for i in range(y_min, y_max + 1, y_step):
            y_pos = chart_area_y + (i - y_min) / (y_max - y_min) * chart_area_height
            c.line(chart_area_x - _pt(5), y_pos, chart_area_x, y_pos)
            c.drawString(x + _pt(10), y_pos - _pt(3), f"{i}%")
        
        # Dessin de l'axe X (stagiaires)
        c.drawString(chart_area_x + chart_area_width/2, chart_area_y - _pt(20), "Stagiaires")
        
        # Calcul des positions des stagiaires sur l'axe X
        num_stagiaires = len(stagiaires_data)
        if num_stagiaires == 0:
            return
            
        x_step = chart_area_width / max(1, num_stagiaires - 1)
        
        # Dessin des noms des stagiaires (rotation pour économiser l'espace)
        c.setFont(FONT_TEXT, 8)
        for i, stagiaire in enumerate(stagiaires_data):
            x_pos = chart_area_x + i * x_step
            name = stagiaire.get("nom", f"Stagiaire {i+1}")
            # Tronquer le nom s'il est trop long
            if len(name) > 12:
                name = name[:9] + "..."
            c.drawString(x_pos - _pt(15), chart_area_y - _pt(15), name)
        
        # Dessin des lignes de données
        colors = {
            "in": HexColor("#00ff00"),   # Vert pour Test In
            "out": HexColor("#ff0000")  # Rouge pour Test Out
        }
        
        # Dessin de la ligne Test In (verte)
        c.setStrokeColor(colors["in"])
        c.setLineWidth(2)
        points_in = []
        for i, stagiaire in enumerate(stagiaires_data):
            taux_in = float(stagiaire.get("test_in", 0))
            x_pos = chart_area_x + i * x_step
            y_pos = chart_area_y + (taux_in - y_min) / (y_max - y_min) * chart_area_height
            points_in.append((x_pos, y_pos))
            
            # Dessin du point
            c.circle(x_pos, y_pos, _pt(2), fill=1, stroke=0)
        
        # Dessin de la ligne Test In
        if len(points_in) > 1:
            for i in range(len(points_in) - 1):
                c.line(points_in[i][0], points_in[i][1], points_in[i+1][0], points_in[i+1][1])
        
        # Dessin de la ligne Test Out (rouge)
        c.setStrokeColor(colors["out"])
        c.setLineWidth(2)
        points_out = []
        for i, stagiaire in enumerate(stagiaires_data):
            taux_out = float(stagiaire.get("test_out", 0))
            x_pos = chart_area_x + i * x_step
            y_pos = chart_area_y + (taux_out - y_min) / (y_max - y_min) * chart_area_height
            points_out.append((x_pos, y_pos))
            
            # Dessin du point
            c.circle(x_pos, y_pos, _pt(2), fill=1, stroke=0)
        
        # Dessin de la ligne Test Out
        if len(points_out) > 1:
            for i in range(len(points_out) - 1):
                c.line(points_out[i][0], points_out[i][1], points_out[i+1][0], points_out[i+1][1])
        
        # Dessin de la légende
        legend_x = chart_area_x + chart_area_width - _pt(80)
        legend_y = chart_area_y + chart_area_height + _pt(10)
        
        c.setFont(FONT_TEXT, 10)
        
        # Légende Test In (vert)
        c.setFillColor(colors["in"])
        c.circle(legend_x, legend_y, _pt(3), fill=1, stroke=0)
        c.setFillColor(HexColor("#000"))
        c.drawString(legend_x + _pt(8), legend_y - _pt(3), "Taux de réussite In (%)")
        
        # Légende Test Out (rouge)
        c.setFillColor(colors["out"])
        c.circle(legend_x, legend_y - _pt(15), _pt(3), fill=1, stroke=0)
        c.setFillColor(HexColor("#000"))
        c.drawString(legend_x + _pt(8), legend_y - _pt(18), "Taux de réussite Out (%)")

    def eval_pages(self, n):
        """
        Génère les pages d'évaluation et d'analyses (3 pages).
        
        PAGE 1 (n) : Graphiques de performance
        - Titre : "2. Evaluation & Analyses"
        - Graphiques générés (si disponibles)
        - Analyses visuelles des résultats
        
        PAGE 2 (n+1) : KPIs et métriques
        - Indicateurs clés de performance
        - Métriques quantitatives de la formation
        
        PAGE 3 (n+2) : Analyses approfondies
        - Recommandations détaillées
        - Synthèses et conclusions partielles
        
        DONNÉES : self.ctx.get("charts", {}), self.ctx.get("kpi", {})
        """
        def w2d(p):
            if not p: return None
            p = p.lstrip("/"); return os.path.join("app", p) if p.startswith("static/") else p

        charts = self.ctx.get("charts") or {}
        kpi = self.ctx.get("kpi") or {}

        # PAGE 1: Graphique des taux de réussite Test In/Out
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # Titre principal
        _draw_text(c, _pt(20), H - _pt(52), "2. Evaluation & Analyses", size=30, font=FONT_TITLE)
        
        # Titre du graphique
        c.setFont(FONT_TEXT, 16)
        #c.drawString(_pt(20), H - _pt(70), "Taux de réussite In/Out")
        
        # Génération du graphique avec seaborn
        # Recharger le contexte pour avoir les données les plus récentes
        self.ctx = _load_ctx(self.sid)
        excel_path = self.ctx.get("excel_path", "")
        print(f"DEBUG - Chemin Excel dans le contexte (rechargé): {excel_path}")
        print(f"DEBUG - Type du chemin: {type(excel_path)}")
        print(f"DEBUG - Contexte complet (rechargé): {self.ctx}")
        
        chart_image_path = None
        
        if excel_path:
            try:
                # Vérifier les dépendances
                try:
                    import pandas as pd
                    print("DEBUG - pandas importé avec succès")
                except ImportError as e:
                    print(f"DEBUG - Erreur import pandas: {e}")
                    return
                
                try:
                    import seaborn as sns
                    print("DEBUG - seaborn importé avec succès")
                except ImportError as e:
                    print(f"DEBUG - Erreur import seaborn: {e}")
                    return
                
                try:
                    import matplotlib.pyplot as plt
                    import matplotlib
                    matplotlib.use('Agg')  # Backend non-interactif
                    print("DEBUG - matplotlib importé avec succès")
                except ImportError as e:
                    print(f"DEBUG - Erreur import matplotlib: {e}")
                    return
                
                # Convertir le chemin web en chemin local
                original_path = excel_path
                if excel_path.startswith('/static/'):
                    excel_path = excel_path[1:]  # Enlever le premier /
                    excel_path = os.path.join("app", excel_path)
                
                print(f"DEBUG - Chemin original: {original_path}")
                print(f"DEBUG - Chemin converti: {excel_path}")
                print(f"DEBUG - Fichier existe: {os.path.exists(excel_path)}")
                
                if os.path.exists(excel_path):
                    try:
                        # Lire le fichier Excel
                        df = pd.read_excel(excel_path)
                        print(f"DEBUG - Fichier Excel lu avec succès")
                        print(f"DEBUG - Shape du DataFrame: {df.shape}")
                        print(f"DEBUG - Colonnes Excel: {list(df.columns)}")
                        print(f"DEBUG - Premières lignes: {df.head()}")
                        
                        # Générer le graphique
                        chart_image_path = self._generate_success_rate_chart(df, excel_path)
                        
                    except Exception as e:
                        print(f"DEBUG - Erreur lecture Excel: {e}")
                        chart_image_path = None
                else:
                    print(f"DEBUG - Fichier Excel non trouvé: {excel_path}")
                    # Essayer d'autres chemins possibles
                    alt_paths = [
                        original_path,
                        os.path.join("app", "static", "uploads", os.path.basename(original_path)),
                        os.path.join("static", "uploads", os.path.basename(original_path))
                    ]
                    for alt_path in alt_paths:
                        print(f"DEBUG - Essai chemin alternatif: {alt_path} - Existe: {os.path.exists(alt_path)}")
                        if os.path.exists(alt_path):
                            excel_path = alt_path
                            break
            except Exception as e:
                print(f"DEBUG - Erreur génération graphique: {e}")
        
        # Affichage du graphique dans le PDF
        if chart_image_path and os.path.exists(chart_image_path):
            # Configuration de l'image - alignée avec le titre, agrandie
            img_x = _pt(0)  # Même X que le titre
            img_y = H - _pt(180)  # En dessous du titre, plus d'espace
            img_width = W - _pt(10)  # Largeur presque complète (10pt de marge de chaque côté)
            img_height = _pt(120)    # Hauteur agrandie
            
            # Dessin de l'image
            c.drawImage(chart_image_path, img_x, img_y, width=img_width, height=img_height,
                        preserveAspectRatio=True, mask='auto')
            
            print(f"DEBUG - Graphique inséré: {chart_image_path}")
            print(f"DEBUG - Position image: x={img_x}, y={img_y}, w={img_width}, h={img_height}")
        else:
            # Message si aucune donnée
            c.setFont(FONT_TEXT, 14)
            c.drawString(_pt(20), H - _pt(90), "Aucune donnée de stagiaires disponible")
            if excel_path:
                c.drawString(_pt(20), H - _pt(105), f"Fichier Excel: {excel_path}")
        
        c.showPage()

        # PAGE 2: Métriques de progression globale
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # Titre principal
        _draw_text(c, _pt(20), H - _pt(52), "2. Evaluation & Analyses", size=30, font=FONT_TITLE)
        
        # Sous-titre
        c.setFont(FONT_TITLE, 18)
        c.drawString(_pt(20), H - _pt(70), "💡 Progression Globale de la Formation (%)")
        
        # Calculer les métriques depuis les données Excel
        metrics = self._calculate_progression_metrics(excel_path)
        
        # Section métriques principales
        y_start = H - _pt(90)
        c.setFont(FONT_TITLE, 16)
        c.drawString(_pt(20), y_start, "Indicateurs de Performance :")
        
        # Métriques en format centré
        y = y_start - _pt(15)
        c.setFont(FONT_TEXT, 14)
        
        # Moyenne Test In
        c.drawString(_pt(20), y, "• Moyenne Test In :")
        c.setFont(FONT_TEXT, 16)
        c.drawString(_pt(150), y, f"{metrics.get('avg_test_in', 0):.1f}%")
        
        y -= _pt(12)
        c.setFont(FONT_TEXT, 14)
        
        # Moyenne Test Out
        c.drawString(_pt(20), y, "• Moyenne Test Out :")
        c.setFont(FONT_TEXT, 16)
        c.drawString(_pt(150), y, f"{metrics.get('avg_test_out', 0):.1f}%")
        
        y -= _pt(12)
        c.setFont(FONT_TEXT, 14)
        
        # Évolution moyenne
        evolution = metrics.get('avg_evolution', 0)
        c.drawString(_pt(20), y, "• Évolution moyenne :")
        c.setFont(FONT_TEXT, 16)
        c.setFillColorRGB(0, 0.8, 0) if evolution > 0 else c.setFillColorRGB(0.8, 0, 0) if evolution < 0 else c.setFillColorRGB(0, 0, 0)
        c.drawString(_pt(150), y, f"{evolution:+.1f} points")
        c.setFillColorRGB(0, 0, 0)  # Remettre en noir
        
        # Section interprétation
        y_section = y_start - _pt(55)
        c.setFont(FONT_TITLE, 16)
        c.drawString(_pt(20), y_section, "Interprétation :")
        
        y = y_section - _pt(14)
        c.setFont(FONT_TEXT, 16)
        
        # Interprétation basée sur les métriques
        interpretation = self._generate_interpretation(metrics)
        lines = self._wrap_text(interpretation, W - _pt(40), 16)
        c.setFont(FONT_TEXT, 16)
        for line in lines:
            c.drawString(_pt(22), y, line)
            y -= _pt(10)
        
        c.showPage(); n += 1

        # PAGE 3: Cas ayant le plus progressé
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # Titre principal
        _draw_text(c, _pt(20), H - _pt(52), "2. Evaluation & Analyses", size=30, font=FONT_TITLE)
        
        # Sous-titre
        c.setFont(FONT_TITLE, 18)
        c.drawString(_pt(20), H - _pt(70), "💡 Participants ayant le plus progressé ")
        
        # Calculer les meilleures progressions depuis les données Excel
        top_progress = self._calculate_top_progress(excel_path)
        
        # Section des meilleures progressions
        y_start = H - _pt(90)
        c.setFont(FONT_TITLE, 16)
        c.drawString(_pt(20), y_start, "Top 3 - Plus Grande Progression :")
        
        # Afficher les 3 meilleures progressions
        y = y_start - _pt(15)
        c.setFont(FONT_TEXT, 16)
        
        for i, participant in enumerate(top_progress[:3], 1):
            name = participant.get('name', f'Stagiaire {i}')
            progression = participant.get('progression', 0)
            test_in = participant.get('test_in', 0)
            test_out = participant.get('test_out', 0)
            
            c.drawString(_pt(20), y, f"{name} :")
            c.setFont(FONT_TEXT, 16)
            c.setFillColorRGB(0, 0.8, 0)  # Vert pour progression positive
            c.drawString(_pt(120), y, f"{progression:+.0f} points")
            c.setFillColorRGB(0, 0, 0)  # Remettre en noir
            c.setFont(FONT_TEXT, 16)
            c.drawString(_pt(150), y, f"({test_in:.0f} --> {test_out:.0f})")
            
            y -= _pt(15)
        
        # Section interprétation
        y_section = y_start - _pt(60)
        c.setFont(FONT_TITLE, 16)
        c.drawString(_pt(20), y_section, "Interprétation :")
        
        y = y_section - _pt(14)
        c.setFont(FONT_TEXT, 16)
        
        # Interprétation des meilleures progressions
        interpretation = self._generate_top_progress_interpretation(top_progress)
        lines = self._wrap_text(interpretation, W - _pt(40), 16)
        c.setFont(FONT_TEXT, 16)
        for line in lines:
            c.drawString(_pt(22), y, line)
            y -= _pt(10)
        
        c.showPage()

        # PAGE 4: Cas à surveiller
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # Titre principal
        _draw_text(c, _pt(20), H - _pt(52), "2. Evaluation & Analyses", size=30, font=FONT_TITLE)
        
        # Sous-titre
        c.setFont(FONT_TITLE, 18)
        c.drawString(_pt(20), H - _pt(70), "💡 Cas à surveiller")
        
        # Calculer les cas à surveiller depuis les données Excel
        cases_to_watch = self._calculate_cases_to_watch(excel_path)
        
        # Section des cas à surveiller
        y_start = H - _pt(90)
        c.setFont(FONT_TITLE, 16)
        c.drawString(_pt(20), y_start, "Top 3 - Cas à surveiller :")
        
        # Afficher les 3 cas à surveiller
        y = y_start - _pt(15)
        c.setFont(FONT_TEXT, 16)
        
        for i, participant in enumerate(cases_to_watch[:3], 1):
            name = participant.get('name', f'Stagiaire {i}')
            progression = participant.get('progression', 0)
            test_in = participant.get('test_in', 0)
            test_out = participant.get('test_out', 0)
            
            c.drawString(_pt(20), y, f"{name} :")
            c.setFont(FONT_TEXT, 16)
            c.setFillColorRGB(0.8, 0, 0)  # Rouge pour progression négative ou faible
            c.drawString(_pt(120), y, f"{progression:+.0f} points")
            c.setFillColorRGB(0, 0, 0)  # Remettre en noir
            c.setFont(FONT_TEXT, 16)
            c.drawString(_pt(150), y, f"({test_in:.0f} --> {test_out:.0f})")
            
            y -= _pt(15)
        
        # Section interprétation
        y_section = y_start - _pt(60)
        c.setFont(FONT_TITLE, 16)
        c.drawString(_pt(20), y_section, "Interprétation :")
        
        y = y_section - _pt(14)
        c.setFont(FONT_TEXT, 16)
        
        # Interprétation des cas à surveiller
        interpretation = self._generate_cases_to_watch_interpretation(cases_to_watch)
        lines = self._wrap_text(interpretation, W - _pt(40), 16)
        c.setFont(FONT_TEXT, 16)
        for line in lines:
            c.drawString(_pt(22), y, line)
            y -= _pt(10)
        
        c.showPage()

        # PAGE 5: Conclusion générale Évaluation & Analyses
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # Titre principal
        _draw_text(c, _pt(20), H - _pt(52), "2. Evaluation & Analyses", size=30, font=FONT_TITLE)
        
        # Sous-titre
        c.setFont(FONT_TITLE, 18)
        c.drawString(_pt(20), H - _pt(70), "💡 Conclusion et recommandations")
        
        # Calculer les métriques pour la conclusion
        metrics = self._calculate_progression_metrics(excel_path)
        top_progress = self._calculate_top_progress(excel_path)
        cases_to_watch = self._calculate_cases_to_watch(excel_path)
        
        # Générer la conclusion générale
        conclusion = self._generate_general_conclusion(metrics, top_progress, cases_to_watch)
        
        # Section conclusion
        y_start = H - _pt(80)
        c.setFont(FONT_TEXT, 14)
        
        # Diviser la conclusion en paragraphes et les afficher
        paragraphs = conclusion.split('\n\n')
        y = y_start
        
        for paragraph in paragraphs:
            if paragraph.strip():
                lines = self._wrap_text(paragraph.strip(), W - _pt(40), 14)
                for line in lines:
                    c.drawString(_pt(20), y, line)
                    y -= _pt(8)
                y -= _pt(5)  # Espacement entre paragraphes
        
        c.showPage()

    def media(self, n):
        """
        Génère la page médiathèque avec galerie d'images de la formation.
        
        STRUCTURE :
        - Titre : "3. Médiathèque"
        - Grille 2x4 (8 photos par page)
        - Boîtes simples avec ombres
        - Pagination automatique
        
        DONNÉES : self.ctx.get("media_paths", [])
        """
        media = self.ctx.get("media_paths", []) or []
        
        if not media:
            # Page vide si pas d'images
            self._start_landscape(n)
            c, W, H = self.c, self.W, self.H
            _draw_text(c, _pt(20), H - _pt(52), "3. Médiathèque", size=30, font=FONT_TITLE)
            c.setFont(FONT_TEXT, 16)
            c.drawString(_pt(20), H - _pt(80), "Aucune image disponible")
            c.showPage()
            return
        
        # Calculer le nombre de pages nécessaires
        images_per_page = 8
        total_pages = (len(media) + images_per_page - 1) // images_per_page
        
        for page_num in range(total_pages):
            self._start_landscape(n + page_num)
            c, W, H = self.c, self.W, self.H
            
            # Titre principal
            _draw_text(c, _pt(20), H - _pt(52), "3. Médiathèque", size=30, font=FONT_TITLE)
            
            # Images pour cette page
            start_idx = page_num * images_per_page
            end_idx = min(start_idx + images_per_page, len(media))
            page_images = media[start_idx:end_idx]
            
            # Configuration de la grille
            cols = 4
            rows = 2
            box_width = _pt(50)
            box_height = _pt(50)
            margin_x = _pt(20)
            margin_y = _pt(50)
            spacing_x = _pt(15)
            spacing_y = _pt(15)
            
            # Dessiner les images dans la grille
            for i, img_path in enumerate(page_images):
                row = i // cols
                col = i % cols
                
                x = margin_x + col * (box_width + spacing_x)
                y = H - margin_y - (row + 1) * (box_height + spacing_y)
                
                self._draw_image_box(c, x, y, box_width, box_height, img_path)
            
            c.showPage()
    
    def _draw_image_box(self, c, x, y, width, height, image_path):
        """Dessine une boîte simple contenant une image."""
        # Dessiner l'ombre (légèrement décalée)
        shadow_offset = _pt(2)
        c.setFillColorRGB(0.8, 0.8, 0.8)
        c.rect(x + shadow_offset, y - shadow_offset, width, height, fill=1)
        
        # Dessiner la boîte principale
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(0.9, 0.9, 0.9)
        c.setLineWidth(1)
        c.rect(x, y, width, height, fill=1, stroke=1)
        
        # Dessiner l'image si elle existe
        if image_path:
            try:
                local_path = _web_to_disk(image_path)
                if local_path and os.path.exists(local_path):
                    # Calculer les dimensions de l'image pour qu'elle s'adapte dans la boîte
                    img_margin = _pt(5)
                    img_x = x + img_margin
                    img_y = y + img_margin
                    img_width = width - 2 * img_margin
                    img_height = height - 2 * img_margin
                    
                    # Centrer l'image dans le conteneur
                    c.drawImage(local_path, img_x, img_y, width=img_width, height=img_height,
                              preserveAspectRatio=True, anchor='c')
                else:
                    # Placeholder si l'image n'existe pas
                    self._draw_placeholder(c, x, y, width, height)
            except Exception as e:
                print(f"DEBUG - Erreur affichage image {image_path}: {e}")
                # Placeholder en cas d'erreur
                self._draw_placeholder(c, x, y, width, height)
        else:
            # Placeholder si pas d'image
            self._draw_placeholder(c, x, y, width, height)
    
    def _draw_placeholder(self, c, x, y, width, height):
        """Dessine un placeholder pour les images manquantes."""
        c.setFont(FONT_TEXT, 10)
        c.setFillColorRGB(0.7, 0.7, 0.7)
        text = "Image non disponible"
        text_width = c.stringWidth(text, FONT_TEXT, 10)
        text_x = x + (width - text_width) / 2
        text_y = y + height / 2
        c.drawString(text_x, text_y, text)
        c.setFillColorRGB(0, 0, 0)

    def appreciation(self, n):
        """
        Génère la page d'appréciation du formateur avec images SVG.
        
        STRUCTURE :
        - Titre : "4. Appréciation formateur"
        - 5 images SVG générées dynamiquement pour chaque catégorie
        - Design moderne avec cartes et barres de progression
        
        DONNÉES : self.ctx.get("appreciation", {})
        """
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # Titre principal
        _draw_text(c, _pt(20), H - _pt(52), "4. Appréciation formateur", size=30, font=FONT_TITLE)
        
        # Récupérer les données d'appréciation
        appreciation = self.ctx.get("appreciation", {})
        
        # Configuration de la grille avec cartes centrées
        card_width = _pt(90)
        card_height = _pt(25)
        spacing_x = _pt(10)
        spacing_y = _pt(8)
        
        # Calculer le centre de la page pour centrer les cartes
        total_width = 2 * card_width + spacing_x  # Largeur totale pour 2 cartes + espacement
        start_x = (W - total_width) / 2  # Centrer horizontalement
        start_y = H - _pt(100)
        
        # Catégories et leurs positions
        categories = [
            ("Accueil", "accueil"),
            ("Logistique des transports", "logistique"), 
            ("Logement", "logement"),
            ("Déroulement général", "deroulement"),
            ("Moyen mis à disposition", "moyens")
        ]
        
        # Générer et positionner les images SVG
        for i, (label, key) in enumerate(categories):
            # Calculer la position (grille 2-2-1 par lignes)
            if i < 2:
                # Première ligne : 2 cartes
                row = 0
                col = i
            elif i < 4:
                # Deuxième ligne : 2 cartes
                row = 1
                col = i - 2
            else:
                # Troisième ligne : 1 carte (centrée)
                row = 2
                col = 0
            
            # Centrer la dernière carte si c'est la seule de sa ligne
            if i == 4:  # Dernière carte
                x = W / 2 - card_width / 2  # Centrer parfaitement la carte seule
            else:
                x = start_x + col * (card_width + spacing_x)
            
            y = start_y - row * (card_height + spacing_y)
            
            # Récupérer la valeur
            value = appreciation.get(key, "")
            print(f"DEBUG - Appréciation {label} ({key}): '{value}'")
            
            # Dessiner directement avec ReportLab
            self._draw_appreciation_card(c, x, y, card_width, card_height, label, value)
        
        # Terminer la page
        c.showPage()
    
    def _draw_appreciation_card(self, c, x, y, width, height, label, value):
        """Dessine une carte d'appréciation directement avec ReportLab."""
        # Convertir la valeur en pourcentage et couleur
        percentage, color_rgb = self._convert_appreciation_to_progress(value)
        
        # Ombre de la carte (décalée)
        shadow_offset = _pt(2)
        c.setFillColorRGB(0.7, 0.7, 0.7)
        c.roundRect(x + shadow_offset, y - shadow_offset, width, height, _pt(4), fill=1, stroke=0)
        
        # Fond de la carte (blanc)
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.setLineWidth(1)
        c.roundRect(x, y, width, height, _pt(4), fill=1, stroke=1)
        
        # Titre de la catégorie (entier et plus visible)
        c.setFont(FONT_TEXT, 16)  # Titre encore plus grand
        c.setFillColorRGB(0, 0, 0)  # Texte noir
        # Ajuster la largeur de la barre pour laisser plus d'espace au titre
        title_width = width - _pt(25)  # Réserver 25pt pour le badge
        c.drawString(x + _pt(3), y + height - _pt(9), label)
        
        # Barre de progression
        bar_width = width - _pt(25)  # Plus d'espace pour le badge
        bar_height_small = _pt(5)  # Barre plus haute
        bar_x = x + _pt(3)
        bar_y = y + _pt(2)
        
        # Fond de la barre (gris clair)
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.roundRect(bar_x, bar_y, bar_width, bar_height_small, _pt(1.5), fill=1, stroke=0)
        
        # Barre de progression colorée
        if percentage > 0:
            progress_width = bar_width * (percentage / 100)
            c.setFillColorRGB(*color_rgb)
            c.roundRect(bar_x, bar_y, progress_width, bar_height_small, _pt(1.5), fill=1, stroke=0)
        
        # Badge de validation encore plus grand (toujours affiché)
        badge_x = x + width - _pt(10)
        badge_y = y + height - _pt(3)
        c.setFillColorRGB(*color_rgb)
        c.circle(badge_x, badge_y, _pt(7), fill=1)  # Badge encore plus grand
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 20)  # Texte encore plus grand
        c.drawString(badge_x - _pt(2), badge_y - _pt(2.5), "✓")
    
    def _convert_appreciation_to_progress(self, value):
        """Convertit une appréciation textuelle en pourcentage et couleur."""
        if not value:
            return 0, (0.8, 0.8, 0.8)  # Gris par défaut
        
        value_lower = value.lower()
        print(f"DEBUG - Conversion appréciation: '{value}' -> '{value_lower}'")
        
        if "passable" in value_lower:
            return 20, (0.9, 0.3, 0.3)  # Rouge
        elif "assez-bien" in value_lower:
            return 40, (0.9, 0.6, 0.2)  # Orange
        elif "tres-bien" in value_lower:
            return 100, (0.3, 0.8, 0.3)  # Vert
        elif "bien" in value_lower:
            return 80, (0.8, 0.8, 0.2)  # Jaune-vert
        else:
            return 0, (0.8, 0.8, 0.8)  # Gris par défaut
    

    def conclusion(self, n):
        """
        Génère la page de conclusion et recommandations.
        
        STRUCTURE :
        - Titre : "Conclusion et recommandations"
        - Paragraphe de conclusion avec retour à la ligne automatique
        - Formatage en paragraphe continu avec wrapper
        
        DONNÉES : self.ctx.get("conclusion", "") - Texte libre
        """
        self._start_landscape(n)
        c, W, H = self.c, self.W, self.H
        
        # Titre principal
        _draw_text(c, _pt(20), H - _pt(52), "Conclusion et recommandations", size=30, font=FONT_TITLE)
        
        # Récupérer le texte de conclusion
        conclusion_text = self.ctx.get("conclusion", "")
        
        if not conclusion_text:
            conclusion_text = """Cette formation a permis d'atteindre les objectifs pédagogiques définis en début de session. Les participants ont démontré une progression significative dans l'acquisition des compétences techniques et méthodologiques.

Les évaluations réalisées montrent une amélioration notable des performances entre les tests d'entrée et de sortie, confirmant l'efficacité du programme de formation. Les apprenants ont particulièrement apprécié la qualité de l'encadrement et la pertinence des supports pédagogiques mis à disposition.

Recommandations :
• Poursuivre le développement des compétences acquises par une mise en pratique régulière
• Organiser des sessions de suivi pour consolider les acquis
• Adapter le contenu selon les retours des participants pour les prochaines sessions

Cette formation constitue une étape importante dans le développement professionnel des participants et contribue à l'amélioration continue des pratiques au sein de l'organisation."""
        
        # Configuration du texte avec wrapper optimisé
        c.setFont(FONT_TEXT, 14)  # Police lisible
        text_width = W - _pt(40)  # Largeur avec marges de 20pt de chaque côté
        y_start = H - _pt(70)     # Position de départ optimisée
        
        # Diviser le texte en paragraphes (séparés par des retours à la ligne)
        paragraphs = conclusion_text.split('\n\n')  # Séparer les paragraphes
        
        y_current = y_start
        
        for paragraph in paragraphs:
            if paragraph.strip():  # Ignorer les paragraphes vides
                # Nettoyer le paragraphe
                paragraph = paragraph.strip()
                
                # Appliquer le wrapper pour le retour automatique à la ligne
                wrapped_lines = _wrap_lines(c, paragraph, text_width, 14, font=FONT_TEXT)
                
                # Dessiner chaque ligne avec le wrapper
                for line in wrapped_lines:
                    if y_current < _pt(50):  # Vérifier si on a encore de la place
                        break
                    c.drawString(_pt(20), y_current, line)  # Marge gauche de 20pt
                    y_current -= _pt(10)  # Espacement compact entre les lignes
                
                # Espacement entre les paragraphes
                y_current -= _pt(8)
        
        c.showPage()

    def attendance(self, n):
        """
        Génère la page des émargements avec images des feuilles de présence.
        
        STRUCTURE :
        - Titre : "Émargements"
        - Images multiples des émargements avec pagination
        - Redimensionnement automatique avec préservation du ratio
        
        DONNÉES : self.ctx.get("attendance_images", []) - Liste d'images
        """
        attendance_images = self.ctx.get("attendance_images", []) or []
        
        if not attendance_images:
            # Aucune image d'émargement disponible
            self._start_landscape(n)
            c, W, H = self.c, self.W, self.H
            _draw_text(c, _pt(20), H - _pt(52), "Émargements", size=30, font=FONT_TITLE)
            c.setFont(FONT_TEXT, 16)
            c.drawString(_pt(20), H - _pt(80), "Aucune image d'émargement disponible")
            c.showPage()
            return
        
        # Traiter chaque image d'émargement
        for i, img_path in enumerate(attendance_images):
            # Convertir le chemin web en chemin disque
            disk_path = _web_to_disk(img_path)
            
            if not (disk_path and os.path.exists(disk_path)):
                print(f"DEBUG - Image d'émargement non trouvée: {img_path}")
                continue
            
            # Créer une nouvelle page pour chaque image
            self._start_landscape(n + i)
            c, W, H = self.c, self.W, self.H
            
            # Titre avec numérotation si plusieurs images
            if len(attendance_images) > 1:
                title = f"Émargements ({i + 1}/{len(attendance_images)})"
            else:
                title = "Émargements"
            
            _draw_text(c, _pt(20), H - _pt(52), title, size=30, font=FONT_TITLE)
            
            # Dessiner l'image avec marges appropriées et bordures
            img_width = W - _pt(40)  # Marges de 20pt de chaque côté
            img_height = H - _pt(90)  # Plus d'espace pour le titre et le footer
            
            # Calculer les dimensions de l'image pour la centrer
            img_x = _pt(20)  # Position X de la bordure
            img_y = _pt(30)  # Position Y de la bordure
            
            # Dessiner la bordure de l'image
            c.setStrokeColorRGB(0.5, 0.5, 0.5)  # Couleur grise pour la bordure
            c.setLineWidth(2)  # Épaisseur de la bordure
            c.rect(img_x, img_y, img_width, img_height, stroke=1, fill=0)
            
            # Dessiner l'image centrée dans le conteneur
            c.drawImage(disk_path, img_x, img_y, 
                       width=img_width, height=img_height,
                    preserveAspectRatio=True, mask='auto', anchor='c')
            
            # Terminer la page pour cette image
            c.showPage()

    def thanks(self, n):
        """
        Génère la page de remerciements (page de fin).
        
        STRUCTURE :
        - Message "Merci" centré en grand (38pt)
        - Signature "Neemba Academy" en dessous (18pt)
        - Style épuré et professionnel
        
        PAGE : Page de clôture du rapport
        """
        self._start_landscape(n)
        W, H = self.W, self.H
        _draw_text(self.c, W/2.0, H/2.0, "Merci", size=38, font=FONT_TITLE, center=True)
        _draw_text(self.c, W/2.0, H/2.0 - _pt(10), "Neemba Academy", size=18, color="#2b2f38", font=FONT_TEXT, center=True)
        self.c.showPage()

    # ---------- Build ----------
    def build(self):
        """
        Construit le rapport PDF complet en générant toutes les pages dans l'ordre.
        Chaque méthode génère une ou plusieurs pages avec un style cohérent.
        PROTECTION : Utilise un verrou pour éviter les conflits entre utilisateurs.
        """
        # Utiliser le verrou de session pour éviter les conflits
        with self.session_lock:
            # Nettoyage automatique des fichiers temporaires anciens
            _cleanup_old_files()
            
            # PAGE 1: COUVERTURE - Page d'accueil avec titre principal et logos
            self.cover()
            
            # Pages suivantes avec style paysage uniforme
            n = 2
            
            # PAGE 2: PRÉSENTATION - Informations client, machine et formateur
            # Contient 4 sous-boxes : photo machine, infos machine, logo client, infos client
            # + Box formateur avec photo et informations détaillées
            self.presentation(n); n += 1
            
            # PAGE 3: SOMMAIRE - Liste des sections du rapport (à puces)
            # Affiche la structure générale du rapport pour navigation
            summary_data = self.ctx.get("summary", [])
            print(f"DEBUG - Sommaire: ctx.get('summary') = {summary_data}")
            print(f"DEBUG - Sommaire: type = {type(summary_data)}, length = {len(summary_data) if summary_data else 0}")
            
            if not summary_data:
                # Données par défaut seulement si aucune donnée du wizard
                summary_data = [
                    "Objectifs",
                    "Contenu & planning",
                    "Évaluation & analyses",
                    "Médiathèque",
                    "Appréciation formateur",
                    "Conclusion",
                    "Émargements"
                ]
                print(f"DEBUG - Sommaire: Utilisation des données par défaut")
            else:
                print(f"DEBUG - Sommaire: Utilisation des données du wizard")
            
            self.list_page("Sommaire", summary_data, n, numbered=True); n += 1
            
            # PAGE 4: OBJECTIFS - Liste numérotée des objectifs de formation
            # Objectifs pédagogiques et résultats attendus de la formation
            objectives_data = self.ctx.get("objectives", [])
            print(f"DEBUG - Objectifs: ctx.get('objectives') = {objectives_data}")
            print(f"DEBUG - Objectifs: type = {type(objectives_data)}, length = {len(objectives_data) if objectives_data else 0}")
            
            if not objectives_data:
                # Données par défaut seulement si aucune donnée du wizard
                objectives_data = [
                    "Objectif 1",
                    "Objectif 2",
                    "Objectif 3",
                    "Objectif 4",
                    "Objectif 5"
                ]
                print(f"DEBUG - Objectifs: Utilisation des données par défaut")
            else:
                print(f"DEBUG - Objectifs: Utilisation des données du wizard")
            
            self.list_page("Objectifs", objectives_data, n, numbered=False); n += 1
            
            # PAGE 5: PLANNING - Tableau détaillé du planning de formation
            # Colonnes : Tâche, Début, Fin, Notes - Planning chronologique
            self.planning(n); n += 1
        
            # PAGES 6-8: ÉVALUATION & ANALYSES - Graphiques et KPIs
            # Page 6: Graphiques de performance et analyses
            # Page 7: KPIs et métriques de formation  
            # Page 8: Analyses approfondies et recommandations
            self.eval_pages(n); n += 3
            
            # PAGE 9: MÉDIATHÈQUE - Galerie d'images de la formation
            # Photos prises pendant la formation avec légendes
            self.media(n); n += 1
            
            # PAGE 10: APPRÉCIATION FORMATEUR - Évaluation par catégories
            # Notes du formateur sur : Accueil, Logement, Moyens, Logistique, Déroulement
            self.appreciation(n); n += 1
            
            # PAGE 11: CONCLUSION - Synthèse et recommandations
            # Conclusion générale de la formation et perspectives d'avenir
            self.conclusion(n); n += 1
            
            # PAGES 12+: ÉMARGEMENTS - Images des feuilles de présence
            # Photos des feuilles d'émargement des participants (une page par image)
            attendance_images = self.ctx.get("attendance_images", []) or []
            if attendance_images:
                self.attendance(n)
                n += len(attendance_images)  # Une page par image d'émargement
            else:
                self.attendance(n)
                n += 1  # Une page même si aucune image
            
            # PAGE 13: REMERCIEMENTS - Page de fin avec remerciements
            # Page de clôture avec message de remerciement
            self.thanks(n)
            
            # Sauvegarde finale du PDF
            self.c.save()
            
            # Nettoyage du verrou de session après génération
            _cleanup_session_lock(self.sid)

def generate_reportlab(sid: str) -> str:
    """Crée le PDF ReportLab pour la session sid et renvoie le chemin disque."""
    if not sid:
        return None
    
    print(f"DEBUG - generate_reportlab() appelée avec sid: {sid}")
    
    session_dir = os.path.join(ROOT, sid)
    os.makedirs(session_dir, exist_ok=True)
    
    # Charger le contexte pour récupérer le nom du client
    ctx = _load_ctx(sid) or {}
    client_name = ctx.get("client", {}).get("name", "")
    
    # Debug pour voir les données reçues
    print(f"DEBUG - Contexte chargé: {ctx}")
    print(f"DEBUG - Client: {ctx.get('client', {})}")
    print(f"DEBUG - Nom du client: '{client_name}'")
    
    
    
    # Générer un timestamp pour éviter les conflits
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Générer le nom du fichier avec le nom du client et timestamp
    if client_name:
        # Nettoyer le nom du client pour le nom de fichier
        clean_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '-', '_')).strip()
        clean_name = clean_name.replace(' ', '_').lower()
        filename = f"rapport_formation_{clean_name}_{timestamp}.pdf"
    else:
        filename = f"rapport_formation_{timestamp}.pdf"
    
    out_pdf = os.path.join(session_dir, filename)
    print(f"DEBUG - Nom du fichier généré: {filename}")
    print(f"DEBUG - Chemin complet: {out_pdf}")
    
    try:
        print(f"DEBUG - Début de la génération du PDF...")
        
        # Vérifier la mémoire disponible (temporairement désactivé)
        try:
            import psutil
            memory_info = psutil.virtual_memory()
            print(f"DEBUG - Mémoire disponible: {memory_info.available / 1024 / 1024:.1f} MB")
            print(f"DEBUG - Mémoire utilisée: {memory_info.percent}%")
        except ImportError:
            print(f"DEBUG - psutil non disponible, vérification mémoire ignorée")
        
        # Vérifier que les fichiers d'images existent
        print(f"DEBUG - Vérification des fichiers d'images...")
        logo_path = ctx.get("client", {}).get("logo_path")
        if logo_path:
            disk_path = _web_to_disk(logo_path)
            print(f"DEBUG - Logo path: {logo_path} -> {disk_path}, existe: {os.path.exists(disk_path)}")
        
        machine_photo = ctx.get("machine", {}).get("photo_path")
        if machine_photo:
            disk_path = _web_to_disk(machine_photo)
            print(f"DEBUG - Machine photo: {machine_photo} -> {disk_path}, existe: {os.path.exists(disk_path)}")
        
        trainer_photo = ctx.get("trainer", {}).get("photo_path")
        if trainer_photo:
            disk_path = _web_to_disk(trainer_photo)
            print(f"DEBUG - Trainer photo: {trainer_photo} -> {disk_path}, existe: {os.path.exists(disk_path)}")
        
        # Forcer le garbage collection avant la génération
        import gc
        gc.collect()
        print(f"DEBUG - Garbage collection effectué")
        
        NembaReportLab(sid, out_pdf).build()
        print(f"DEBUG - PDF généré avec succès!")
        
        # Vérifier que le fichier existe
        if os.path.exists(out_pdf):
            file_size = os.path.getsize(out_pdf)
            print(f"DEBUG - Fichier PDF créé: {out_pdf}, taille: {file_size} bytes")
        else:
            print(f"DEBUG - ERREUR: Fichier PDF non créé!")
            
    except Exception as e:
        print(f"DEBUG - ERREUR lors de la génération du PDF: {e}")
        import traceback
        traceback.print_exc()
        raise e
    
    return out_pdf
