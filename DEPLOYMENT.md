# Guide de Déploiement — LiuGong Academy

## Vue d'ensemble

Application **FastAPI + Tailwind + ReportLab** pour générer des rapports de formation
au format PDF. **Aucune base de données** : tout est en mémoire + fichiers temporaires
par session.

Le projet est **Windows-first** : un script PowerShell `makefile.ps1` automatise tout
le déploiement (diagnostic, dépendances, build front-end, services Windows, conteneurs
Docker, tunnel Cloudflare).

---

## 🚀 Quick start (1 commande)

Sur Windows, après `git clone` :

```powershell
.\makefile.ps1 start
```

Le script effectue **12 vérifications avec auto-fix**, puis propose un menu :
1. **Dev local** (uvicorn --reload)
2. **Service NSSM** (Windows Service permanent)
3. **Docker** (conteneur isolé)

Et propose ensuite **Cloudflare Tunnel** (Quick ou nommé) pour exposer sur Internet.

```powershell
# Variantes utiles
.\makefile.ps1 start -Port 8080
.\makefile.ps1 start -Profile prod -Pull -Backup
.\makefile.ps1 start -NoBrowser -NoFirewall   # CI / serveur headless
.\makefile.ps1 help                            # aide complète
```

---

## Prérequis

### Windows (recommandé)

| Outil | Version | Rôle | Auto-installé par `start` |
|---|---|---|---|
| **PowerShell** | 5.1+ ou 7+ | Shell | ✅ (Windows) |
| **uv** | 0.4+ | Gestion Python | ❌ → `irm https://astral.sh/uv/install.ps1 \| iex` |
| **Python** | 3.11+ | Runtime | ✅ via `uv python install` |
| **git** | 2.x | Clone + pull | Recommandé |
| **NSSM** | 2.24+ | Service Windows | Optionnel (mode 2) |
| **Docker Desktop** | 4.x+ | Conteneur | ✅ via `winget install` (mode 3) |
| **cloudflared** | 2024+ | Tunnel CF | ✅ via `winget install` (option) |

### Linux / cloud

| Cible | Version |
|---|---|
| **Ubuntu / Debian** | 20.04 / 11+ |
| **Python** | 3.11+ |
| **uv** ou **pip** | dernière |
| **Render** / **Railway** / **Fly.io** | compte gratuit OK |

---

## 1. Workflow Windows recommandé

### a) Pré-requis machine

```powershell
# 1. Installer uv (gestionnaire Python rapide)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Cloner le projet
git clone <URL_DU_REPO> liugong-academy
cd liugong-academy

# 3. Lancement assisté
.\makefile.ps1 start
```

Tout le reste (Python 3.11, dépendances, Tailwind CLI, CSS compilé,
police d'icônes, dossiers `uploads/` et `logs/`, génération SECRET_KEY,
configuration Docker / NSSM / Cloudflare) est automatique.

### b) Mode dev local

Lancement uvicorn avec `--reload`, ouverture auto du navigateur après ~2s.

```powershell
.\makefile.ps1 start
# (puis : 1)
# ou directement :
.\makefile.ps1 dev
```

### c) Mode service Windows (NSSM)

Le script crée un service Windows nommé **`liugong-academy`** qui :
- Démarre automatiquement au boot (`SERVICE_AUTO_START`)
- Redémarre automatiquement en cas de crash (5 s de délai)
- Logge dans `logs/liugong-academy.out.log` et `logs/liugong-academy.err.log`
- Tourne via `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`

```powershell
.\makefile.ps1 start
# (puis : 2 → o pour confirmer la création)

# Commandes utiles ensuite
.\makefile.ps1 nssm-status
.\makefile.ps1 nssm-restart
.\makefile.ps1 nssm-stop
.\makefile.ps1 nssm-remove
Get-Content logs\liugong-academy.out.log -Tail 50 -Wait
```

