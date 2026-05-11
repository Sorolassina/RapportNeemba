# NEMBA GROUP – Générateur de rapports de formation

Plateforme FastAPI (HTML/CSS/JS) pour saisir les informations d'une formation et générer un **rapport PDF**.
Aucune base de données : tout est en **mémoire + fichiers temporaires** par session.

## Démarrage rapide (Windows / PowerShell)

Le projet expose un **task runner** PowerShell `makefile.ps1` à la racine.

```powershell
# Première installation après clone (uv sync + Tailwind CLI + build CSS)
.\makefile.ps1 install

# Serveur de développement (auto-reload sur http://127.0.0.1:8000)
.\makefile.ps1 dev

# Aide complète
.\makefile.ps1 help
```

### Tâches disponibles

| Tâche | Effet |
|---|---|
| `install` | `uv sync` + télécharge Tailwind CLI + build CSS |
| `dev` | Serveur dev (auto-reload) — `-BindHost`, `-Port` |
| `serve` | Serveur prod (sans reload, `0.0.0.0`) |
| `build-css` | Compile Tailwind en production (~20 Ko) |
| `watch-css` | Tailwind watch — recompile à chaque modif HTML |
| `icons` | Subset Material Symbols Outlined |
| `lint` / `format` | `ruff check` / `ruff format` |
| `clean -Force` | Supprime `__pycache__/`, `*.pyc` et uploads |
| `tree` | Arborescence du projet |
| `info` | Versions des outils installés |

### Démarrage manuel (sans makefile)

```bash
uv run uvicorn app.main:app --reload
```
Puis ouvrez http://127.0.0.1:8000

### Moteur PDF
Le rapport est généré nativement avec **ReportLab** (`reportlab_report.py`), exposé via `POST /generate-reportlab`.

## Flux
1. Saisie en 6 étapes (Client → Formateur → Sommaire/Objectifs → Planning → Évaluation (Excel) → Média & Emargements).
2. Aperçu HTML → Génération PDF téléchargeable.

## Structure
- `app/main.py` : routes FastAPI
- `app/analysis.py` : lecture Excel & KPIs
- `app/charts.py` : graphiques Matplotlib
- `reportlab_report.py` : génération PDF (ReportLab)
- `app/templates` : base, wizard, report
- `app/static` : CSS/JS et uploads par session

## Front-end (Tailwind CSS)

Tailwind est **pré-compilé** via le CLI standalone (pas de Node.js requis).
Le fichier généré `app/static/css/tailwind.css` (~20 Ko) est référencé dans `base_v2.html`.

### Premier lancement après clone

```powershell
# Télécharge tools\tailwindcss.exe (~38 Mo, ignoré par git)
.\scripts\tailwind.ps1 install

# Puis génère le CSS
.\scripts\tailwind.ps1 build
```

### Workflow dev (recompile à chaque modification de template)

```powershell
.\scripts\tailwind.ps1 watch
```

### Build de production (minifié)

```powershell
.\scripts\tailwind.ps1 build
```

> Si tu ajoutes une nouvelle classe Tailwind dans un template, **relance le build**
> sinon le CSS final ne contiendra pas la règle correspondante (purge automatique).

### Personnalisation

- `tailwind.config.js` : couleurs, espacements, polices, plugins
- `app/static/css/tailwind.input.css` : directives `@tailwind` + composants/utilities personnalisés
- `app/static/css/style.css` : CSS legacy (wizard / report / help / deployment)

### Polices Material Symbols

La police d'icônes Material Symbols Outlined est **auto-hébergée** dans
`app/static/fonts/MaterialSymbolsOutlined.woff2` (subseté pour ne contenir
que les icônes utilisées). Pour ajouter une icône : édite la liste `ICONS`
dans `scripts/subset_material_symbols.py` puis :

```powershell
uv run python scripts/subset_material_symbols.py
```
