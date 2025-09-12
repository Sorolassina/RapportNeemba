# Guide de Déploiement - NEMBA Report Generator

## Vue d'ensemble

Cette application est un générateur de rapports de formation développé avec FastAPI et ReportLab. Elle permet de créer des rapports PDF professionnels à partir de données de formation saisies via une interface web.

## Prérequis système

### Serveur recommandé
- **OS** : Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM** : Minimum 2GB, recommandé 4GB+
- **CPU** : 2 cœurs minimum
- **Stockage** : 10GB d'espace libre minimum
- **Python** : 3.9+ (recommandé 3.11)

### Dépendances système
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev build-essential

# CentOS/RHEL
sudo yum install python311 python311-devel gcc gcc-c++ make
```

## Installation

### 1. Cloner le projet
```bash
cd /opt
sudo git clone <URL_DU_REPOSITORY> nemba-report
sudo chown -R www-data:www-data nemba-report
cd nemba-report
```

### 2. Configuration de l'environnement Python
```bash
# Créer un environnement virtuel
python3.11 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configuration des variables d'environnement
```bash
# Créer le fichier de configuration
sudo nano /etc/nemba-report.env
```

Contenu du fichier :
```env
# Configuration serveur
HOST=0.0.0.0
PORT=8000
DEBUG=False

# Configuration des chemins
UPLOAD_DIR=/var/lib/nemba-report/uploads
LOG_DIR=/var/log/nemba-report

# Configuration de sécurité
SECRET_KEY=votre_cle_secrete_ici
SESSION_TIMEOUT=3600

# Configuration des polices (optionnel)
FONTS_DIR=/opt/nemba-report/app/static/fonts
```

### 4. Création des répertoires système
```bash
# Répertoires de données
sudo mkdir -p /var/lib/nemba-report/uploads
sudo mkdir -p /var/log/nemba-report
sudo mkdir -p /opt/nemba-report/app/static/fonts

# Permissions
sudo chown -R www-data:www-data /var/lib/nemba-report
sudo chown -R www-data:www-data /var/log/nemba-report
sudo chmod -R 755 /var/lib/nemba-report
sudo chmod -R 755 /var/log/nemba-report
```

## Configuration du serveur web

### Comparaison des options

| Aspect | Nginx + Gunicorn | Apache + mod_wsgi |
|--------|------------------|-------------------|
| **Performance** | Excellente | Bonne |
| **Facilité de config** | Moyenne | Facile |
| **Intégration** | Externe | Native |
| **Monitoring** | Via systemd | Via Apache |
| **Ressources** | Faibles | Moyennes |
| **Sécurité** | Excellente | Bonne |
| **Maintenance** | Moyenne | Facile |

### Option 1 : Nginx + Gunicorn (Recommandé pour la performance)

#### Installation de Gunicorn
```bash
source venv/bin/activate
pip install gunicorn
```

#### Configuration Gunicorn
```bash
sudo nano /etc/systemd/system/nemba-report.service
```

