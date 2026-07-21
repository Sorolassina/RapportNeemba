"""
Migration ponctuelle : fusionne les données précédemment importées du
classeur Excel (app/data/personnel/base1_personnel.json,
base2_avancement.json, app/data/tutorat/ojt_progression.json,
referentiel_competences.json) dans le nouveau store éditable
app/data/techniciens/techniciens.json (+ referentiel_competences.json).

À partir de cette migration, le fichier Excel est abandonné : cette
migration ne doit être exécutée qu'une seule fois, au moment du passage du
module Techniciens à sa nouvelle logique. Toute modification ultérieure se
fait dans l'application.

Usage : python scripts/migrate_personnel_to_techniciens.py
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONNEL_DIR = ROOT / "app" / "data" / "personnel"
TUTORAT_DIR = ROOT / "app" / "data" / "tutorat"
OUT_DIR = ROOT / "app" / "data" / "techniciens"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _load(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    base1 = _load(PERSONNEL_DIR / "base1_personnel.json")
    base2 = _load(PERSONNEL_DIR / "base2_avancement.json")
    ojt = _load(TUTORAT_DIR / "ojt_progression.json")
    referentiel = _load(TUTORAT_DIR / "referentiel_competences.json")

    if not base1:
        print("[!] base1_personnel.json introuvable, rien à migrer.")
        return

    base2_par_mtle = {}
    for rec in (base2["records"] if base2 else []):
        mtle = str(rec.get("Mtle"))
        base2_par_mtle.setdefault(mtle, []).append(rec)

    ojt_par_mtle = {}
    for rec in (ojt["records"] if ojt else []):
        mtle = str(rec["fiche"].get("Mtle"))
        ojt_par_mtle[mtle] = rec

    techniciens = []
    for rec in base1["records"]:
        mtle = str(rec.get("Mtle"))
        tech = dict(rec)  # tous les champs Base 1 tels quels
        tech["id"] = uuid.uuid4().hex[:10]
        tech["created_at"] = _now()

        avancement = []
        for a in base2_par_mtle.get(mtle, []):
            a = dict(a)
            a["id"] = uuid.uuid4().hex[:10]
            avancement.append(a)
        tech["avancement"] = avancement

        ojt_rec = ojt_par_mtle.get(mtle)
        tech["ojt_niveaux"] = ojt_rec["niveaux"] if ojt_rec else {}
        tech["competences"] = ojt_rec["competences"] if ojt_rec else {}

        techniciens.append(tech)

    (OUT_DIR / "techniciens.json").write_text(
        json.dumps(techniciens, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[ok] {len(techniciens)} techniciens migrés -> app/data/techniciens/techniciens.json")

    if referentiel:
        (OUT_DIR / "referentiel_competences.json").write_text(
            json.dumps(referentiel["records"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[ok] {len(referentiel['records'])} compétences -> app/data/techniciens/referentiel_competences.json")


if __name__ == "__main__":
    main()
