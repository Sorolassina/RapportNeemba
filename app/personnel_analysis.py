"""
Recalcule en Python les indicateurs que le classeur "01_Suivi_du_personnel"
obtenait via des onglets de calcul/pivot (TCD1, TCD2, Analyse, Analyse 2026,
Objectif, Cap&Cap...), à partir des onglets SOURCES importés dans
app/personnel_store.py.

Objectif : ne pas recopier des chiffres figés, mais reproduire la même
logique d'agrégation (SUMIF, comptages par année/niveau/service) directement
sur les données vivantes, pour qu'elle reste juste après chaque ré-import.

Note de périmètre : les onglets "Analyse", "Grille TCDP", "TCD1/TCD2" du
classeur d'origine s'appuient aussi sur des onglets non importés ici
(Certif, ILT_Neemba, 1. F. English — considérés comme des extractions
externes plutôt que des données saisies). Les indicateurs ci-dessous
utilisent donc les équivalents disponibles dans Base 1 / Base 2 / Objectif /
Cap&Cap / Départ1 / Recrutement, ce qui couvre la même intention (avancement
des certifications, objectifs vs réalisé, recrutement, départs).

Le fichier Excel étant abandonné, les indicateurs par technicien (effectif,
niveau atelier) sont calculés sur les données vivantes de
app/techniciens_store.py. Seuls les tableaux de référence qui ne sont pas
rattachés à un technicien (Recrutement annuel, Objectifs, Cap&Cap, Départs)
restent lus depuis les fichiers importés une fois pour toutes dans
app/personnel_store.py.
"""
from collections import defaultdict

from . import personnel_store as ps
from . import techniciens_store as ts

NIVEAUX_ORDRE = ["Foundational", "Advanced", "Expert"]


def _to_num(v):
    if v in (None, ""):
        return 0
    if isinstance(v, (int, float)):
        return v
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return 0


# ──────────────────────────────────────────────────────────────────────────
# Objectif : reproduit les SUMIF(Objectif[Niveau], <niveau>, Objectif[<col>])
# ──────────────────────────────────────────────────────────────────────────

def objectifs_par_niveau() -> dict:
    """Équivalent de l'onglet 'Objectif' (tableau récap. B3:N5) :
    somme par Niveau des colonnes Année en cours / 2022..2028 / Mini / Maxi /
    Résultats 2025 / Résultat 2026."""
    cols = ["Année en cours", "2022", "2023", "2024", "2025", "2026", "2027",
            "2028", "Mini", "Maxi", "Résultats 2025", "Résultat 2026"]
    out = {niveau: {c: 0 for c in cols} for niveau in NIVEAUX_ORDRE}
    for rec in ps.list_objectifs():
        niveau = rec.get("Niveau")
        if niveau not in out:
            continue
        for c in cols:
            out[niveau][c] += _to_num(rec.get(c))
    return out


def objectifs_par_societe(code_societe: str = None) -> list:
    rows = ps.list_objectifs()
    if code_societe:
        rows = [r for r in rows if r.get("Code société") == code_societe]
    return rows


# ──────────────────────────────────────────────────────────────────────────
# Cap&Cap : capacité / capabilité par pays, service, niveau, année
# ──────────────────────────────────────────────────────────────────────────

def cap_and_cap_par_niveau() -> dict:
    annees = ["2022", "2023", "2024", "2025", "2026", "2027", "2028"]
    out = {niveau: {a: 0 for a in annees} for niveau in NIVEAUX_ORDRE}
    for rec in ps.list_cap_and_cap():
        niveau = rec.get("Niveau")
        if niveau not in out:
            continue
        for a in annees:
            out[niveau][a] += _to_num(rec.get(a))
    return out


def cap_and_cap_par_service() -> dict:
    out = defaultdict(lambda: defaultdict(float))
    for rec in ps.list_cap_and_cap():
        service = rec.get("Service") or "?"
        out[service]["Année en cours"] += _to_num(rec.get("Année en cours"))
    return {k: dict(v) for k, v in out.items()}


# ──────────────────────────────────────────────────────────────────────────
# Recrutement annuel
# ──────────────────────────────────────────────────────────────────────────

def recrutement_summary() -> dict:
    rows = ps.list_recrutement()
    # colonnes réelles : {'Recrutement annuel': <code société>, '2025':..., '2026':..., 2026 validé...}
    total_effectue = 0
    total_prevision = 0
    total_valide = 0
    par_societe = []
    for r in rows:
        vals = list(r.values())
        code = vals[0] if vals else None
        effectue = _to_num(vals[1]) if len(vals) > 1 else 0
        prevision = _to_num(vals[2]) if len(vals) > 2 else 0
        valide = _to_num(vals[3]) if len(vals) > 3 else 0
        total_effectue += effectue
        total_prevision += prevision
        total_valide += valide
        par_societe.append({
            "code_societe": code, "effectue_2025": effectue,
            "prevision_2026": prevision, "valide_2026": valide,
        })
    return {
        "par_societe": par_societe,
        "total_effectue_2025": total_effectue,
        "total_prevision_2026": total_prevision,
        "total_valide_2026": total_valide,
    }


