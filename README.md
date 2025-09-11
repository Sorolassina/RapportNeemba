# NEMBA GROUP – Générateur de rapports de formation

Plateforme FastAPI (HTML/CSS/JS) pour saisir les informations d'une formation et générer un **rapport PDF**.
Aucune base de données : tout est en **mémoire + fichiers temporaires** par session.

## Démarrer
```bash
uv run uvicorn app.main:app --reload
```
Puis ouvrez http://127.0.0.1:8000

### Dépendances PDF
- **WeasyPrint** (automatique sur Linux/macOS) _ou_
- **wkhtmltopdf** (Windows recommandé) + `pdfkit`.
  - Installez wkhtmltopdf puis, si nécessaire, renseignez la variable d'environnement `WKHTMLTOPDF_CMD` vers l'exécutable.

## Flux
1. Saisie en 6 étapes (Client → Formateur → Sommaire/Objectifs → Planning → Évaluation (Excel) → Média & Emargements).
2. Aperçu HTML → Génération PDF téléchargeable.

## Structure
- `app/main.py` : routes FastAPI
- `app/analysis.py` : lecture Excel & KPIs
- `app/charts.py` : graphiques Matplotlib
- `app/pdf.py` : HTML → PDF (WeasyPrint ou wkhtmltopdf)
- `app/templates` : base, wizard, report
- `app/static` : CSS/JS et uploads par session
