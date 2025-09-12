#!/usr/bin/env python3
"""
WSGI Configuration pour NEMBA Report Generator
Déploiement avec Apache + mod_wsgi
"""

import sys
import os

# Ajouter le répertoire du projet au Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Configuration de l'environnement
os.environ.setdefault('PYTHONPATH', project_dir)

# Import de l'application FastAPI
from app.main import app

# Configuration pour mod_wsgi
application = app

# Configuration des logs (optionnel)
import logging
logging.basicConfig(level=logging.INFO)
