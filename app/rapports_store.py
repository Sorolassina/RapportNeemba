"""
Rapports & Pilotage : agrège les données des autres modules (Académie,
Techniciens, Terrain & SAV, Ressources) pour produire un rapport mensuel
d'activités, et stocke la synthèse narrative éditable par mois.

Ne duplique aucune donnée : les KPI sont recalculés à la volée à partir
des stores existants à chaque consultation.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from app import academie_store, ressources_store, techniciens_store, terrain_store

_DATA_DIR = Path(__file__).resolve().parent / "data" / "rapports"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()
_FILE = _DATA_DIR / "syntheses_mensuelles.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> list:
    if not _FILE.exists():
        return []
    try:
        raw = _FILE.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: list) -> None:
    with _LOCK:
        _FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def get_synthese(mois: str) -> Optional[dict]:
    return next((x for x in _load() if x.get("mois") == mois), None)


def save_synthese(mois: str, faits_marquants: str, actions_prochain_mois: str) -> dict:
    items = _load()
    for i, it in enumerate(items):
        if it.get("mois") == mois:
            items[i] = {
                "mois": mois, "faits_marquants": faits_marquants,
                "actions_prochain_mois": actions_prochain_mois, "updated_at": _now(),
            }
            _save(items)
            return items[i]
    entry = {
        "mois": mois, "faits_marquants": faits_marquants,
        "actions_prochain_mois": actions_prochain_mois, "updated_at": _now(),
    }
    items.append(entry)
    _save(items)
    return entry


def list_syntheses() -> list:
    return sorted(_load(), key=lambda x: x.get("mois") or "", reverse=True)


def _in_month(date_str: Optional[str], mois: str) -> bool:
    return bool(date_str) and date_str[:7] == mois


def _qr_satisfaction(reponses: list) -> int:
    good, total = 0, 0
    for r in reponses:
        for field in ("note_contenu", "note_pedagogie", "note_logistique"):
            v = r.get(field)
            if v:
                total += 1
                if v in ("bien", "tres-bien"):
                    good += 1
    return round(good / total * 100) if total else 0


def get_monthly_activity(mois: str) -> dict:
    """Agrège toutes les données du mois (format 'YYYY-MM') pour le rapport."""

    planning = academie_store.list_planning()
    sessions_mois = [p for p in planning if _in_month(p.get("date_debut"), mois)]
    sessions_realisees = [p for p in sessions_mois if p.get("statut") == "realise"]
    sessions_client = [p for p in sessions_mois if p.get("type_session") == "client"]
    sessions_interne = [p for p in sessions_mois if p.get("type_session") == "interne"]
    try:
        participants_total = sum(int(p.get("participants_prevus") or 0) for p in sessions_mois)
    except (TypeError, ValueError):
        participants_total = 0

    evaluations_mois = [e for e in academie_store.list_evaluations() if _in_month(e.get("date"), mois)]
    reponses_mois = [r for r in academie_store.list_reponses() if _in_month(r.get("date"), mois)]
    questionnaires_mois = [
        q for q in academie_store.list_questionnaires() if _in_month(q.get("created_at"), mois)
    ]

    techniciens = techniciens_store.list_techniciens()
    tech_nouveaux = [t for t in techniciens if _in_month(t.get("created_at"), mois)]
    suivis_mois = [s for s in techniciens_store.list_suivis() if _in_month(s.get("date"), mois)]
    tests_mois = [t for t in techniciens_store.list_tests() if _in_month(t.get("date"), mois)]

    depannages = terrain_store.list_depannages()
    depannages_mois = [d for d in depannages if _in_month(d.get("date"), mois)]
    depannages_formation = [d for d in depannages_mois if d.get("necessite_formation")]
    audits_mois = [a for a in terrain_store.list_audits() if _in_month(a.get("date_appel"), mois)]

    ressources_mois = [r for r in ressources_store.list_ressources() if _in_month(r.get("created_at"), mois)]

    return {
        "mois": mois,
        "academie": {
            "sessions_total": len(sessions_mois),
            "sessions_realisees": len(sessions_realisees),
            "sessions_client": len(sessions_client),
            "sessions_interne": len(sessions_interne),
            "participants_total": participants_total,
            "evaluations": len(evaluations_mois),
            "questionnaires_crees": len(questionnaires_mois),
            "reponses_qr": len(reponses_mois),
            "taux_satisfaction": _qr_satisfaction(reponses_mois),
            "sessions": sessions_mois,
        },
        "techniciens": {
            "nouveaux": len(tech_nouveaux),
            "suivis_realises": len(suivis_mois),
            "tests_recrutement": len(tests_mois),
            "liste_nouveaux": tech_nouveaux,
        },
        "terrain": {
            "depannages": len(depannages_mois),
            "depannages_formation": len(depannages_formation),
            "audits": len(audits_mois),
            "liste_depannages": depannages_mois,
            "liste_audits": audits_mois,
        },
        "ressources": {
            "ajoutees": len(ressources_mois),
            "liste": ressources_mois,
        },
    }
