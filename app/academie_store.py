"""
Stockage léger (fichiers JSON) pour le module Académie :
planning annuel, fiches d'évaluation, questionnaires QR et réponses,
plans d'action mensuels.

Suit le même principe que app/storage.py (pas de base de données),
mais les fichiers vivent hors de app/static pour ne jamais être exposés
publiquement via le mount StaticFiles (les réponses/questionnaires
contiennent des données qui ne doivent pas être téléchargeables).
"""
import json
import uuid
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from threading import Lock
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent / "data" / "academie"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()

_FILES = {
    "planning": _DATA_DIR / "planning.json",
    "evaluations": _DATA_DIR / "evaluations.json",
    "questionnaires": _DATA_DIR / "questionnaires.json",
    "reponses": _DATA_DIR / "reponses.json",
    "plans_action": _DATA_DIR / "plans_action.json",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(name: str) -> list:
    p = _FILES[name]
    if not p.exists():
        return []
    try:
        raw = p.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(name: str, items: list) -> None:
    p = _FILES[name]
    with _LOCK:
        p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


# ──────────────────────────────────────────────────────────────────────────
# Planning annuel de formation
# ──────────────────────────────────────────────────────────────────────────

def list_planning() -> list:
    return sorted(_load("planning"), key=lambda x: x.get("date_debut") or "")


def get_planning(item_id: str) -> Optional[dict]:
    return next((x for x in _load("planning") if x.get("id") == item_id), None)


def save_planning_item(data: dict) -> dict:
    items = _load("planning")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("planning", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("planning", items)
    return data


def delete_planning_item(item_id: str) -> None:
    items = [x for x in _load("planning") if x.get("id") != item_id]
    _save("planning", items)


# ──────────────────────────────────────────────────────────────────────────
# Vue Gantt du planning annuel (détection des chevauchements de sessions)
# ──────────────────────────────────────────────────────────────────────────

_MOIS_ABBR = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]

_GRANULARITES = [
    ("semaine", "Semaine"),
    ("mois", "Mois"),
    ("trimestre", "Trimestre"),
    ("semestre", "Semestre"),
    ("annee", "Année"),
]

_STATUT_META = {
    "planifie": {"label": "Planifié", "color": "#9aa0a6"},
    "confirme": {"label": "Confirmé", "color": "#378ADD"},
    "realise": {"label": "Réalisé", "color": "#1D9E75"},
    "annule": {"label": "Annulé", "color": "#b0413e"},
}
_RETARD_COLOR = "#e24b4a"

_GROUPES_DEF = [
    ("client", "Sessions client", "#0b2c6e"),
    ("interne", "Sessions internes", "#4a4232"),
]


def _parse_date(s: Optional[str]):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _fmt_range(d1, d2) -> str:
    if d1 == d2:
        return d1.strftime("%d/%m/%Y")
    return f"{d1.strftime('%d/%m/%Y')} → {d2.strftime('%d/%m/%Y')}"


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, 1)


