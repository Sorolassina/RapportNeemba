"""
Tableau de bord : vue d'ensemble en direct de l'activité de LiuGong Academy.

Contrairement à l'ancien tableau de bord (iframe Power BI externe), ce module
recalcule tous les indicateurs et séries de graphiques à la volée à partir
des stores existants (Académie, Techniciens, Terrain & SAV, Ressources).
Aucune donnée n'est dupliquée ni mise en cache.
"""
from collections import defaultdict
from datetime import datetime
from typing import Optional

from app import academie_store, ressources_store, techniciens_store, terrain_store

SYSTEME_LABELS = {
    "hydraulique": "Hydraulique",
    "moteur": "Moteur",
    "electrique": "Électrique",
    "transmission": "Transmission",
    "train_roulement": "Train roulant",
    "climatisation": "Climatisation",
    "autre": "Autre",
    "Non renseigné": "Non renseigné",
}

STATUT_TECH_LABELS = [
    ("candidat", "Candidat"),
    ("en_integration", "En intégration"),
    ("actif", "Actif"),
    ("inactif", "Inactif"),
    ("sorti", "Sorti"),
]

NOTE_FIELDS = ("note_contenu", "note_pedagogie", "note_logistique")


def _mois_range(n: int) -> list:
    """Les n derniers mois (format 'YYYY-MM'), du plus ancien au plus récent."""
    today = datetime.now()
    y, m = today.year, today.month
    mois = []
    for _ in range(n):
        mois.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(mois))


def _mois_label(mois: str) -> str:
    noms = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
    try:
        y, m = mois.split("-")
        return f"{noms[int(m)]} {y[2:]}"
    except (ValueError, IndexError):
        return mois


def _taux_satisfaction(reponses: list) -> int:
    good, total = 0, 0
    for r in reponses:
        for field in NOTE_FIELDS:
            v = r.get(field)
            if v:
                total += 1
                if v in ("bien", "tres-bien"):
                    good += 1
    return round(good / total * 100) if total else 0


def get_dashboard_data() -> dict:
    now_mois = datetime.now().strftime("%Y-%m")

    # ---------------- Académie ----------------
    planning = academie_store.list_planning()
    sessions_realisees = [p for p in planning if p.get("statut") == "realise"]
    try:
        participants_total = sum(int(p.get("participants_prevus") or 0) for p in sessions_realisees)
    except (TypeError, ValueError):
        participants_total = 0
    sessions_client = len([p for p in sessions_realisees if p.get("type_session") == "client"])
    sessions_interne = len([p for p in sessions_realisees if p.get("type_session") == "interne"])
    sessions_a_venir = len([p for p in planning if p.get("statut") in ("planifie", "confirme")])

    reponses = academie_store.list_reponses()
    taux_satisfaction = _taux_satisfaction(reponses)

    # ---------------- Techniciens ----------------
    techniciens = techniciens_store.list_techniciens()
    tech_par_statut: dict = defaultdict(int)
    for t in techniciens:
        tech_par_statut[t.get("statut") or "candidat"] += 1
    tech_nouveaux_mois = len([t for t in techniciens if (t.get("created_at") or "")[:7] == now_mois])

    # ---------------- Terrain & SAV ----------------
    depannages = terrain_store.list_depannages()
    depannages_formation = len([d for d in depannages if d.get("necessite_formation")])
    audits = terrain_store.list_audits()
    repartition_pannes_raw = terrain_store.repartition_pannes(depannages)[:6]
    repartition_pannes = [
        {"label": SYSTEME_LABELS.get(r["systeme"], r["systeme"]), "nb": r["nb"], "pct": r["pct"]}
        for r in repartition_pannes_raw
    ]

    # ---------------- Ressources ----------------
    ressources = ressources_store.list_ressources()
    repartition_ressources_raw = ressources_store.repartition_categories(ressources)
    repartition_ressources = [
        {"label": r["label"], "nb": r["nb"]} for r in repartition_ressources_raw
    ]

    # ---------------- Tendance 6 derniers mois ----------------
    mois_list = _mois_range(6)
    trend = []
    for mois in mois_list:
        sess_m = [p for p in sessions_realisees if (p.get("date_debut") or "")[:7] == mois]
        try:
            part_m = sum(int(p.get("participants_prevus") or 0) for p in sess_m)
        except (TypeError, ValueError):
            part_m = 0
        rep_m = [r for r in reponses if (r.get("date") or "")[:7] == mois]
        trend.append({
            "mois": mois,
            "label": _mois_label(mois),
            "sessions": len(sess_m),
            "participants": part_m,
            "satisfaction": _taux_satisfaction(rep_m),
        })

    return {
        "kpi": {
            "sessions_realisees": len(sessions_realisees),
            "sessions_a_venir": sessions_a_venir,
            "participants_total": participants_total,
            "sessions_client": sessions_client,
            "sessions_interne": sessions_interne,
            "taux_satisfaction": taux_satisfaction,
            "techniciens_total": len(techniciens),
            "techniciens_actifs": tech_par_statut.get("actif", 0),
            "techniciens_en_integration": tech_par_statut.get("en_integration", 0),
            "techniciens_nouveaux_mois": tech_nouveaux_mois,
            "depannages_total": len(depannages),
            "depannages_formation": depannages_formation,
            "audits_total": len(audits),
            "ressources_total": len(ressources),
        },
        "tech_par_statut": [
            {"label": label, "nb": tech_par_statut.get(s, 0)} for s, label in STATUT_TECH_LABELS
        ],
        "repartition_pannes": repartition_pannes,
        "repartition_ressources": repartition_ressources,
        "trend": trend,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
