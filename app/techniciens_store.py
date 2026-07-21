"""
Module Techniciens — remplace intégralement l'ancienne logique "maison"
(fiche simplifiée + test de recrutement + tâches d'intégration + suivi
périodique), qui existait en attendant que le fichier Excel "Suivi du
personnel" / "Suivi du tutorat" soit finalisé.

Désormais, un technicien EST une fiche au format du fichier Excel
"01_Suivi_du_personnel" (mêmes champs, mêmes libellés — cf. FIELD_GROUPS
ci-dessous), enrichie de :
- son avancement formations/DPC (onglet "Base 2" du même classeur) ;
- sa progression OJT / compétences (fichier "02_Suivi du tutorat").

Le fichier Excel est abandonné : toute création, modification ou suppression
se fait maintenant directement dans l'application, qui est la seule source
de vérité. Stockage : fichiers JSON (pas de base de données), comme le reste
de l'application.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent / "data" / "techniciens"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_TECHNICIENS_FILE = _DATA_DIR / "techniciens.json"
_REFERENTIEL_FILE = _DATA_DIR / "referentiel_competences.json"

_LOCK = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _load(path: Path) -> list:
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(path: Path, items) -> None:
    with _LOCK:
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────
# Champs de la fiche technicien (identiques aux colonnes du fichier Excel
# "Suivi du personnel", onglet "Base 1"), regroupés pour l'affichage du
# formulaire.
# ──────────────────────────────────────────────────────────────────────────

# Les intitulés de groupes ci-dessous reprennent volontairement les libellés
# de sections utilisés dans l'onglet "Base 1" du fichier Excel (ligne 2 :
# "Données RH" / "Données Atelier" / "Données CDF" / "Formation année en
# cours") afin qu'on retrouve exactement le même repère visuel qu'en Excel.
FIELD_GROUPS = [
    ("Identité", [
        "Code société", "User Id", "Mtle", "Nom / Prénom", "Statut", "Age",
        "Date de Naissance", "Niveau  d'étude", "Filière", "Adresse mail",
    ]),
    ("Données RH", [
        "Sta9", "Sta9 Niveau", "Poste harmonisé Actuel", "Poste harmonisé Cible",
        "Poste RH", "Service", "Type Contrat", "Ancienneté", "Date entrée",
        "Année entrée", "Date de sortie", "CWSId2", "Code CAT2", "Groupe",
        "Raison de la démission 1", "Raison de la démission 2",
    ]),
    ("Données Atelier", [
        "Niveau Atelier actuel", "Niveau Atelier Cible", "Niveau fin de cursus",
        "Pris en compte dans la grille TCDP",
    ]),
    ("Données CDF", [
        "Niveau CDF validé", "Niveau CDF en cours", "Certification Expert",
        "Certification Advanced", "Certification Foundational",
        "Certification validée", "Certification en cours", "Inscrit dans DPC",
        "Programme 1", "Programme 2", "Programme 3",
    ]),
    ("Formation année en cours", [
        "Form prévue", "Form réalisée", "A un ILP",
        "Form Prévue (Nb Sem)", "Form Réalisée (Nb Sem)",
    ]),
    ("Historique niveau atelier (2021-2026)", [
        "Niveau atelier 2021", "Niveau atelier 2022", "Niveau atelier 2023",
        "Niveau Atelier 2024", "Niveau Atelier 2025", "Niveau Atelier 2026",
    ]),
    ("Historique formations (2015-2025)", [
        "Form 2015", "Form 2016", "Form 2017", "Form 2018", "Form 2019",
        "Form 2020", "Form 2021", "Form 2022", "Form 2023", "Form 2024", "Form 2025",
    ]),
    ("Volume d'heures formation (2015-2025)", [
        "Form 2015 Volume d'heures", "Form 2016 Volume d'heures",
        "Form 2017 Volume d'heures", "Form 2018 Volume d'heures",
        "Form 2019 Volume d'heures", "Form 2020 Volume d'heures",
        "Form 2021 Volume d'heures", "Form 2022 Volume d'heures",
        "Form 2023 Volume d'heures", "Form 2024 Volume d'heure",
        "Form 2025 Volume d'heure",
    ]),
    ("Formation 2026 (prévue / réalisée)", [
        "Form 2026 prévu 1", "Form 2026 prévu 2", "Form 2026 prévu 3",
        "Form 2026 prévu 4", "Form 2026 prévu 5", "Form 2026 prévu 6",
        "Form 2026 prévu (Nb Sem)", "Note 2026", "Form 2026 réalisé",
        "Form 2026 réalisé (Nb Sem)", "Form 2026 non réalisé",
        "Form 2026 non réalisé (Nb Sem)",
    ]),
    ("Modules & certifications spécifiques", [
        "Elec. Troubles 52647", "P. Link 42416", "AFA1 26213", "AFA2 26214",
        "Certif Adv Heavy 54618", "Machine Perf I-VXGN71",
        "Certif Expert Heavy 42022", "EPG2 26240", "EPG3 26236",
        "Engine troubles 53054", "D3500 Master meca 26247",
        "C175 Engine training 32302", "Elec. Troubles 2 44819",
        "Digital Com Troubles 55817", "Certif  Adv EPG 52968",
        "EMCP 4.3/4.4 40004", "Appli & Install 41761",
        "Certif Expert EPG 26249", "MEST 40688", "Certif Adv Marine 45643",
        "Marine Install & Diag 41963", "MCS 45257", "Certif Expert Marine 43831",
        "CIAP 40118", "Boot Camp 44916",
    ]),
    ("Volumes d'heures modules spécifiques", [
        "Elec. Troubles Volume d'heures", "P. Link  Volume d'heures",
        "AFA1  Volume d'heures", "AFA2 Volume d'heures",
        "Certif Adv Heavy Volume d'heures", "EPG2 Volume d'heures",
        "EPG3 Volume d'heures",
    ]),
    ("Divers / évaluations", [
        "Engine Trouble", "Powertrain Trouble", "Hydrau Trouble", "ALL 1",
        "CKECK_P2", "CKECK_P1", "CKECK_P3", "Check Ass theo", "Nb Ass theo",
        "Libre 1", "Libre 2", "Libre 3", "Libre 4",
    ]),
]

ALL_FIELDS = [f for _, fields in FIELD_GROUPS for f in fields]

# Champs "Base 2" (avancement formations / DPC) rattachés à un technicien
AVANCEMENT_FIELDS = [
    "Programme", "Identifiant dans DPC", "Identifiant programme CAT",
    "Compil extraction", "Niveau", "A prendre en compte",
    "Programme pris en compte", "Avancement Curriculum",
    "1. Fundamental English", "2. ILT Neemba",
    "3. Certification interne ou CAT", "4. Avancement DPC2",
    "Extraction résultats de DPC", "Commentaire",
]


# ──────────────────────────────────────────────────────────────────────────
# CRUD technicien
# ──────────────────────────────────────────────────────────────────────────

def list_techniciens() -> list:
    items = _load(_TECHNICIENS_FILE)
    return sorted(items, key=lambda x: (x.get("Nom / Prénom") or "").lower())


def get_technicien(item_id: str) -> Optional[dict]:
    return next((x for x in _load(_TECHNICIENS_FILE) if x.get("id") == item_id), None)


def save_technicien(data: dict) -> dict:
    """Crée ou met à jour un technicien. `data` peut contenir n'importe lequel
    des champs de ALL_FIELDS (les champs absents restent inchangés en cas de
    mise à jour partielle)."""
    items = _load(_TECHNICIENS_FILE)
    item_id = data.get("id")
    if item_id:
        for i, it in enumerate(items):
            if it.get("id") == item_id:
                merged = {**it, **data, "updated_at": _now()}
                items[i] = merged
                _save(_TECHNICIENS_FILE, items)
                return merged
    data = {**data, "id": _new_id(), "created_at": _now(),
            "avancement": data.get("avancement", []),
            "competences": data.get("competences", {}),
            "ojt_niveaux": data.get("ojt_niveaux", {})}
    items.append(data)
    _save(_TECHNICIENS_FILE, items)
    return data


def delete_technicien(item_id: str) -> None:
    _save(_TECHNICIENS_FILE, [x for x in _load(_TECHNICIENS_FILE) if x.get("id") != item_id])


def search_techniciens(query: str, limit: int = 30) -> list:
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    out = []
    for t in list_techniciens():
        if q in (t.get("Nom / Prénom") or "").lower() or q in str(t.get("Mtle") or "").lower():
            out.append(t)
            if len(out) >= limit:
                break
    return out


# ──────────────────────────────────────────────────────────────────────────
# Avancement formations / DPC (ex "Base 2"), rattaché à un technicien
# ──────────────────────────────────────────────────────────────────────────

def save_avancement(technicien_id: str, data: dict) -> Optional[dict]:
    items = _load(_TECHNICIENS_FILE)
    for i, it in enumerate(items):
        if it.get("id") != technicien_id:
            continue
        avancement = it.get("avancement", [])
        entry_id = data.get("id")
        if entry_id:
            for j, a in enumerate(avancement):
                if a.get("id") == entry_id:
                    avancement[j] = {**a, **data}
                    break
        else:
            data = {**data, "id": _new_id()}
            avancement.append(data)
        it["avancement"] = avancement
        it["updated_at"] = _now()
        items[i] = it
        _save(_TECHNICIENS_FILE, items)
        return it
    return None


def delete_avancement(technicien_id: str, avancement_id: str) -> None:
    items = _load(_TECHNICIENS_FILE)
    for i, it in enumerate(items):
        if it.get("id") == technicien_id:
            it["avancement"] = [a for a in it.get("avancement", []) if a.get("id") != avancement_id]
            items[i] = it
            _save(_TECHNICIENS_FILE, items)
            return


# ──────────────────────────────────────────────────────────────────────────
# Compétences OJT (fichier tutorat), rattachées à un technicien
# ──────────────────────────────────────────────────────────────────────────

def save_competence(technicien_id: str, code: str, valeur) -> Optional[dict]:
    if not code:
        return None
    items = _load(_TECHNICIENS_FILE)
    for i, it in enumerate(items):
        if it.get("id") != technicien_id:
            continue
        competences = it.get("competences", {})
        if valeur in (None, ""):
            competences.pop(code, None)
        else:
            competences[code] = valeur
        it["competences"] = competences
        it["updated_at"] = _now()
        items[i] = it
        _save(_TECHNICIENS_FILE, items)
        return it
    return None


def delete_competence(technicien_id: str, code: str) -> None:
    save_competence(technicien_id, code, None)


# ──────────────────────────────────────────────────────────────────────────
# Référentiel de compétences (fichier tutorat) — édité dans l'application
# ──────────────────────────────────────────────────────────────────────────

def list_referentiel() -> list:
    return _load(_REFERENTIEL_FILE)


def get_referentiel_by_code() -> dict:
    return {r.get("Code compétence"): r for r in list_referentiel() if r.get("Code compétence")}


def save_competence_referentiel(data: dict) -> dict:
    items = _load(_REFERENTIEL_FILE)
    code = data.get("Code compétence")
    for i, it in enumerate(items):
        if it.get("Code compétence") == code:
            items[i] = {**it, **data}
            _save(_REFERENTIEL_FILE, items)
            return items[i]
    items.append(data)
    _save(_REFERENTIEL_FILE, items)
    return data


def delete_competence_referentiel(code: str) -> None:
    _save(_REFERENTIEL_FILE, [r for r in _load(_REFERENTIEL_FILE) if r.get("Code compétence") != code])