# ──────────────────────────────────────────────────────────────────────────
# Départs
# ──────────────────────────────────────────────────────────────────────────

def departs_summary() -> dict:
    """NB : dans le classeur d'origine, l'onglet "Départ1" est lui-même une
    copie/formule pointant vers un fichier externe ("Tableau d'analyse_Tech_
    Année", cf. note dans l'onglet). Dans l'extraction fournie, ces formules
    sont cassées (#REF!) faute d'accès à ce fichier externe : ces lignes sont
    donc écartées des comptages ci-dessous plutôt que comptées comme de vrais
    départs. Si le fichier "Tableau d'analyse_Tech_Année" est fourni, on
    pourra le brancher pour récupérer les vraies données de départs."""
    rows = ps.list_departs()
    lignes_invalides = 0
    par_annee = defaultdict(int)
    par_raison = defaultdict(int)
    par_service = defaultdict(int)
    valides = 0
    for r in rows:
        if any(v == "#REF!" for v in r.values()):
            lignes_invalides += 1
            continue
        valides += 1
        date_sortie = r.get("Date de sortie")
        annee_sortie = None
        if isinstance(date_sortie, str) and len(date_sortie) >= 4:
            annee_sortie = date_sortie[:4]
        if annee_sortie:
            par_annee[annee_sortie] += 1
        raison = r.get("Raison 1") or "Non renseigné"
        par_raison[raison] += 1
        service = r.get("Service") or "Non renseigné"
        par_service[service] += 1
    return {
        "total": valides,
        "lignes_invalides_ref": lignes_invalides,
        "par_annee": dict(sorted(par_annee.items())),
        "par_raison": dict(sorted(par_raison.items(), key=lambda kv: -kv[1])),
        "par_service": dict(sorted(par_service.items(), key=lambda kv: -kv[1])),
    }


# ──────────────────────────────────────────────────────────────────────────
# Évolution du niveau atelier (proxy de l'onglet "Analyse" : certifiés par
# année), à partir des colonnes historiques de Base 1.
# ──────────────────────────────────────────────────────────────────────────

_COLS_NIVEAU_ATELIER_PAR_AN = {
    "2021": "Niveau atelier 2021",
    "2022": "Niveau atelier 2022",
    "2023": "Niveau atelier 2023",
    "2024": "Niveau Atelier 2024",
    "2025": "Niveau Atelier 2025",
    "2026": "Niveau Atelier 2026",
}


def niveau_atelier_evolution() -> dict:
    """Nombre de techniciens par niveau atelier, pour chaque année 2021-2026."""
    out = {}
    rows = ts.list_techniciens()
    for annee, col in _COLS_NIVEAU_ATELIER_PAR_AN.items():
        compte = defaultdict(int)
        for r in rows:
            niveau = r.get(col)
            if niveau not in (None, ""):
                compte[str(niveau)] += 1
        out[annee] = dict(sorted(compte.items()))
    return out


def effectif_par_statut() -> dict:
    compte = defaultdict(int)
    for r in ts.list_techniciens():
        compte[r.get("Statut") or "Non renseigné"] += 1
    return dict(sorted(compte.items(), key=lambda kv: -kv[1]))


def effectif_par_service() -> dict:
    compte = defaultdict(int)
    for r in ts.list_techniciens():
        compte[r.get("Service") or "Non renseigné"] += 1
    return dict(sorted(compte.items(), key=lambda kv: -kv[1]))


def effectif_par_niveau_atelier_actuel() -> dict:
    compte = defaultdict(int)
    for r in ts.list_techniciens():
        niveau = r.get("Niveau Atelier actuel")
        if niveau not in (None, ""):
            compte[str(niveau)] += 1
    return dict(sorted(compte.items()))


# ──────────────────────────────────────────────────────────────────────────
# Progression OJT : % de compétences validées par technicien
# ──────────────────────────────────────────────────────────────────────────

def ojt_progression_globale() -> dict:
    """Pour chaque technicien : nb de compétences renseignées vs total de
    compétences suivies dans le référentiel."""
    referentiel = ts.list_referentiel()
    total_competences = len(referentiel) or 1
    rows = ts.list_techniciens()
    out = []
    for fiche in rows:
        nb_valide = len(fiche.get("competences", {}))
        out.append({
            "id": fiche.get("id"),
            "mtle": fiche.get("Mtle"),
            "nom": fiche.get("Nom / Prénom"),
            "niveau_atelier_actuel": fiche.get("Niveau Atelier actuel"),
            "niveau_atelier_cible": fiche.get("Niveau Atelier Cible"),
            "nb_competences_validees": nb_valide,
            "total_competences_referentiel": total_competences,
            "taux_progression": round(100 * nb_valide / total_competences, 1),
        })
    return {"techniciens": out, "total_competences_referentiel": total_competences}