Contenu du service :
```ini
[Unit]
Description=NEMBA Report Generator
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/nemba-report
Environment=PATH=/opt/nemba-report/venv/bin
ExecStart=/opt/nemba-report/venv/bin/gunicorn --bind unix:/run/nemba-report.sock --workers 3 --worker-class uvicorn.workers.UvicornWorker app.main:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

#### Configuration Nginx
```bash
sudo nano /etc/nginx/sites-available/nemba-report
```

Configuration Nginx :
```nginx
server {
    listen 80;
    server_name votre-domaine.com;  # Remplacer par votre domaine
    
    # Taille maximale des uploads (ajustez selon vos besoins)
    client_max_body_size 50M;
    
    # Logs
    access_log /var/log/nginx/nemba-report.access.log;
    error_log /var/log/nginx/nemba-report.error.log;
    
    # Fichiers statiques
    location /static/ {
        alias /opt/nemba-report/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Application principale
    location / {
        proxy_pass http://unix:/run/nemba-report.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Gestion des erreurs
    error_page 500 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
```

#### Activation des services
```bash
# Activer le site Nginx
sudo ln -s /etc/nginx/sites-available/nemba-report /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Démarrer le service
sudo systemctl enable nemba-report
sudo systemctl start nemba-report
sudo systemctl status nemba-report
```

### Option 2 : Apache + mod_wsgi (Mode HTML)

#### Installation des modules Apache
```bash
# Ubuntu/Debian
sudo apt install apache2 libapache2-mod-wsgi-py3

# CentOS/RHEL
sudo yum install httpd mod_wsgi python3-mod_wsgi
```

#### Configuration du fichier WSGI
```bash
# Le fichier app.wsgi est déjà créé dans le projet
sudo chmod 755 /opt/nemba-report/app.wsgi
```

#### Configuration Apache complète
```bash
# Copier la configuration Apache
sudo cp apache-config.conf /etc/apache2/sites-available/nemba-report.conf

# Ou créer manuellement
sudo nano /etc/apache2/sites-available/nemba-report.conf
```

Configuration Apache complète (voir fichier `apache-config.conf`) :
```apache
<VirtualHost *:80>
    ServerName votre-domaine.com
    DocumentRoot /opt/nemba-report
    
    # Configuration WSGI optimisée
    WSGIDaemonProcess nemba-report \
        python-path=/opt/nemba-report \
        python-home=/opt/nemba-report/venv \
        processes=4 \
        threads=15 \
        maximum-requests=1000 \
        user=www-data \
        group=www-data
    
    WSGIProcessGroup nemba-report
    WSGIScriptAlias / /opt/nemba-report/app.wsgi
    
    # Sécurité renforcée
    <Directory /opt/nemba-report>
        WSGIApplicationGroup %{GLOBAL}
        Require all granted
        
        # Interdire l'accès aux fichiers sensibles
        <Files "*.py">
            Require all denied
        </Files>
        <Files "*.env">
            Require all denied
        </Files>
    </Directory>
    
    # Fichiers statiques avec cache
    Alias /static /opt/nemba-report/app/static
    <Directory /opt/nemba-report/app/static>
        Require all granted
        ExpiresActive On
        ExpiresByType text/css "access plus 1 month"
        ExpiresByType application/javascript "access plus 1 month"
    </Directory>
    
    # Uploads sécurisés
    Alias /uploads /var/lib/nemba-report/uploads
    <Directory /var/lib/nemba-report/uploads>
        Require all granted
        Options -ExecCGI
        <Files "*.php">
            Require all denied
        </Files>
    </Directory>
    
    # Headers de sécurité
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options DENY
    Header always set X-XSS-Protection "1; mode=block"
    
    # Logs
    ErrorLog ${APACHE_LOG_DIR}/nemba-report_error.log
    CustomLog ${APACHE_LOG_DIR}/nemba-report_access.log combined
</VirtualHost>
```

#### Activation du site Apache
```bash
# Activer les modules nécessaires
sudo a2enmod wsgi
sudo a2enmod headers
sudo a2enmod expires
sudo a2enmod deflate

# Activer le site
sudo a2ensite nemba-report
sudo apache2ctl configtest
sudo systemctl reload apache2
sudo systemctl status apache2
```

## Configuration SSL (HTTPS)

### Avec Let's Encrypt (Certbot)
```bash
# Installation
sudo apt install certbot python3-certbot-nginx

# Génération du certificat
sudo certbot --nginx -d votre-domaine.com

# Renouvellement automatique
sudo crontab -e
# Ajouter : 0 12 * * * /usr/bin/certbot renew --quiet
```

## Configuration de la base de données (Optionnel)

Si vous souhaitez persister les sessions :
```bash
# Installation PostgreSQL
sudo apt install postgresql postgresql-contrib

# Création de la base
sudo -u postgres createdb nemba_report
sudo -u postgres createuser nemba_user
sudo -u postgres psql -c "ALTER USER nemba_user PASSWORD 'mot_de_passe';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE nemba_report TO nemba_user;"
```

## Monitoring et logs

### Configuration des logs
```bash
# Rotation des logs
sudo nano /etc/logrotate.d/nemba-report
```

Contenu :
```
/var/log/nemba-report/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
    postrotate
        systemctl reload nemba-report
    endscript
}
```

### Monitoring avec systemd
```bash
# Vérifier le statut
sudo systemctl status nemba-report

# Voir les logs en temps réel
sudo journalctl -u nemba-report -f

# Redémarrer le service
sudo systemctl restart nemba-report
```

## Sécurité

### Configuration du pare-feu
```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# iptables (CentOS)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

### Sécurisation des fichiers
```bash
# Permissions restrictives
sudo chmod 600 /etc/nemba-report.env
sudo chmod 755 /opt/nemba-report
sudo chmod -R 644 /opt/nemba-report/app/static
```

## Maintenance

### Mise à jour de l'application
```bash
cd /opt/nemba-report
sudo systemctl stop nemba-report
sudo -u www-data git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start nemba-report
```

### Sauvegarde
```bash
# Script de sauvegarde
sudo nano /usr/local/bin/backup-nemba-report.sh
```

Contenu du script :
```bash
#!/bin/bash
BACKUP_DIR="/backup/nemba-report"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR/$DATE
cp -r /opt/nemba-report $BACKUP_DIR/$DATE/
cp -r /var/lib/nemba-report/uploads $BACKUP_DIR/$DATE/

# Garder seulement les 7 dernières sauvegardes
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;
```

### Nettoyage automatique
```bash
# Cron job pour nettoyer les fichiers temporaires
sudo crontab -e
# Ajouter : 0 2 * * * find /var/lib/nemba-report/uploads -type f -mtime +7 -delete
```

## Dépannage

### Problèmes courants

1. **Erreur de permissions**
   ```bash
   sudo chown -R www-data:www-data /opt/nemba-report
   sudo chmod -R 755 /opt/nemba-report
   ```

2. **Port déjà utilisé**
   ```bash
   sudo netstat -tlnp | grep :8000
   sudo lsof -i :8000
   ```

3. **Problème de mémoire**
   ```bash
   # Réduire le nombre de workers dans le service systemd
   # Changer --workers 3 en --workers 1
   ```

4. **Logs d'erreur**
   ```bash
   sudo journalctl -u nemba-report --since "1 hour ago"
   sudo tail -f /var/log/nginx/nemba-report.error.log
   ```

### Test de fonctionnement
```bash
# Test local
curl http://localhost:8000/health

# Test depuis l'extérieur
curl http://votre-domaine.com/health
```

## Support

Pour toute question technique :
- Vérifiez les logs : `sudo journalctl -u nemba-report -f`
- Consultez la documentation FastAPI : https://fastapi.tiangolo.com/
- Consultez la documentation ReportLab : https://www.reportlab.com/docs/

## Notes importantes

- L'application génère des fichiers temporaires dans `/var/lib/nemba-report/uploads`
- Les sessions utilisateur expirent après 1 heure par défaut
- La taille maximale des fichiers uploadés est de 50MB (configurable)
- Les polices personnalisées peuvent être ajoutées dans `/opt/nemba-report/app/static/fonts/`