def _week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _periods_for_granularite(granularite: str, today: date) -> list:
    """Retourne la liste des périodes (start, end, label) affichées dans la
    fenêtre visible du Gantt, positionnée autour d'aujourd'hui."""
    if granularite == "semaine":
        start0 = _week_monday(today)
        past, future = 4, 8
        periods = []
        for i in range(-past, future + 1):
            p_start = start0 + timedelta(weeks=i)
            p_end = p_start + timedelta(days=6)
            periods.append((p_start, p_end, f"S{p_start.isocalendar()[1]}"))
        return periods

    months_per, past, future = {
        "mois": (1, 2, 5),
        "trimestre": (3, 2, 3),
        "semestre": (6, 1, 2),
        "annee": (12, 1, 2),
    }.get(granularite, (3, 2, 3))

    if months_per == 1:
        cur_start_month = today.month
    else:
        cur_start_month = ((today.month - 1) // months_per) * months_per + 1
    cur_start = date(today.year, cur_start_month, 1)

    periods = []
    for i in range(-past, future + 1):
        p_start = _add_months(cur_start, i * months_per)
        p_end = _add_months(p_start, months_per) - timedelta(days=1)
        if months_per == 1:
            label = f"{_MOIS_ABBR[p_start.month]} {p_start.year % 100:02d}"
        elif months_per == 3:
            label = f"T{(p_start.month - 1) // 3 + 1} {p_start.year}"
        elif months_per == 6:
            label = f"S{(p_start.month - 1) // 6 + 1} {p_start.year}"
        else:
            label = f"{p_start.year}"
        periods.append((p_start, p_end, label))
    return periods


def compute_gantt(items: list, granularite: str = "trimestre", today: Optional[date] = None) -> dict:
    """
    Construit les données de la vue Gantt du planning annuel : sessions
    groupées par type (client / interne), positionnées sur une frise dont
    l'échelle (semaine / mois / trimestre / semestre / année) est réglable,
    avec ligne "aujourd'hui", statut coloré par session, détection des
    sessions en retard et détection explicite des chevauchements de dates.
    """
    if today is None:
        today = datetime.now().date()

    # 1) Sessions datées, normalisées (date_fin >= date_debut)
    dated = []
    for it in items:
        d1 = _parse_date(it.get("date_debut"))
        if not d1:
            continue
        d2 = _parse_date(it.get("date_fin")) or d1
        if d2 < d1:
            d1, d2 = d2, d1
        dated.append({**it, "_start": d1, "_end": d2})

    # 2) Chevauchements : calculés sur l'ensemble des sessions datées, quelle
    #    que soit la fenêtre affichée, pour ne jamais manquer un conflit.
    conflits = []
    conflict_map: dict = {}
    for i in range(len(dated)):
        for j in range(i + 1, len(dated)):
            a, b = dated[i], dated[j]
            if a["_start"] <= b["_end"] and b["_start"] <= a["_end"]:
                conflict_map.setdefault(a["id"], []).append(b.get("titre") or "Sans titre")
                conflict_map.setdefault(b["id"], []).append(a.get("titre") or "Sans titre")
                conflits.append({
                    "a_titre": a.get("titre") or "Sans titre",
                    "a_dates": _fmt_range(a["_start"], a["_end"]),
                    "b_titre": b.get("titre") or "Sans titre",
                    "b_dates": _fmt_range(b["_start"], b["_end"]),
                })

    # 3) Fenêtre temporelle + colonnes selon la granularité choisie
    if granularite not in {g[0] for g in _GRANULARITES}:
        granularite = "trimestre"
    periods_raw = _periods_for_granularite(granularite, today)
    window_start, window_end = periods_raw[0][0], periods_raw[-1][1]
    total_days = (window_end - window_start).days + 1

    periodes = []
    for p_start, p_end, label in periods_raw:
        left = (p_start - window_start).days / total_days * 100
        width = ((p_end - p_start).days + 1) / total_days * 100
        periodes.append({"label": label, "left_pct": round(left, 3), "width_pct": round(width, 3)})

    today_left_pct = None
    if window_start <= today <= window_end:
        today_left_pct = round((today - window_start).days / total_days * 100, 3)

    # 4) Lignes visibles dans la fenêtre, groupées par type de session
    groupes = []
    for key, label, dot_color in _GROUPES_DEF:
        subset = sorted(
            (
                it for it in dated
                if (it.get("type_session") or "client") == key
                and it["_end"] >= window_start and it["_start"] <= window_end
            ),
            key=lambda x: x["_start"],
        )
        rows = []
        for it in subset:
            clamped_start = max(it["_start"], window_start)
            clamped_end = min(it["_end"], window_end)
            left_pct = (clamped_start - window_start).days / total_days * 100
            width_pct = max(((clamped_end - clamped_start).days + 1) / total_days * 100, 0.5)
            statut = it.get("statut") or "planifie"
            en_retard = it["_end"] < today and statut not in ("realise", "annule")
            meta = _STATUT_META.get(statut, _STATUT_META["planifie"])
            item_id = it.get("id")
            rows.append({
                "id": item_id,
                "titre": it.get("titre") or "Sans titre",
                "formateur": it.get("formateur") or "",
                "statut": statut,
                "statut_label": "En retard" if en_retard else meta["label"],
                "statut_color": _RETARD_COLOR if en_retard else meta["color"],
                "en_retard": en_retard,
                "date_debut": it["_start"].isoformat(),
                "date_fin": it["_end"].isoformat(),
                "left_pct": round(left_pct, 3),
                "width_pct": round(width_pct, 3),
                "conflit": item_id in conflict_map,
                "conflit_avec": conflict_map.get(item_id, []),
            })
        groupes.append({"key": key, "label": label, "dot_color": dot_color, "sessions": rows, "count": len(rows)})

    return {
        "granularite": granularite,
        "granularites": _GRANULARITES,
        "periodes": periodes,
        "today_left_pct": today_left_pct,
        "groupes": groupes,
        "conflits": conflits,
        "total_conflits": len(conflits),
        "total_sessions": len(dated),
    }


# ──────────────────────────────────────────────────────────────────────────
# Fiches d'évaluation de la formation (côté formateur)
# ──────────────────────────────────────────────────────────────────────────

def list_evaluations() -> list:
    return sorted(_load("evaluations"), key=lambda x: x.get("date") or "", reverse=True)


def get_evaluation(item_id: str) -> Optional[dict]:
    return next((x for x in _load("evaluations") if x.get("id") == item_id), None)


def save_evaluation(data: dict) -> dict:
    items = _load("evaluations")
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save("evaluations", items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now()}
    items.append(data)
    _save("evaluations", items)
    return data


def delete_evaluation(item_id: str) -> None:
    items = [x for x in _load("evaluations") if x.get("id") != item_id]
    _save("evaluations", items)


# ──────────────────────────────────────────────────────────────────────────
# Questionnaires QR code (fin de formation) — config
# ──────────────────────────────────────────────────────────────────────────

def list_questionnaires() -> list:
    return sorted(_load("questionnaires"), key=lambda x: x.get("created_at") or "", reverse=True)


def get_questionnaire(token: str) -> Optional[dict]:
    return next((x for x in _load("questionnaires") if x.get("token") == token), None)


def create_questionnaire(data: dict) -> dict:
    items = _load("questionnaires")
    data = {**data, "token": uuid.uuid4().hex[:8], "actif": True, "created_at": _now()}
    items.append(data)
    _save("questionnaires", items)
    return data


def set_questionnaire_actif(token: str, actif: bool) -> None:
    items = _load("questionnaires")
    for it in items:
        if it.get("token") == token:
            it["actif"] = actif
    _save("questionnaires", items)


def delete_questionnaire(token: str) -> None:
    items = [x for x in _load("questionnaires") if x.get("token") != token]
    _save("questionnaires", items)
    reponses = [x for x in _load("reponses") if x.get("token") != token]
    _save("reponses", reponses)


# ──────────────────────────────────────────────────────────────────────────
# Réponses au questionnaire (soumises par les stagiaires, anonymes)
# ──────────────────────────────────────────────────────────────────────────

def add_reponse(token: str, data: dict) -> dict:
    items = _load("reponses")
    data = {**data, "id": _new_id(), "token": token, "date": _now()}
    items.append(data)
    _save("reponses", items)
    return data


def list_reponses(token: Optional[str] = None) -> list:
    items = _load("reponses")
    if token:
        items = [x for x in items if x.get("token") == token]
    return sorted(items, key=lambda x: x.get("date") or "", reverse=True)


# ──────────────────────────────────────────────────────────────────────────
# Plans d'action mensuels (propositions d'amélioration issues des stats QR)
# ──────────────────────────────────────────────────────────────────────────

def get_plan_action(mois: str) -> Optional[dict]:
    return next((x for x in _load("plans_action") if x.get("mois") == mois), None)


def save_plan_action(mois: str, texte: str) -> dict:
    items = _load("plans_action")
    for i, it in enumerate(items):
        if it.get("mois") == mois:
            items[i] = {"mois": mois, "texte": texte, "updated_at": _now()}
            _save("plans_action", items)
            return items[i]
    entry = {"mois": mois, "texte": texte, "updated_at": _now()}
    items.append(entry)
    _save("plans_action", items)
    return entry


def list_plans_action() -> list:
    return sorted(_load("plans_action"), key=lambda x: x.get("mois") or "", reverse=True)
