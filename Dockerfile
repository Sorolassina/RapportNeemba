# =============================================================================
# Dockerfile pour NEMBA Report
#
# Build :   docker build -t nemba-report:latest .
# Run   :   docker run -d -p 8000:8000 --name nemba-report nemba-report:latest
# =============================================================================

# ----- Stage 1 : builder (uv + dependencies) ---------------------------------
FROM python:3.11-slim AS builder

# uv : gestionnaire de paquets Python (rapide)
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# 1) Installation des deps (cache friendly)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2) Code applicatif
COPY app ./app
COPY reportlab_report.py ./

# 3) Install du projet lui-même
RUN uv sync --frozen --no-dev

# ----- Stage 2 : runtime (image finale, plus légère) -------------------------
FROM python:3.11-slim AS runtime

# Dépendances système nécessaires à matplotlib / reportlab / cairo
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libfreetype6 \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur non-root pour la sécurité
RUN groupadd -r nemba && useradd -r -g nemba -d /app -s /sbin/nologin nemba

WORKDIR /app

# Récupération du venv et du code depuis le builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Dossier d'uploads (volume recommandé en production)
RUN mkdir -p /app/app/static/uploads && \
    chown -R nemba:nemba /app

USER nemba

EXPOSE 8000

# Healthcheck : vérifie que l'app répond sur /home
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/home', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