**Pré-requis** : avoir installé NSSM ([https://nssm.cc/download](https://nssm.cc/download))
et l'avoir ajouté au PATH système.

### d) Mode Docker

Le `Dockerfile` à la racine est multi-stage (builder + runtime python:3.11-slim),
avec utilisateur non-root, healthcheck HTTP, et libs cairo/freetype pour matplotlib.

```powershell
.\makefile.ps1 start
# (puis : 3)
# Le script propose d'installer Docker Desktop via winget si absent.

# Commandes utiles ensuite
docker ps -f name=liugong-academy
docker logs -f liugong-academy
docker restart liugong-academy
docker stop liugong-academy
docker rm -f liugong-academy             # supprimer le conteneur
```

Le conteneur expose `0.0.0.0:8000` et monte `app/static/uploads/` en volume
pour persister les uploads de session.

### e) Cloudflare Tunnel

Après le choix du mode (1, 2 ou 3), le script demande :

```text
Voulez-vous aussi exposer via Cloudflare Tunnel ? (o/n) [n]:
```

Si **oui**, deux modes disponibles :

| Mode | Pour quoi | URL générée |
|---|---|---|
| **Quick Tunnel** | Test rapide, démo (pas de compte requis) | `*.trycloudflare.com` (éphémère) |
| **Tunnel nommé** | Production avec domaine | `https://votre-sous-domaine.votre-domaine.com` |

Le tunnel nommé crée automatiquement :
- `~/.cloudflared/config.yml` (ingress vers `localhost:port`)
- Une route DNS dans Cloudflare
- Un service `cloudflared` (optionnel, pour autostart)

```powershell
# Pour démarrer comme service Windows ensuite (autostart)
cloudflared service install
```

---

## 2. Structure des dossiers en runtime

```
liugong-academy/
├── app/
│   ├── main.py                  # Routes FastAPI
│   ├── analysis.py              # Lecture Excel + KPIs
│   ├── charts.py                # Matplotlib
│   ├── templates/               # Jinja2
│   └── static/
│       ├── css/
│       │   ├── tailwind.css     # GÉNÉRÉ (~20 Ko, ne pas éditer)
│       │   ├── tailwind.input.css
│       │   └── style.css
│       ├── fonts/
│       │   └── MaterialSymbolsOutlined.woff2  # subseté
│       └── uploads/             # uploads de session (volume Docker)
├── reportlab_report.py          # Génération PDF
├── tools/
│   └── tailwindcss.exe          # Binaire CLI (gitignored, ~38 Mo)
├── scripts/
│   ├── tailwind.ps1
│   └── subset_material_symbols.py
├── logs/                        # Logs NSSM (gitignored)
├── backups/                     # Backups uploads (gitignored)
├── makefile.ps1                 # Task runner principal
├── Dockerfile
├── tailwind.config.js
├── pyproject.toml
└── .env.example
```

---

## 3. Variables d'environnement

`.env` (copié depuis `.env.example` au premier lancement) :

```env
# Port d'écoute (défaut: 8000)
# PORT=8000

# Root path FastAPI (reverse proxy)
# ROOT_PATH=/neembacoaching

# Version applicative (sinon: court SHA git, sinon timestamp)
# APP_VERSION=

# Clé secrète pour les sessions (auto-générée par makefile.ps1 start si vide)
# SECRET_KEY=
```

**Profils multi-environnement** : créer `.env.dev`, `.env.staging`, `.env.prod`
puis lancer avec `-Profile <nom>`. Le bon `.env` est copié à chaque démarrage.

---

## 4. Maintenance

### Mise à jour du code

```powershell
.\makefile.ps1 start -Pull -Backup
# (-Pull : git pull avant lancement)
# (-Backup : sauvegarde uploads/ avant)
```

### Mise à jour du CSS / icônes après modification de templates

```powershell
.\makefile.ps1 build-css            # une fois
.\makefile.ps1 watch-css            # mode dev (recompile auto)
.\makefile.ps1 icons                # après ajout d'une nouvelle icône
```

### Nettoyage

```powershell
.\makefile.ps1 clean -Force         # __pycache__, *.pyc, uploads, caches
```

### Diagnostic / état

```powershell
.\makefile.ps1 info                 # versions des outils + tailles
.\makefile.ps1 tree                 # arborescence
```

---

## 5. Déploiement Linux (alternative)

Si la cible est un serveur Linux (sans Windows / NSSM), voici la procédure
manuelle équivalente.

### a) Installation

```bash
# Pré-requis système (Debian/Ubuntu)
sudo apt update && sudo apt install -y python3.11 python3.11-venv build-essential nginx git

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Cloner et installer
sudo git clone <URL> /opt/liugong-academy
cd /opt/liugong-academy
uv sync

# Build du CSS Tailwind (équivalent .\scripts\tailwind.ps1 build)
curl -L https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 \
     -o tools/tailwindcss && chmod +x tools/tailwindcss
./tools/tailwindcss -c tailwind.config.js \
                    -i app/static/css/tailwind.input.css \
                    -o app/static/css/tailwind.css --minify
```

### b) Service systemd

```ini
# /etc/systemd/system/liugong-academy.service
[Unit]
Description=LiuGong Academy
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/liugong-academy
ExecStart=/root/.local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now liugong-academy
sudo systemctl status liugong-academy
```

### c) Reverse proxy Nginx

```nginx
# /etc/nginx/sites-available/liugong-academy
server {
    listen 80;
    server_name votre-domaine.com;
    client_max_body_size 50M;

    location /static/ {
        alias /opt/liugong-academy/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/liugong-academy /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d votre-domaine.com   # SSL via Let's Encrypt
```

---

## 6. Déploiement cloud (Render / Railway)

### Render

Créer `render.yaml` à la racine :

```yaml
services:
  - type: web
    name: liugong-academy
    env: python
    plan: free
    buildCommand: |
      pip install uv
      uv sync --frozen
      curl -L https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 -o /tmp/tailwindcss
      chmod +x /tmp/tailwindcss
      /tmp/tailwindcss -c tailwind.config.js -i app/static/css/tailwind.input.css -o app/static/css/tailwind.css --minify
    startCommand: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
```

Puis : Render → New + → Web Service → connecter le repo. SSL automatique inclus.

### Railway / Fly.io

Le `Dockerfile` du projet fonctionne tel quel. Configurer le port (`8000` exposé).

---

## 7. Sécurité

| Aspect | Recommandation |
|---|---|
| **Firewall** | Le mode `start` propose d'ouvrir le port via `Add-FirewallRule` (UAC) |
| **HTTPS** | Cloudflare Tunnel fournit TLS automatiquement, sinon Let's Encrypt |
| **`.env`** | Jamais commit (déjà dans `.gitignore`) |
| **`SECRET_KEY`** | Auto-généré par `start` si vide dans `.env` |
| **User non-root** | Image Docker tourne en `liugong` (UID dédié) |
| **Permissions uploads** | NSSM tourne en LocalSystem ; sur Linux, `www-data` |

---

## 8. Dépannage

### Port déjà utilisé

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
Stop-Process -Id <PID> -Force
# Ou changer de port :
.\makefile.ps1 start -Port 8080
```

### Icônes Material Symbols affichées comme texte

Police absente. Lancer :

```powershell
.\makefile.ps1 icons
```

### CSS non à jour après modification d'un template

Le pre-flight de `start` détecte automatiquement. Sinon manuellement :

```powershell
.\makefile.ps1 build-css
```

### Service NSSM ne démarre pas

```powershell
.\makefile.ps1 nssm-status
Get-Content logs\liugong-academy.err.log -Tail 50
# Erreurs typiques : port pris, deps manquantes, .env corrompu
```

### Container Docker crash au démarrage

```powershell
docker logs liugong-academy --tail 100
docker exec -it liugong-academy bash    # debug interactif
```

### Cloudflared : authentification échouée

Si pas de compte / domaine Cloudflare :
1. Sign up gratuit : <https://dash.cloudflare.com/sign-up>
2. Sites → Add a site (plan Free)
3. Pointer les nameservers du domaine vers Cloudflare
4. Relancer `.\makefile.ps1 start` → option Cloudflared → mode 2

### Mode dev : auto-reload ne déclenche rien

Vérifier que les fichiers modifiés sont bien dans le watcher uvicorn.
Le `--reload` surveille `app/`. Pour les templates HTML, le serveur les
recharge à chaque requête (Jinja).

---

## 9. Commandes de référence rapide

```powershell
# Démarrage assisté (le plus simple)
.\makefile.ps1 start

# Production avec backup + git pull
.\makefile.ps1 start -Profile prod -Pull -Backup

# Mode CI / headless
.\makefile.ps1 start -NoBrowser -NoFirewall -NoChecks

# Diagnostic seul (sans démarrage)
.\makefile.ps1 info

# Front-end uniquement
.\makefile.ps1 build-css
.\makefile.ps1 watch-css

# Maintenance
.\makefile.ps1 clean -Force
.\makefile.ps1 lint
.\makefile.ps1 format

# Aide complète
.\makefile.ps1 help
```

---

## Support

- Code source : `app/main.py`, `reportlab_report.py`
- Documentation FastAPI : <https://fastapi.tiangolo.com/>
- Documentation ReportLab : <https://www.reportlab.com/docs/>
- Documentation Tailwind v3 : <https://v3.tailwindcss.com/docs/installation>
- Documentation Cloudflare Tunnel : <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/>
