# =============================================================================
# makefile.ps1 — Task runner PowerShell pour LiuGong Academy.
#
# Usage :
#   .\makefile.ps1                   # Affiche l'aide
#   .\makefile.ps1 <tâche> [opts]
#
# Exemples :
#   .\makefile.ps1 install           # Première install après clone
#   .\makefile.ps1 dev               # Serveur dev (auto-reload, port 8000)
#   .\makefile.ps1 dev -Port 8080
#   .\makefile.ps1 serve -BindHost 0.0.0.0 -Port 8000
#   .\makefile.ps1 watch-css         # Tailwind en watch (recompile auto)
#   .\makefile.ps1 build-css         # CSS production (minifié)
#   .\makefile.ps1 icons             # Subset Material Symbols
#   .\makefile.ps1 clean -Force      # Nettoie caches + uploads
#   .\makefile.ps1 nssm-install      # Service Windows NSSM
#   .\makefile.ps1 nssm-status       # Statut du service
# =============================================================================

[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)]
    [string]$Task = 'help',

    [string]$BindHost = '127.0.0.1',
    [int]   $Port     = 8000,

    # Profil .env charge avant lancement (.env.dev, .env.staging, .env.prod)
    [ValidateSet('dev','staging','prod')]
    [string]$Profile  = 'dev',

    # Comportements modulables au demarrage (utilises par 'start')
    [switch]$Force,        # confirme suppression dans 'clean'
    [switch]$Quiet,        # supprime les titres et etapes
    [switch]$NoBrowser,    # ne pas ouvrir le navigateur apres demarrage
    [switch]$NoFirewall,   # ne pas creer de regle pare-feu
    [switch]$Pull,         # git pull avant lancement
    [switch]$Backup,       # backup app/static/uploads avant NSSM/Docker
    [switch]$NoChecks      # saute le pre-flight (debug)
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = $PSScriptRoot
$NssmServiceName = 'liugong-academy'
$DockerImageName = 'liugong-academy:latest'
$DockerContainerName = 'liugong-academy'
$AppDisplayName = 'LiuGong Academy'
$AppServiceDescription = "Plateforme FastAPI LiuGong Academy - Façonner l'Excellence Technique."
Set-Location $ProjectRoot

# ----------------------------------------------------------------------------
# Helpers couleurs
# ----------------------------------------------------------------------------
function Write-Title { param([string]$msg) if (-not $Quiet) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan } }
function Write-Step  { param([string]$msg) if (-not $Quiet) { Write-Host "  > $msg" -ForegroundColor Yellow } }
function Write-Ok    { param([string]$msg) if (-not $Quiet) { Write-Host "  [OK] $msg" -ForegroundColor Green } }
function Write-Warn  { param([string]$msg) Write-Host "  [!]  $msg" -ForegroundColor DarkYellow }
function Write-Err2  { param([string]$msg) Write-Host "  [X] $msg" -ForegroundColor Red }
function Write-Info2 { param([string]$msg) if (-not $Quiet) { Write-Host "  $msg" -ForegroundColor Gray } }

# ----------------------------------------------------------------------------
# Vérifications environnement
# ----------------------------------------------------------------------------
function Assert-Uv {
    if (-not (Resolve-Uv)) {
        Write-Err2 "uv introuvable. Installation : https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    }
}

function Test-CommandAvailable {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-NssmAvailable {
    if (-not (Test-CommandAvailable 'nssm')) {
        Write-Err2 "nssm.exe introuvable dans le PATH."
        Write-Info2 "  Installer : https://nssm.cc/download"
        return $false
    }
    return $true
}

function Assert-Nssm {
    if (-not (Test-NssmAvailable)) { exit 1 }
}

function Test-NssmServiceRegistered {
    param([string]$ServiceName = $NssmServiceName)
    $status = ((& nssm status $ServiceName 2>$null) | Out-String).Trim()
    return ($LASTEXITCODE -eq 0 -and $status)
}

function Get-NssmServiceStatus {
    param([string]$ServiceName = $NssmServiceName)
    return ((& nssm status $ServiceName 2>$null) | Out-String).Trim()
}

# ----------------------------------------------------------------------------
# Resolve-Uv : trouve uv.exe meme s'il n'est pas dans le PATH du shell courant
# (cas frequent apres une fresh install ou un changement d'utilisateur Windows).
# Si trouve hors PATH, on prepend son dossier au $env:Path de la session pour
# que toutes les commandes 'uv ...' subsequentes fonctionnent.
# Retourne le chemin complet de uv.exe ou $null.
# ----------------------------------------------------------------------------
function Resolve-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        (Join-Path $env:USERPROFILE '.local\bin\uv.exe'),
        (Join-Path $env:USERPROFILE '.cargo\bin\uv.exe'),
        (Join-Path $env:LOCALAPPDATA 'uv\uv.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\uv\uv.exe'),
        (Join-Path $env:APPDATA       'Python\Scripts\uv.exe')
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path -LiteralPath $p)) {
            $dir = Split-Path -Parent $p
            if (-not (";$($env:Path);" -like "*;$dir;*")) {
                $env:Path = "$dir;$env:Path"
            }
            return $p
        }
    }
    return $null
}

# ----------------------------------------------------------------------------
# Install-Uv : installation auto via le script officiel Astral. Bloquant et
# bavard. Retourne $true en cas de succes (uv.exe presente apres install).
# ----------------------------------------------------------------------------
function Install-Uv {
    Write-Info2 "Installation de uv (script officiel Astral)..."
    try {
        # Le script ecrit uv dans %USERPROFILE%\.local\bin
        Invoke-RestMethod -Uri 'https://astral.sh/uv/install.ps1' -UseBasicParsing |
            Invoke-Expression
    } catch {
        Write-Err2 "Echec du telechargement du script d'installation uv : $($_.Exception.Message)"
        return $false
    }
    if (Resolve-Uv) {
        Write-Ok "uv installe avec succes"
        return $true
    }
    Write-Err2 "uv ne semble pas avoir ete installe correctement."
    return $false
}

function Test-PortFree {
    param([int]$VPort)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect('127.0.0.1', $VPort)
        $tcp.Close()
        return $false   # port occupe
    } catch {
        return $true    # port libre
    }
}

function Read-Choice {
    param(
        [string]$Prompt,
        [string[]]$Choices,
        [string]$Default
    )
    $answer = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
    return $answer.Trim().ToLower()
}

function Test-CssNeedsRebuild {
    $css = Join-Path $ProjectRoot 'app\static\css\tailwind.css'
    if (-not (Test-Path $css)) { return $true }
    $cssTime = (Get-Item $css).LastWriteTime
    $sources = @(
        Join-Path $ProjectRoot 'app\templates'
        Join-Path $ProjectRoot 'app\static\js'
        Join-Path $ProjectRoot 'app\static\css\tailwind.input.css'
        Join-Path $ProjectRoot 'tailwind.config.js'
    )
    foreach ($src in $sources) {
        if (-not (Test-Path $src)) { continue }
        $newer = Get-ChildItem -Path $src -File -Recurse -ErrorAction SilentlyContinue |
                 Where-Object { $_.LastWriteTime -gt $cssTime } | Select-Object -First 1
        if ($newer) { return $true }
    }
    return $false
}

# =============================================================================
# HELPERS DEPLOIEMENT (ajouts pour 'start')
# =============================================================================

# A. Version Python -----------------------------------------------------------
function Test-PythonVersion {
    $version = & uv run python --version 2>&1 | Out-String
    if ($version -match 'Python (\d+)\.(\d+)\.(\d+)') {
        $major = [int]$Matches[1]; $minor = [int]$Matches[2]
        $ok = ($major -gt 3) -or ($major -eq 3 -and $minor -ge 11)
        return [PSCustomObject]@{ Ok = $ok; Version = "$major.$minor.$($Matches[3])" }
    }
    return [PSCustomObject]@{ Ok = $false; Version = 'inconnue' }
}

# B. Smoke test : l'app importe sans erreur ----------------------------------
function Test-AppImport {
    $output = & uv run python -c "from app.main import app; print('IMPORT_OK')" 2>&1 | Out-String
    if ($output -match 'IMPORT_OK') {
        return [PSCustomObject]@{ Ok = $true; Output = $output }
    }
    return [PSCustomObject]@{ Ok = $false; Output = $output }
}

# C. SECRET_KEY auto-genere (uniquement si la variable existe deja vide) ----
function Initialize-SecretKey {
    $envPath = Join-Path $ProjectRoot '.env'
    if (-not (Test-Path $envPath)) { return $false }
    $content = Get-Content $envPath -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return $false }

    $needsKey = $false
    if ($content -match '(?m)^SECRET_KEY\s*=\s*["'']?\s*["'']?\s*$') { $needsKey = $true }

    if (-not $needsKey) { return $false }

    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $key = -join ($bytes | ForEach-Object { '{0:x2}' -f $_ })
    $content = $content -replace '(?m)^SECRET_KEY\s*=.*$', "SECRET_KEY=$key"
    Set-Content -Path $envPath -Value $content -NoNewline -Encoding UTF8
    return $true
}

# D. Dossier logs/ -----------------------------------------------------------
function Initialize-LogsFolder {
    $logs = Join-Path $ProjectRoot 'logs'
    $created = $false
    if (-not (Test-Path $logs)) {
        New-Item -ItemType Directory -Path $logs -Force | Out-Null
        $created = $true
    }
    $keep = Join-Path $logs '.gitkeep'
    if (-not (Test-Path $keep)) {
        New-Item -ItemType File -Path $keep -Force | Out-Null
    }
    return $created
}

# E. Espace disque -----------------------------------------------------------
function Test-DiskSpace {
    param([int]$MinMB = 500)
    try {
        $drive = (Get-Item $ProjectRoot).PSDrive.Name
        $free  = (Get-PSDrive $drive -ErrorAction Stop).Free
        $freeMB = [Math]::Round($free / 1MB)
        return [PSCustomObject]@{ FreeMB = $freeMB; Ok = ($freeMB -gt $MinMB); Drive = $drive }
    } catch {
        return [PSCustomObject]@{ FreeMB = -1; Ok = $true; Drive = '?' }
    }
}

# F. Git status --------------------------------------------------------------
function Test-GitClean {
    if (-not (Test-CommandAvailable 'git')) {
        return [PSCustomObject]@{ Available = $false }
    }
    Push-Location $ProjectRoot
    try {
        $insideRepo = (& git rev-parse --is-inside-work-tree 2>$null) -eq 'true'
        if (-not $insideRepo) {
            return [PSCustomObject]@{ Available = $true; InRepo = $false }
        }
        $status = & git status --porcelain 2>$null
        $branch = (& git rev-parse --abbrev-ref HEAD 2>$null)
        $count  = if ($status) { ($status -split "`n" | Where-Object { $_ }).Count } else { 0 }
        return [PSCustomObject]@{
            Available = $true; InRepo = $true; Clean = ($count -eq 0); Files = $count; Branch = $branch
        }
    } finally { Pop-Location }
}

# G. Pare-feu Windows --------------------------------------------------------
function Add-FirewallRule {
    param([int]$VPort)

    $ruleName = "LiuGong-Academy-$VPort"
    try {
        $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
        if ($existing) { return [PSCustomObject]@{ Ok = $true; Existed = $true } }
    } catch {
        return [PSCustomObject]@{ Ok = $false; Existed = $false; Reason = 'NoNetSecurity' }
    }

    Write-Info2 "  Creation de la regle pare-feu (UAC va demander les droits admin)..."
    $cmd = "New-NetFirewallRule -DisplayName '$ruleName' -Direction Inbound " +
           "-LocalPort $VPort -Protocol TCP -Action Allow -Profile Any | Out-Null"
    try {
        Start-Process -FilePath 'powershell.exe' `
                      -ArgumentList @('-NoProfile', '-Command', $cmd) `
                      -Verb RunAs -Wait
        return [PSCustomObject]@{ Ok = $true; Existed = $false }
    } catch {
        return [PSCustomObject]@{ Ok = $false; Existed = $false; Reason = 'UAC denied' }
    }
}

# H. Healthcheck post-demarrage ----------------------------------------------
function Get-RootPath {
    <#
    .SYNOPSIS
    Lit ROOT_PATH depuis .env (format /xxx ou ""). Cache le resultat.
    #>
    if ($script:_cachedRootPath -ne $null) { return $script:_cachedRootPath }
    $rp = ''
    $envFile = Join-Path $ProjectRoot '.env'
    if (Test-Path $envFile) {
        $line = (Get-Content $envFile -ErrorAction SilentlyContinue |
                 Where-Object { $_ -match '^\s*ROOT_PATH\s*=' } | Select-Object -First 1)
        if ($line) {
            $rp = ($line -replace '^\s*ROOT_PATH\s*=\s*', '').Trim().Trim('"').Trim("'")
            if ($rp -and -not $rp.StartsWith('/')) { $rp = '/' + $rp }
            $rp = $rp.TrimEnd('/')
        }
    }
    $script:_cachedRootPath = $rp
    return $rp
}

function Get-HealthUrl {
    param([int]$VPort)
    $rp = Get-RootPath
    return "http://localhost:$VPort$rp/health"
}

function Get-AppUrl {
    param([int]$VPort)
    $rp = Get-RootPath
    return "http://localhost:$VPort$rp/"
}

function Wait-AppReady {
    param([int]$VPort, [int]$TimeoutSec = 30)
    $url = Get-HealthUrl -VPort $VPort
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) { return $true }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    return $false
}

# I. Open browser ------------------------------------------------------------
function Open-AppInBrowser {
    param([int]$VPort)
    if ($script:NoBrowser) { return }
    Start-Process (Get-AppUrl -VPort $VPort)
}

# J. Recap final -------------------------------------------------------------
function Show-LaunchSummary {
    param(
        [int]$VPort,
        [string]$Mode,
        [string]$TunnelMode = ''
    )
    Write-Title "RECAP - Application demarree"
    $rp = Get-RootPath
    Write-Info2 "Mode           : $Mode"
    Write-Info2 "Profil .env    : $Profile"
    if ($rp) { Write-Info2 "ROOT_PATH      : $rp  (prefixe d'URL applique)" }
    Write-Info2 "URL locale     : http://localhost:$VPort$rp/"

    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
               Where-Object {
                   $_.IPAddress -ne '127.0.0.1' -and
                   $_.PrefixOrigin -in @('Dhcp','Manual') -and
                   $_.IPAddress -notlike '169.254.*'
               } | Select-Object -First 1).IPAddress
        if ($ip) { Write-Info2 "URL reseau     : http://${ip}:$VPort$rp/" }
    } catch {}

    if ($TunnelMode) { Write-Info2 "Tunnel CF      : voir la fenetre cloudflared ($TunnelMode)" }

    Write-Host ""
    Write-Info2 "Commandes utiles :"
    switch ($Mode) {
        'NSSM' {
            Write-Info2 "  Statut    : .\makefile.ps1 nssm-status"
            Write-Info2 "  Restart   : .\makefile.ps1 nssm-restart"
            Write-Info2 "  Stop      : .\makefile.ps1 nssm-stop"
            Write-Info2 "  Logs      : Get-Content logs\$NssmServiceName.out.log -Tail 50 -Wait"
        }
        'Docker' {
            Write-Info2 "  Statut    : docker ps -f name=$DockerContainerName"
            Write-Info2 "  Logs      : docker logs -f $DockerContainerName"
            Write-Info2 "  Restart   : docker restart $DockerContainerName"
            Write-Info2 "  Stop      : docker stop $DockerContainerName"
        }
        default {
            Write-Info2 "  Arret     : Ctrl+C dans cette fenetre"
        }
    }
}

# K. Profil .env -------------------------------------------------------------
function Resolve-EnvFile {
    param([string]$ProfileName)
    $target = Join-Path $ProjectRoot '.env'
    $source = Join-Path $ProjectRoot ".env.$ProfileName"

    if (Test-Path $source) {
        Copy-Item $source $target -Force
        return [PSCustomObject]@{ Loaded = $true; From = ".env.$ProfileName" }
    }
    return [PSCustomObject]@{ Loaded = $false; From = '.env' }
}

# L. git pull ----------------------------------------------------------------
function Invoke-GitPull {
    if (-not (Test-CommandAvailable 'git')) {
        Write-Warn "git non installe, skip pull."
        return $false
    }
    Push-Location $ProjectRoot
    try {
        $insideRepo = (& git rev-parse --is-inside-work-tree 2>$null) -eq 'true'
        if (-not $insideRepo) {
            Write-Warn "Pas dans un dossier git, skip pull."
            return $false
        }
        Write-Step "Recuperation de la derniere version (git pull)..."
        & git pull --ff-only 2>&1 | Out-Host
        return ($LASTEXITCODE -eq 0)
    } finally { Pop-Location }
}

# M. Backup uploads ----------------------------------------------------------
function Backup-Uploads {
    $uploads = Join-Path $ProjectRoot 'app\static\uploads'
    if (-not (Test-Path $uploads)) { return $null }
    $items = Get-ChildItem $uploads -Force -ErrorAction SilentlyContinue |
             Where-Object { $_.Name -ne '.gitkeep' }
    if ($items.Count -eq 0) {
        return [PSCustomObject]@{ Skipped = $true; Reason = 'empty' }
    }
    $stamp = Get-Date -Format 'yyyy-MM-dd-HHmm'
    $backupDir = Join-Path $ProjectRoot "backups\$stamp"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    Copy-Item -Path "$uploads\*" -Destination $backupDir -Recurse -Force -Exclude '.gitkeep'
    return [PSCustomObject]@{ Skipped = $false; Path = $backupDir; Count = $items.Count }
}

# N. Mise a jour des outils tiers --------------------------------------------
function Test-ToolsUpdate {
    $updates = @()
    # Tailwind
    $bin = Join-Path $ProjectRoot 'tools\tailwindcss.exe'
    if (Test-Path $bin) {
        $current = $null
        $line = & $bin --help 2>&1 | Where-Object { $_ -match 'tailwindcss v(\S+)' } | Select-Object -First 1
        if ($line -match 'tailwindcss v(\S+)') { $current = $Matches[1] }
        if ($current) {
            try {
                $latest = (Invoke-RestMethod 'https://api.github.com/repos/tailwindlabs/tailwindcss/releases/latest' -TimeoutSec 4).tag_name -replace '^v',''
                if ($latest -and $latest -ne $current) {
                    $updates += "Tailwind CLI : v$current installe -> v$latest disponible (.\scripts\tailwind.ps1 install pour mettre a jour)"
                }
            } catch {}
        }
    }
    # cloudflared
    if (Test-CommandAvailable 'cloudflared') {
        try {
            $cfCurrent = (& cloudflared --version 2>&1 | Out-String) -replace '[\r\n]',' '
            if ($cfCurrent -match 'version (\S+)') {
                $cfV = $Matches[1]
                $cfLatest = (Invoke-RestMethod 'https://api.github.com/repos/cloudflare/cloudflared/releases/latest' -TimeoutSec 4).tag_name -replace '^v',''
                if ($cfLatest -and $cfLatest -ne $cfV) {
                    $updates += "cloudflared  : v$cfV installe -> v$cfLatest disponible (winget upgrade Cloudflare.cloudflared)"
                }
            }
        } catch {}
    }
    return $updates
}

# ----------------------------------------------------------------------------
# AIDE
# ----------------------------------------------------------------------------
function Show-Help {
    Write-Host @'

  LIUGONG ACADEMY - Task Runner
  ===========================

  Usage : .\makefile.ps1 <task> [options]

  TACHES PRINCIPALES
  ------------------
    start         [RECOMMANDE] Diagnostic 12 points + auto-fix + menu interactif.

                  Pre-flight (auto-fix quand possible) :
                    - uv installe + Python >= 3.11
                    - Profil .env charge (-Profile dev/staging/prod)
                    - Dependances Python (uv sync)
                    - SECRET_KEY auto-genere si vide dans .env
                    - Tailwind CLI + CSS compile a jour
                    - Police Material Symbols
                    - Dossiers uploads/ et logs/ crees
                    - Smoke test : import de l'app sans erreur
                    - Espace disque libre > 500 MB
                    - Etat git (branche + fichiers non commits)
                    - Port libre

                  Apres pre-flight :
                    - Affiche les mises a jour Tailwind / cloudflared
                    - Menu : Dev local / NSSM / Docker
                    - Option pare-feu Windows (NSSM/Docker, UAC)
                    - Option backup uploads/ (NSSM/Docker)
                    - Option Cloudflare Tunnel (Quick / nomme)
                    - Auto-installation Docker / cloudflared (winget) si absent
                    - Healthcheck post-demarrage (NSSM/Docker)
                    - Auto-ouverture du navigateur
                    - Recap : URLs locale/reseau/tunnel + commandes utiles

                  Options de 'start' :
                    -Profile dev|staging|prod  Profil .env (def: dev)
                    -Pull                      git pull avant lancement
                    -Backup                    Backup uploads/ sans demander
                    -NoBrowser                 Ne pas ouvrir le navigateur
                    -NoFirewall                Ne pas configurer le pare-feu
                    -NoChecks                  Saute le pre-flight (debug)

    install       Installe tout (uv sync + Tailwind CLI + build CSS).
                  A lancer une fois apres clone.

    dev           Serveur de developpement (auto-reload).
                  Options: -BindHost 127.0.0.1 -Port 8000
    serve         Serveur production (sans reload, ouvert sur 0.0.0.0).
                  Options: -BindHost 0.0.0.0   -Port 8000
    run           Alias de 'dev'.

  FRONT-END (Tailwind / icones)
  ------------------------------
    build-css     Compile Tailwind en production (minifie ~20 Ko).
    watch-css     Tailwind watch : recompile a chaque modif HTML/JS.
    icons         Re-subset Material Symbols Outlined (apres ajout d'une
                  icone dans scripts/subset_material_symbols.py).

  QUALITE
  --------
    lint          Lance ruff check (si installe).
    format        Lance ruff format (si installe).
    check         lint + verifie que le CSS est a jour.

  UTILITAIRES
  -----------
    clean         Supprime __pycache__, *.pyc et uploads de session.
                  Demande confirmation, utiliser -Force pour passer outre.
    tree          Affiche l'arborescence du projet (profondeur 2).
    info          Affiche les versions des outils (uv, python, tailwind).
    help          Affiche cette aide (par defaut).

  SERVICE NSSM (Windows)
  ----------------------
    nssm-install  Cree ou recree le service 'liugong-academy' (uv + uvicorn).
                  Options: -Port 8000
    nssm-start    Demarre le service s'il est arrete.
    nssm-stop     Arrete le service.
    nssm-restart  Redemarre le service (ou recree si etat casse).
    nssm-status   Affiche le statut NSSM + Windows + chemins des logs.
    nssm-remove   Stoppe et supprime le service (desinstallation).
                  Necessite un terminal en mode administrateur si echec.

  EXEMPLES
  --------
    .\makefile.ps1 start                          # demarrage assiste recommande
    .\makefile.ps1 start -Port 8080
    .\makefile.ps1 start -Profile prod -Pull -Backup
    .\makefile.ps1 start -NoBrowser -NoFirewall   # mode silencieux/CI
    .\makefile.ps1 install
    .\makefile.ps1 dev
    .\makefile.ps1 serve -BindHost 0.0.0.0 -Port 8000
    .\makefile.ps1 watch-css
    .\makefile.ps1 clean -Force
    .\makefile.ps1 nssm-install -Port 8000
    .\makefile.ps1 nssm-status
    .\makefile.ps1 nssm-restart
    .\makefile.ps1 nssm-remove

'@ -ForegroundColor White
}

# ----------------------------------------------------------------------------
# TASKS
# ----------------------------------------------------------------------------

function Task-Install {
    Write-Title "Installation LiuGong Academy"
    Assert-Uv

    Write-Step "1/3 Synchronisation des dependances Python (uv sync)..."
    & uv sync
    if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec uv sync"; exit $LASTEXITCODE }

    Write-Step "2/3 Tailwind CLI (telechargement si absent + build production)..."
    & "$ProjectRoot\scripts\tailwind.ps1" install
    & "$ProjectRoot\scripts\tailwind.ps1" build

    Write-Step "3/3 Material Symbols Outlined..."
    if (Test-Path "$ProjectRoot\app\static\fonts\MaterialSymbolsOutlined.woff2") {
        Write-Info2 "Police deja presente : app\static\fonts\MaterialSymbolsOutlined.woff2"
    } else {
        Write-Warn "Police manquante. Telechargez-la une fois depuis Google :"
        Write-Info2 "  Voir scripts\subset_material_symbols.py pour la procedure."
    }

    Write-Ok "Installation terminee. Lancez : .\makefile.ps1 dev"
}

function Task-Dev {
    param([string]$VHost, [int]$VPort)
    Write-Title "Serveur de developpement"
    Assert-Uv
    if (Test-CssNeedsRebuild) {
        Write-Warn "CSS Tailwind desynchronise (templates plus recents) - recompilation..."
        & "$ProjectRoot\scripts\tailwind.ps1" build
        if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec compilation CSS"; return }
    }
    Write-Info2 "URL : http://${VHost}:${VPort}"
    Write-Info2 "Auto-reload actif. Ctrl+C pour arreter."
    Write-Host ""
    & uv run uvicorn app.main:app --reload --host $VHost --port $VPort
}

function Task-Serve {
    param([string]$VHost, [int]$VPort)
    Write-Title "Serveur production"
    Assert-Uv
    if ($VHost -eq '127.0.0.1') { $VHost = '0.0.0.0' }
    Write-Info2 "URL : http://${VHost}:${VPort}  (accessible sur le reseau)"
    Write-Info2 "Ctrl+C pour arreter."
    Write-Host ""
    & uv run uvicorn app.main:app --host $VHost --port $VPort
}

function Task-BuildCss {
    & "$ProjectRoot\scripts\tailwind.ps1" build
}

function Task-WatchCss {
    & "$ProjectRoot\scripts\tailwind.ps1" watch
}

function Task-Icons {
    Write-Title "Subset Material Symbols Outlined"
    Assert-Uv
    & uv run python "$ProjectRoot\scripts\subset_material_symbols.py"
}

function Task-Lint {
    Write-Title "Lint (ruff)"
    Assert-Uv
    & uv run ruff check .
}

function Task-Format {
    Write-Title "Format (ruff)"
    Assert-Uv
    & uv run ruff format .
}

function Task-Check {
    Task-Lint
    Write-Step "Re-build CSS pour verifier qu'il est a jour..."
    Task-BuildCss
}

function Task-Clean {
    param([switch]$DoForce)
    Write-Title "Nettoyage"
    if (-not $DoForce) {
        Write-Warn "Cette commande va supprimer :"
        Write-Info2 "  - Tous les dossiers __pycache__/"
        Write-Info2 "  - Tous les fichiers *.pyc et *.pyo"
        Write-Info2 "  - Tous les fichiers dans app/static/uploads/ (sauf .gitkeep)"
        Write-Info2 "  - Le dossier .pytest_cache et .ruff_cache si presents"
        Write-Host ""
        Write-Err2 "Relancer avec -Force pour confirmer : .\makefile.ps1 clean -Force"
        return
    }

    Write-Step "Suppression des __pycache__/..."
    $pycaches = Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue
    foreach ($d in $pycaches) { Remove-Item -Path $d.FullName -Recurse -Force }
    Write-Info2 "  $($pycaches.Count) dossier(s) supprime(s)"

    Write-Step "Suppression des *.pyc / *.pyo..."
    $pyc = Get-ChildItem -Path $ProjectRoot -File -Recurse -Include "*.pyc","*.pyo" -ErrorAction SilentlyContinue
    foreach ($f in $pyc) { Remove-Item -Path $f.FullName -Force }
    Write-Info2 "  $($pyc.Count) fichier(s) supprime(s)"

    Write-Step "Nettoyage app/static/uploads/..."
    $uploadsDir = Join-Path $ProjectRoot "app\static\uploads"
    if (Test-Path $uploadsDir) {
        Get-ChildItem -Path $uploadsDir -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne '.gitkeep' } |
            ForEach-Object { Remove-Item -Path $_.FullName -Recurse -Force }
        Write-Info2 "  uploads vide (sauf .gitkeep)"
    }

    Write-Step "Suppression des caches d'outils..."
    foreach ($cache in '.pytest_cache', '.ruff_cache', '.mypy_cache') {
        $p = Join-Path $ProjectRoot $cache
        if (Test-Path $p) { Remove-Item -Path $p -Recurse -Force; Write-Info2 "  $cache supprime" }
    }

    Write-Ok "Nettoyage termine"
}

function Task-Tree {
    Write-Title "Arborescence (profondeur 2)"
    $exclude = @('__pycache__', '.git', '.venv', 'node_modules', '.pytest_cache', '.ruff_cache', 'uploads')
    function Show-Tree {
        param([string]$Path, [int]$Depth, [string]$Prefix = '')
        if ($Depth -lt 0) { return }
        $items = Get-ChildItem -Path $Path -Force -ErrorAction SilentlyContinue |
                 Where-Object { $exclude -notcontains $_.Name -and $_.Name -notmatch '^\.' -or $_.Name -in '.env.example','.gitignore' } |
                 Sort-Object @{e='PSIsContainer';desc=$true}, Name
        $count = $items.Count
        for ($i = 0; $i -lt $count; $i++) {
            $item = $items[$i]
            $isLast = ($i -eq $count - 1)
            $branch = if ($isLast) { '+--' } else { '+--' }
            $line   = "$Prefix$branch $($item.Name)"
            if ($item.PSIsContainer) { $line += '/' }
            Write-Host $line
            if ($item.PSIsContainer -and $Depth -gt 0) {
                $newPrefix = if ($isLast) { "$Prefix    " } else { "$Prefix|   " }
                Show-Tree -Path $item.FullName -Depth ($Depth - 1) -Prefix $newPrefix
            }
        }
    }
    Show-Tree -Path $ProjectRoot -Depth 2
}

function Invoke-PreflightChecks {
    <#
    .SYNOPSIS
    Diagnostique l'environnement et corrige automatiquement ce qui peut l'etre.
    Retourne $true si tout est pret, $false sinon.
    #>
    Write-Title "Pre-flight - Verification de l'environnement"

    # 1. uv ------------------------------------------------------------------
    Write-Step "1/12  uv (gestionnaire Python)..."
    $uvPath = Resolve-Uv
    if (-not $uvPath) {
        Write-Warn "uv n'est pas installe (et introuvable dans les emplacements standards)."
        $answer = Read-Choice -Prompt "Voulez-vous l'installer maintenant ? (script officiel Astral) [O/n]" -Choices @('o','n') -Default 'o'
        if ($answer -eq 'o' -or $answer -eq 'oui' -or $answer -eq 'y' -or $answer -eq 'yes') {
            if (-not (Install-Uv)) {
                Write-Info2 "  Installation manuelle : powershell -c `"irm https://astral.sh/uv/install.ps1 | iex`""
                Write-Info2 "  Puis fermez ET rouvrez PowerShell pour rafraichir le PATH."
                return $false
            }
            $uvPath = Resolve-Uv
        } else {
            Write-Info2 "  Installer manuellement : powershell -c `"irm https://astral.sh/uv/install.ps1 | iex`""
            return $false
        }
    }
    Write-Ok "$(& $uvPath --version 2>&1 | Select-Object -First 1)  ($uvPath)"

    # 2. Profil .env (K) -----------------------------------------------------
    Write-Step "2/12  Profil .env ($Profile)..."
    $resolved = Resolve-EnvFile -ProfileName $Profile
    if ($resolved.Loaded) {
        Write-Ok ".env charge depuis $($resolved.From)"
    } elseif (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Ok ".env cree depuis .env.example (profil '$Profile' non trouve)"
        } else {
            Write-Warn ".env absent et .env.example introuvable"
        }
    } else {
        Write-Ok ".env present (profil '$Profile' non trouve, .env standard utilise)"
    }

    # 3. Dependances Python --------------------------------------------------
    Write-Step "3/12  Dependances Python (uv sync)..."
    & uv sync --quiet
    if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec uv sync"; return $false }
    Write-Ok "Environnement Python synchronise"

    # 4. Version Python (A) --------------------------------------------------
    Write-Step "4/12  Version Python..."
    $py = Test-PythonVersion
    if (-not $py.Ok) {
        Write-Err2 "Python $($py.Version) detecte. Le projet requiert >= 3.11."
        Write-Info2 "  uv installe automatiquement la bonne version :"
        Write-Info2 "    uv python install 3.11"
        return $false
    }
    Write-Ok "Python $($py.Version)"

    # 5. SECRET_KEY (C) ------------------------------------------------------
    Write-Step "5/12  Cle secrete (.env)..."
    if (Initialize-SecretKey) {
        Write-Ok "SECRET_KEY genere automatiquement (32 octets hex)"
    } else {
        Write-Ok "SECRET_KEY non requis ou deja defini"
    }

    # 6. Tailwind CLI --------------------------------------------------------
    Write-Step "6/12  Tailwind CLI (binaire local)..."
    $bin = Join-Path $ProjectRoot 'tools\tailwindcss.exe'
    if (-not (Test-Path $bin)) {
        Write-Info2 "  Tailwind CLI absent, telechargement..."
        & "$ProjectRoot\scripts\tailwind.ps1" install
        if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec telechargement Tailwind"; return $false }
    }
    Write-Ok "Tailwind CLI present"

    # 7. CSS compile a jour --------------------------------------------------
    Write-Step "7/12  CSS Tailwind compile..."
    if (Test-CssNeedsRebuild) {
        Write-Info2 "  CSS desynchronise (templates plus recents), recompilation..."
        & "$ProjectRoot\scripts\tailwind.ps1" build
        if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec compilation CSS"; return $false }
    }
    $cssSize = [Math]::Round((Get-Item "app\static\css\tailwind.css").Length / 1KB, 1)
    Write-Ok "CSS a jour ($cssSize Ko)"

    # 8. Police Material Symbols ---------------------------------------------
    Write-Step "8/12  Police Material Symbols Outlined..."
    $font = Join-Path $ProjectRoot 'app\static\fonts\MaterialSymbolsOutlined.woff2'
    if (-not (Test-Path $font)) {
        Write-Warn "Police absente : les icones afficheront leur nom (ex: 'menu_book')."
        Write-Info2 "  Telecharger depuis Google Fonts puis : .\makefile.ps1 icons"
    } else {
        $fontSize = [Math]::Round((Get-Item $font).Length / 1KB, 1)
        Write-Ok "Police presente ($fontSize Ko)"
    }

    # 9. Dossiers uploads + logs (D) -----------------------------------------
    Write-Step "9/12  Dossiers de runtime (uploads, logs)..."
    $uploads = Join-Path $ProjectRoot 'app\static\uploads'
    if (-not (Test-Path $uploads)) {
        New-Item -ItemType Directory -Path $uploads -Force | Out-Null
        New-Item -ItemType File -Path (Join-Path $uploads '.gitkeep') -Force | Out-Null
        Write-Info2 "  uploads/ cree"
    }
    if (Initialize-LogsFolder) {
        Write-Info2 "  logs/ cree"
    }
    Write-Ok "uploads/ et logs/ OK"

    # 10. Smoke test d'import (B) --------------------------------------------
    Write-Step "10/12  Smoke test - import de l'application..."
    $smoke = Test-AppImport
    if (-not $smoke.Ok) {
        Write-Err2 "Erreur d'import detectee :"
        Write-Host $smoke.Output -ForegroundColor Red
        Write-Info2 "  Corrigez l'erreur ci-dessus avant de demarrer le serveur."
        return $false
    }
    Write-Ok "app.main:app importe sans erreur"

    # 11. Espace disque + git status (E + F) ---------------------------------
    Write-Step "11/12  Espace disque et etat git..."
    $disk = Test-DiskSpace -MinMB 500
    if ($disk.FreeMB -ge 0) {
        if ($disk.Ok) {
            Write-Ok "Disque $($disk.Drive): : $($disk.FreeMB) MB libres"
        } else {
            Write-Warn "Disque $($disk.Drive): : seulement $($disk.FreeMB) MB libres (uploads/PDF risquent de saturer)"
        }
    }
    $git = Test-GitClean
    if ($git.Available -and $git.InRepo) {
        if ($git.Clean) {
            Write-Info2 "  Git    : branche '$($git.Branch)', repo propre"
        } else {
            Write-Warn "Git : $($git.Files) fichier(s) non commit(s) sur '$($git.Branch)'"
            Write-Info2 "    git status   pour voir le detail"
        }
    }

    # 12. Port disponible ----------------------------------------------------
    Write-Step "12/12  Disponibilite du port $Port..."
    if (Test-PortFree -VPort $Port) {
        Write-Ok "Port $Port libre"
    } else {
        Write-Warn "Port $Port deja utilise. Le serveur risque de ne pas demarrer."
        Write-Info2 "  Trouver le processus : Get-NetTCPConnection -LocalPort $Port | Select-Object OwningProcess"
    }

    return $true
}

function Show-LaunchMenu {
    Write-Title "Mode de demarrage"
    Write-Host ""
    Write-Host "  1) Dev local      " -ForegroundColor White -NoNewline
    Write-Host "uvicorn --reload, recommande pour developper" -ForegroundColor Gray
    Write-Host "  2) Service NSSM   " -ForegroundColor White -NoNewline
    Write-Host "Service Windows permanent (auto au boot)" -ForegroundColor Gray
    Write-Host "  3) Docker         " -ForegroundColor White -NoNewline
    Write-Host "Image + container isole, portable" -ForegroundColor Gray
    Write-Host "  q) Quitter        " -ForegroundColor Gray
    Write-Host ""
    return (Read-Choice -Prompt "Votre choix" -Default '1' -Choices @('1','2','3','q'))
}

function Start-DevLocal {
    Write-Title "Lancement en mode dev local"
    Write-Info2 "URL : http://${BindHost}:${Port}"
    Write-Info2 "Auto-reload actif. Ctrl+C pour arreter."
    Write-Host ""
    & uv run uvicorn app.main:app --reload --host $BindHost --port $Port
}

function Start-NssmMode {
    Write-Title "Lancement en service NSSM"

    if (-not (Test-NssmAvailable)) { return }

    $serviceName = $NssmServiceName
    Write-Info2 "Nom du service : $serviceName"

    # Detection si service existe
    $status = (& nssm status $serviceName 2>$null) | Out-String
    $status = $status.Trim()
    $serviceExists = ($LASTEXITCODE -eq 0 -and $status)

    # Etats consideres "casses" : ne peuvent pas etre redemarres simplement,
    # il faut detruire + recreer (NSSM met SERVICE_PAUSED apres trop de
    # crashes consecutifs, p.ex.).
    $brokenStates = @('SERVICE_PAUSED', 'SERVICE_PAUSE_PENDING', 'SERVICE_DISABLED')
    $isBroken = $brokenStates -contains $status

    if ($serviceExists -and $isBroken) {
        Write-Warn "Service existant en etat '$status' (recreation requise)."
        $action = Read-Choice -Prompt "(r)ecreer (supprime + recree) / (s)top / (q)uitter" -Default 'r' -Choices @('r','s','q')
    } elseif ($serviceExists) {
        Write-Info2 "Service existant - statut : $status"
        $action = Read-Choice -Prompt "(r)estart / (s)top / (c)recreer (supprime + recree) / (q)uitter" -Default 'r' -Choices @('r','s','c','q')
    } else {
        Write-Info2 "Service absent."
        $confirm = Read-Choice -Prompt "Creer le service maintenant ? (o/n)" -Default 'o' -Choices @('o','n')
        if ($confirm -ne 'o') { return }
        Install-NssmService -ServiceName $serviceName
        $action = 'created'
    }

    switch ($action) {
        'r' {
            # Tentative de redemarrage simple (service en bon etat)
            & nssm restart $serviceName 2>&1 | Out-Null
            Start-Sleep -Seconds 2
            $newStatus = ((& nssm status $serviceName 2>$null) | Out-String).Trim()
            if ($newStatus -eq 'SERVICE_RUNNING') {
                Write-Ok "Service redemarre (statut : $newStatus)"
            } else {
                Write-Warn "Redemarrage echoue (statut : $newStatus). Bascule en recreation..."
                Install-NssmService -ServiceName $serviceName  # interne stop+remove+create
            }
        }
        's' {
            & nssm stop $serviceName 2>&1 | Out-Null
            Write-Ok "Service arrete"
        }
        'c' {
            # Reconfiguration explicite : supprimer + recreer (idempotent)
            Install-NssmService -ServiceName $serviceName
        }
        'q' { return }
        'created' { }  # rien a faire, deja cree au-dessus
    }

    Write-Host ""
    Write-Info2 "Acceder au service :"
    Write-Info2 "  Etat       : .\makefile.ps1 nssm-status"
    Write-Info2 "  Logs       : Get-Content logs\$NssmServiceName.out.log -Tail 50 -Wait"
    Write-Info2 "  Stop       : .\makefile.ps1 nssm-stop"
    Write-Info2 "  Restart    : .\makefile.ps1 nssm-restart"
    Write-Info2 "  Recreer    : .\makefile.ps1 nssm-install"
    Write-Info2 "  Desinstall : .\makefile.ps1 nssm-remove"
}

function Install-NssmService {
    <#
    .SYNOPSIS
    Cree (ou recree) le service NSSM 'liugong-academy' de zero.
    .DESCRIPTION
    Strategie : toujours supprimer le service existant (s'il y en a un) avant
    de le recreer. C'est plus fiable que `nssm set ...` en place car cela
    nettoie tout etat residuel (Paused, Disabled, mauvais ObjectName, etc.).
    Le service tourne sous LocalSystem et utilise tools\uv.exe (copie locale)
    comme Application, ce qui le rend self-contained.
    #>
    param(
        [string]$ServiceName
    )

    # 1. Localiser uv.exe (PATH ou emplacements standards)
    $uvSource = Resolve-Uv
    if (-not $uvSource) {
        throw "uv introuvable. Installez-le via : powershell -c `"irm https://astral.sh/uv/install.ps1 | iex`""
    }

    # 2. Copier uv.exe dans tools\ pour que le service soit self-contained
    #    (evite tout probleme de profil utilisateur, droits sur %USERPROFILE%
    #    pour LocalSystem, mauvais PATH apres install, etc.)
    $toolsDir = Join-Path $ProjectRoot 'tools'
    if (-not (Test-Path $toolsDir)) {
        New-Item -ItemType Directory -Path $toolsDir | Out-Null
    }
    $uvLocal = Join-Path $toolsDir 'uv.exe'
    $needsCopy = $true
    if (Test-Path $uvLocal) {
        # Re-copie uniquement si la source est plus recente
        $needsCopy = (Get-Item $uvSource).LastWriteTime -gt (Get-Item $uvLocal).LastWriteTime
    }
    if ($needsCopy) {
        Copy-Item -LiteralPath $uvSource -Destination $uvLocal -Force
        Write-Info2 "uv.exe copie dans tools\ (service self-contained)"
    }
    $uvExe = $uvLocal

    # 3. Logs (logs/ + reinit si > 5 Mo)
    $logsDir = Join-Path $ProjectRoot 'logs'
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir | Out-Null
    }
    $stdout = Join-Path $logsDir "$ServiceName.out.log"
    $stderr = Join-Path $logsDir "$ServiceName.err.log"

    # 4. TOUJOURS supprimer le service existant avant de le recreer.
    #    Plus robuste que `nssm set` en place : nettoie les etats residuels
    #    (Paused, Disabled, ObjectName errone, AppDirectory obsolete, etc.).
    $existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Step "Suppression du service existant '$ServiceName' (statut : $($existing.Status))..."
        & nssm stop   $ServiceName 2>&1 | Out-Null
        Start-Sleep -Milliseconds 800
        & nssm remove $ServiceName confirm 2>&1 | Out-Null
        Start-Sleep -Milliseconds 800

        # Verification : si le service est toujours la, on echoue clairement.
        $still = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($still) {
            throw "Impossible de supprimer le service '$ServiceName'. Lancez PowerShell en mode administrateur et relancez."
        }
        Write-Ok "Ancien service supprime"
    }

    # 5. Creation du service avec tous les parametres.
    Write-Step "Creation du service NSSM..."
    & nssm install $ServiceName $uvExe | Out-Null

    & nssm set $ServiceName Application    $uvExe        | Out-Null
    & nssm set $ServiceName AppDirectory   $ProjectRoot  | Out-Null
    & nssm set $ServiceName AppParameters  "run uvicorn app.main:app --host 0.0.0.0 --port $Port" | Out-Null
    & nssm set $ServiceName AppStdout      $stdout       | Out-Null
    & nssm set $ServiceName AppStderr      $stderr       | Out-Null
    & nssm set $ServiceName AppStdoutCreationDisposition 2 | Out-Null
    & nssm set $ServiceName AppStderrCreationDisposition 2 | Out-Null
    & nssm set $ServiceName Start          SERVICE_AUTO_START | Out-Null
    & nssm set $ServiceName ObjectName     LocalSystem   | Out-Null

    # Anti-throttling : NSSM met le service en Paused s'il redemarre en
    # boucle trop vite. On laisse 10s entre tentatives + 60s de stabilisation
    # avant de considerer un crash comme "throttle".
    & nssm set $ServiceName AppRestartDelay  10000 | Out-Null
    & nssm set $ServiceName AppThrottle      60000 | Out-Null
    & nssm set $ServiceName AppExit Default Restart | Out-Null

    & nssm set $ServiceName DisplayName    $AppDisplayName | Out-Null
    & nssm set $ServiceName Description    $AppServiceDescription | Out-Null

    # 6. Demarrage et polling du statut (jusqu'a SERVICE_RUNNING ou timeout 30s)
    & nssm start $ServiceName 2>&1 | Out-Null
    $deadline = (Get-Date).AddSeconds(30)
    $svcStatus = ''
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $svcStatus = ((& nssm status $ServiceName 2>$null) | Out-String).Trim()
        if ($svcStatus -eq 'SERVICE_RUNNING' -or
            $svcStatus -eq 'SERVICE_STOPPED' -or
            $svcStatus -eq 'SERVICE_PAUSED') { break }
    }
    if ($svcStatus -eq 'SERVICE_RUNNING') {
        Write-Ok "Service '$ServiceName' cree et demarre sur le port $Port"
    } else {
        Write-Warn "Service cree mais statut = $svcStatus apres 30s."
        Write-Info2 "  Verifiez les logs : Get-Content logs\$ServiceName.err.log -Tail 50"
    }
    Write-Info2 "URL : http://localhost:$Port  (et reseau via http://0.0.0.0:$Port)"
    Write-Info2 "Logs : logs\$ServiceName.out.log  /  logs\$ServiceName.err.log"
}

function Remove-NssmService {
    param([string]$ServiceName = $NssmServiceName)

    Write-Title "Suppression du service NSSM '$ServiceName'"

    if (-not (Test-NssmAvailable)) { return }

    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Info2 "Service '$ServiceName' inexistant, rien a faire."
        return
    }

    Write-Info2 "Statut actuel : $($svc.Status)"
    Write-Step "Stop..."
    & nssm stop $ServiceName 2>&1 | Out-Null
    Start-Sleep -Milliseconds 800
    Write-Step "Remove..."
    & nssm remove $ServiceName confirm 2>&1 | Out-Null
    Start-Sleep -Milliseconds 500

    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Ok "Service '$ServiceName' supprime."
    } else {
        Write-Err2 "Echec : le service est toujours present (statut=$($svc.Status))."
        Write-Info2 "  Tentez en mode admin : .\makefile.ps1 nssm-remove"
    }
}

function Task-NssmStatus {
    param([string]$ServiceName = $NssmServiceName)

    Assert-Nssm
    Write-Title "Statut NSSM - $ServiceName"

    if (-not (Test-NssmServiceRegistered $ServiceName)) {
        Write-Warn "Service '$ServiceName' absent ou non enregistre dans NSSM."
        Write-Info2 "  Creer : .\makefile.ps1 nssm-install"
        return
    }

    $status = Get-NssmServiceStatus $ServiceName
    Write-Ok "NSSM : $status"
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($svc) { Write-Info2 "Windows : $($svc.Status)" }
    Write-Info2 "URL  : http://localhost:$Port/"
    Write-Info2 "Logs : logs\$ServiceName.out.log"
    Write-Info2 "       logs\$ServiceName.err.log"
}

function Task-NssmStart {
    param([string]$ServiceName = $NssmServiceName)

    Assert-Nssm
    Write-Title "Demarrage NSSM - $ServiceName"

    if (-not (Test-NssmServiceRegistered $ServiceName)) {
        Write-Err2 "Service '$ServiceName' introuvable."
        Write-Info2 "  Creer : .\makefile.ps1 nssm-install"
        exit 1
    }

    $before = Get-NssmServiceStatus $ServiceName
    if ($before -eq 'SERVICE_RUNNING') {
        Write-Ok "Service deja en cours d'execution."
        return
    }

    Write-Step "Demarrage..."
    & nssm start $ServiceName 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    $after = Get-NssmServiceStatus $ServiceName
    if ($after -eq 'SERVICE_RUNNING') {
        Write-Ok "Service demarre (statut : $after)"
        Write-Info2 "URL : http://localhost:$Port/"
    } else {
        Write-Warn "Statut apres demarrage : $after"
        Write-Info2 "  Verifiez : .\makefile.ps1 nssm-status"
        Write-Info2 "  Logs     : Get-Content logs\$ServiceName.err.log -Tail 50"
        exit 1
    }
}

function Task-NssmStop {
    param([string]$ServiceName = $NssmServiceName)

    Assert-Nssm
    Write-Title "Arret NSSM - $ServiceName"

    if (-not (Test-NssmServiceRegistered $ServiceName)) {
        Write-Warn "Service '$ServiceName' absent, rien a faire."
        return
    }

    $before = Get-NssmServiceStatus $ServiceName
    if ($before -eq 'SERVICE_STOPPED') {
        Write-Ok "Service deja arrete."
        return
    }

    Write-Step "Arret..."
    & nssm stop $ServiceName 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    $after = Get-NssmServiceStatus $ServiceName
    if ($after -eq 'SERVICE_STOPPED') {
        Write-Ok "Service arrete."
    } else {
        Write-Warn "Statut apres arret : $after"
    }
}

function Task-NssmRestart {
    param([string]$ServiceName = $NssmServiceName)

    Assert-Nssm
    Write-Title "Redemarrage NSSM - $ServiceName"

    if (-not (Test-NssmServiceRegistered $ServiceName)) {
        Write-Err2 "Service '$ServiceName' introuvable."
        Write-Info2 "  Creer : .\makefile.ps1 nssm-install"
        exit 1
    }

    $before = Get-NssmServiceStatus $ServiceName
    $brokenStates = @('SERVICE_PAUSED', 'SERVICE_PAUSE_PENDING', 'SERVICE_DISABLED')
    if ($brokenStates -contains $before) {
        Write-Warn "Service en etat '$before' - recreation via nssm-install..."
        Assert-Uv
        Install-NssmService -ServiceName $ServiceName
        return
    }

    Write-Step "Redemarrage..."
    & nssm restart $ServiceName 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    $after = Get-NssmServiceStatus $ServiceName
    if ($after -eq 'SERVICE_RUNNING') {
        Write-Ok "Service redemarre (statut : $after)"
        Write-Info2 "URL : http://localhost:$Port/"
    } else {
        Write-Warn "Redemarrage echoue (statut : $after). Recreation..."
        Assert-Uv
        Install-NssmService -ServiceName $ServiceName
    }
}

function Task-NssmInstall {
    Assert-Uv
    Assert-Nssm
    Install-NssmService -ServiceName $NssmServiceName
}

function Test-DockerReady {
    <#
    .SYNOPSIS
    Verifie si Docker est utilisable. Retourne un objet avec
    .Ready (bool) et .Reason (string : 'ok' / 'not-installed' / 'daemon-stopped').
    #>
    if (-not (Test-CommandAvailable 'docker')) {
        return [PSCustomObject]@{ Ready = $false; Reason = 'not-installed' }
    }
    & docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        return [PSCustomObject]@{ Ready = $false; Reason = 'daemon-stopped' }
    }
    return [PSCustomObject]@{ Ready = $true; Reason = 'ok' }
}

function Update-SessionPath {
    <#
    Refresh du PATH apres installation par winget (winget met a jour la
    variable systeme mais pas la session courante).
    #>
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path', 'User')
}

function Install-DockerDesktop {
    Write-Step "Tentative d'installation automatique de Docker Desktop..."

    if (Test-CommandAvailable 'winget') {
        Write-Info2 "  winget detecte. Installation en cours (peut prendre quelques minutes)..."
        & winget install --id Docker.DockerDesktop -e `
            --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Docker Desktop installe."
            Update-SessionPath
            Write-Host ""
            Write-Warn "IMPORTANT : Docker Desktop necessite un redemarrage de Windows."
            Write-Info2 "  1. Redemarrez Windows."
            Write-Info2 "  2. Lancez Docker Desktop depuis le menu Demarrer."
            Write-Info2 "  3. Attendez que l'icone systray soit verte."
            Write-Info2 "  4. Relancez : .\makefile.ps1 start"
            return $true
        }
        Write-Warn "  winget a echoue (code $LASTEXITCODE)."
    } else {
        Write-Info2 "  winget non disponible (Windows 10 < 1809 ou App Installer absent)."
    }

    Write-Host ""
    Write-Err2 "Installation automatique impossible."
    Write-Info2 "  Telechargez Docker Desktop manuellement :"
    Write-Info2 "    https://docs.docker.com/desktop/install/windows-install/"
    Write-Info2 "  Apres installation, redemarrez Windows puis : .\makefile.ps1 start"
    return $false
}

function Start-DockerMode {
    Write-Title "Lancement Docker"

    $check = Test-DockerReady
    if (-not $check.Ready) {
        switch ($check.Reason) {
            'not-installed' {
                Write-Err2 "Docker Desktop n'est pas installe sur cette machine."
                Write-Host ""
                $do = Read-Choice -Prompt "Tenter une installation automatique maintenant ? (o/n)" -Default 'o' -Choices @('o','n')
                if ($do -eq 'o') {
                    Install-DockerDesktop | Out-Null
                } else {
                    Write-Info2 "  Lien : https://docs.docker.com/desktop/install/windows-install/"
                }
                return
            }
            'daemon-stopped' {
                Write-Err2 "Docker est installe mais le daemon n'est pas demarre."
                Write-Info2 "  -> Lancez Docker Desktop depuis le menu Demarrer."
                Write-Info2 "  -> Attendez que l'icone systray devienne verte (jusqu'a 30s)."
                Write-Info2 "  -> Puis relancez : .\makefile.ps1 start"
                return
            }
        }
    }

    if (-not (Test-Path "Dockerfile")) {
        Write-Err2 "Dockerfile introuvable a la racine du projet."
        return
    }

    $imageName  = $DockerImageName
    $container  = $DockerContainerName

    # Image deja construite ?
    $imgExists = (& docker images -q $imageName 2>$null)
    if (-not $imgExists) {
        Write-Step "Image inexistante - build..."
        & docker build -t $imageName .
        if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec docker build"; return }
        Write-Ok "Image '$imageName' construite"
    } else {
        $rebuild = Read-Choice -Prompt "Image deja construite. Rebuild ? (o/n)" -Default 'n' -Choices @('o','n')
        if ($rebuild -eq 'o') {
            & docker build -t $imageName .
            if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec docker build"; return }
            Write-Ok "Image '$imageName' reconstruite"
        }
    }

    # Container deja en cours ?
    $running = (& docker ps -q -f "name=^${container}$" 2>$null)
    if ($running) {
        Write-Info2 "Container '$container' deja en cours d'execution."
        $action = Read-Choice -Prompt "(r)estart / (s)top / (l)ogs / (q)uitter" -Default 'l' -Choices @('r','s','l','q')
        switch ($action) {
            'r' { & docker restart $container | Out-Null; Write-Ok "Container redemarre" }
            's' { & docker stop    $container | Out-Null; Write-Ok "Container arrete" }
            'l' { & docker logs -f --tail 50 $container }
            'q' { return }
        }
        return
    }

    # Container existe mais arrete ?
    $existing = (& docker ps -aq -f "name=^${container}$" 2>$null)
    if ($existing) {
        Write-Info2 "Container '$container' existe (arrete) - redemarrage..."
        & docker start $container | Out-Null
    } else {
        Write-Step "Creation et demarrage du container..."
        & docker run -d `
            --name $container `
            -p "${Port}:8000" `
            --restart unless-stopped `
            -v "${ProjectRoot}\app\static\uploads:/app/app/static/uploads" `
            $imageName | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec docker run"; return }
    }

    Write-Ok "Container '$container' lance sur http://localhost:$Port"
    Write-Host ""
    Write-Info2 "Commandes utiles :"
    Write-Info2 "  docker logs -f $container        (suivre les logs)"
    Write-Info2 "  docker stop    $container        (arreter)"
    Write-Info2 "  docker restart $container        (redemarrer)"
    Write-Info2 "  docker rm -f   $container        (supprimer)"
}

# =============================================================================
# CLOUDFLARED — Tunnels Cloudflare
# =============================================================================

function Install-Cloudflared {
    Write-Step "Tentative d'installation automatique de cloudflared..."

    if (Test-CommandAvailable 'winget') {
        Write-Info2 "  winget detecte. Installation en cours..."
        & winget install --id Cloudflare.cloudflared -e `
            --accept-package-agreements --accept-source-agreements 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            Update-SessionPath
            if (Test-CommandAvailable 'cloudflared') {
                Write-Ok "cloudflared installe."
                return $true
            }
        }
        Write-Warn "  winget a echoue ou cloudflared toujours absent du PATH."
    } else {
        Write-Info2 "  winget non disponible."
    }

    Write-Host ""
    Write-Err2 "Installation automatique impossible."
    Write-Info2 "  Telechargez le binaire manuellement (Windows x64) :"
    Write-Info2 "    https://github.com/cloudflare/cloudflared/releases/latest"
    Write-Info2 "    -> cloudflared-windows-amd64.exe"
    Write-Info2 "  Renommez en 'cloudflared.exe' et placez dans un dossier du PATH"
    Write-Info2 "  (ex: C:\Windows\System32 ou C:\cloudflared\), puis relancez."
    return $false
}

function Start-CloudflaredTunnel {
    param([int]$VPort)

    Write-Title "Configuration Cloudflare Tunnel"

    if (-not (Test-CommandAvailable 'cloudflared')) {
        Write-Warn "cloudflared n'est pas installe sur cette machine."
        Write-Host ""
        $do = Read-Choice -Prompt "Tenter une installation automatique ? (o/n)" -Default 'o' -Choices @('o','n')
        if ($do -ne 'o') {
            Write-Info2 "  Lien : https://github.com/cloudflare/cloudflared/releases/latest"
            return
        }
        if (-not (Install-Cloudflared)) { return }
    } else {
        Write-Ok "cloudflared detecte"
    }

    Write-Host ""
    Write-Info2 "Modes disponibles :"
    Write-Host "  1) Quick Tunnel  " -ForegroundColor White -NoNewline
    Write-Host "URL aleatoire trycloudflare.com (pas de compte requis)" -ForegroundColor Gray
    Write-Host "  2) Tunnel nomme  " -ForegroundColor White -NoNewline
    Write-Host "Domaine personnalise persistant (production, demande compte CF)" -ForegroundColor Gray
    Write-Host "  q) Annuler" -ForegroundColor Gray
    Write-Host ""

    $choice = Read-Choice -Prompt "Votre choix" -Default '1' -Choices @('1','2','q')
    Write-Host ""

    switch ($choice) {
        '1' { Start-QuickTunnel    -VPort $VPort }
        '2' { Start-NamedTunnel    -VPort $VPort }
        'q' { Write-Info2 "Annule." }
    }
}

function Start-QuickTunnel {
    param([int]$VPort)
    Write-Title "Quick Tunnel"
    Write-Info2 "Lancement de cloudflared dans une nouvelle fenetre PowerShell."
    Write-Info2 "L'URL trycloudflare.com s'affichera apres quelques secondes -"
    Write-Info2 "copiez-la pour la partager (valable jusqu'a la fermeture de la fenetre)."
    Write-Host ""

    $cmd = "Write-Host 'Cloudflare Quick Tunnel - port $VPort' -ForegroundColor Cyan; " +
           "Write-Host 'Ctrl+C ou fermer la fenetre pour arreter le tunnel.' -ForegroundColor Yellow; " +
           "Write-Host ''; cloudflared tunnel --url http://localhost:$VPort"

    Start-Process -FilePath 'powershell.exe' `
                  -ArgumentList @('-NoExit', '-Command', $cmd) `
                  -WorkingDirectory $ProjectRoot

    Write-Ok "Tunnel lance dans une nouvelle fenetre."
}

function Start-NamedTunnel {
    param([int]$VPort)
    Write-Title "Tunnel nomme (production)"

    Write-Info2 "Cette procedure necessite :"
    Write-Info2 "  - Un compte Cloudflare (gratuit) avec un domaine deja ajoute"
    Write-Info2 "  - Une etape interactive d'authentification dans le navigateur"
    Write-Host ""
    $confirm = Read-Choice -Prompt "Continuer ? (o/n)" -Default 'o' -Choices @('o','n')
    if ($confirm -ne 'o') { return }

    $cfDir = Join-Path $env:USERPROFILE '.cloudflared'
    if (-not (Test-Path $cfDir)) { New-Item -ItemType Directory -Path $cfDir -Force | Out-Null }

    # ---- 1/4 : login ----
    $certPath = Join-Path $cfDir 'cert.pem'
    if (-not (Test-Path $certPath)) {
        Write-Step "1/4 Authentification Cloudflare..."
        Write-Info2 "  Une page web va s'ouvrir : choisissez le domaine concerne."
        & cloudflared tunnel login
        if (-not (Test-Path $certPath)) {
            Write-Err2 "Authentification echouee (cert.pem absent)."
            Write-Info2 "  Si tu n'as pas de compte / domaine Cloudflare :"
            Write-Info2 "    1. Cree un compte sur https://dash.cloudflare.com/sign-up"
            Write-Info2 "    2. Ajoute un domaine (Sites -> Add a site, plan Free)"
            Write-Info2 "    3. Pointe les nameservers du domaine vers ceux de Cloudflare"
            Write-Info2 "    4. Relance .\makefile.ps1 start"
            return
        }
        Write-Ok "Authentifie"
    } else {
        Write-Ok "1/4 Deja authentifie (cert.pem present)"
    }

    # ---- 2/4 : nom du tunnel ----
    $tunnelName = Read-Host "Nom du tunnel (ex: liugong-academy)"
    if ([string]::IsNullOrWhiteSpace($tunnelName)) { Write-Err2 "Nom vide, abandon."; return }

    $existing = & cloudflared tunnel list 2>$null | Select-String -Pattern "\b$([regex]::Escape($tunnelName))\b"
    if ($existing) {
        Write-Ok "2/4 Tunnel '$tunnelName' deja existant"
    } else {
        Write-Step "2/4 Creation du tunnel '$tunnelName'..."
        & cloudflared tunnel create $tunnelName 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { Write-Err2 "Echec creation tunnel"; return }
        Write-Ok "Tunnel cree"
    }

    # ---- 3/4 : DNS ----
    $hostname = Read-Host "Hostname public (ex: academy.liugong.com)"
    if ([string]::IsNullOrWhiteSpace($hostname)) { Write-Err2 "Hostname vide, abandon."; return }

    Write-Step "3/4 Configuration de la route DNS..."
    & cloudflared tunnel route dns $tunnelName $hostname 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Echec config DNS. Causes possibles :"
        Write-Info2 "  - Le hostname existe deja sur un autre tunnel (supprime via dashboard)"
        Write-Info2 "  - Le domaine n'est pas dans ton compte Cloudflare"
        Write-Info2 "  - cloudflared n'a pas les droits sur ce domaine"
        Write-Host ""
        $cont = Read-Choice -Prompt "Continuer quand meme ? (o/n)" -Default 'n' -Choices @('o','n')
        if ($cont -ne 'o') { return }
    }

    # ---- 4/4 : config + run ----
    Write-Step "4/4 Generation du fichier de configuration..."
    $tunnelInfo = & cloudflared tunnel list 2>$null | Select-String $tunnelName
    if (-not $tunnelInfo) { Write-Err2 "Tunnel introuvable apres creation."; return }
    $tunnelId = ($tunnelInfo.ToString().Trim() -split '\s+')[0]

    $configPath = Join-Path $cfDir 'config.yml'
    $credPath   = Join-Path $cfDir "$tunnelId.json"

    @"
# Genere par makefile.ps1 le $(Get-Date -Format 'yyyy-MM-dd HH:mm')
tunnel: $tunnelId
credentials-file: $credPath

ingress:
  - hostname: $hostname
    service: http://localhost:$VPort
  - service: http_status:404
"@ | Set-Content -Path $configPath -Encoding UTF8

    Write-Ok "Configuration ecrite : $configPath"
    Write-Host ""
    Write-Info2 "URL publique (apres demarrage du tunnel) : https://$hostname"
    Write-Host ""

    $runNow = Read-Choice -Prompt "Demarrer le tunnel maintenant ? (o/n)" -Default 'o' -Choices @('o','n')
    if ($runNow -eq 'o') {
        $cmd = "Write-Host 'Cloudflare Named Tunnel - $tunnelName -> https://$hostname' -ForegroundColor Cyan; " +
               "Write-Host 'Ctrl+C pour arreter.' -ForegroundColor Yellow; Write-Host ''; " +
               "cloudflared tunnel run $tunnelName"
        Start-Process -FilePath 'powershell.exe' `
                      -ArgumentList @('-NoExit', '-Command', $cmd) `
                      -WorkingDirectory $ProjectRoot
        Write-Ok "Tunnel '$tunnelName' lance dans une nouvelle fenetre."
    } else {
        Write-Info2 "Pour demarrer plus tard : cloudflared tunnel run $tunnelName"
    }

    Write-Host ""
    Write-Info2 "ASTUCE : pour installer cloudflared comme service Windows (autostart) :"
    Write-Info2 "  cloudflared service install"
    Write-Info2 "Ou utiliser le script avance : configurations\orchestrate-cloudflared.ps1"
}

# =============================================================================

function Task-Start {
    # ----- Pre-step : git pull (L) ------------------------------------------
    if ($Pull) {
        Write-Title "Mise a jour du code source (git pull)"
        Invoke-GitPull | Out-Null
        Write-Host ""
    }

    # ----- Pre-flight checks (A B C D E F + existants) ----------------------
    if (-not $NoChecks) {
        if (-not (Invoke-PreflightChecks)) {
            Write-Host ""
            Write-Err2 "Verification de l'environnement echouee. Corrigez les erreurs ci-dessus puis relancez."
            exit 1
        }
    } else {
        Write-Warn "Pre-flight saute (-NoChecks)"
    }

    Write-Host ""
    Write-Ok "Environnement pret a 100%"

    # ----- Mises a jour disponibles (N) -------------------------------------
    $updates = Test-ToolsUpdate
    if ($updates.Count -gt 0) {
        Write-Host ""
        Write-Title "Mises a jour disponibles"
        foreach ($u in $updates) { Write-Info2 "  $u" }
    }

    # ----- Choix du mode de lancement ---------------------------------------
    $launchChoice = Show-LaunchMenu
    if ($launchChoice -eq 'q') { Write-Info2 "Annule par l'utilisateur."; exit 0 }
    if ($launchChoice -notin @('1','2','3')) { Write-Err2 "Choix invalide : $launchChoice"; exit 1 }

    $modeLabel = switch ($launchChoice) { '1' { 'Dev local' }; '2' { 'NSSM' }; '3' { 'Docker' } }

    # ----- Pare-feu Windows (G) - uniquement pour modes accessibles reseau --
    if ($launchChoice -in @('2','3') -and -not $NoFirewall) {
        Write-Host ""
        $askFw = Read-Choice -Prompt "Ouvrir le port $Port dans le pare-feu Windows (acces reseau) ? (o/n)" -Default 'o' -Choices @('o','n')
        if ($askFw -eq 'o') {
            $fw = Add-FirewallRule -VPort $Port
            if ($fw.Ok -and -not $fw.Existed) {
                Write-Ok "Regle pare-feu creee pour le port $Port"
            } elseif ($fw.Ok -and $fw.Existed) {
                Write-Ok "Regle pare-feu deja existante pour le port $Port"
            } else {
                Write-Warn "Pare-feu non configure. L'app sera limitee a localhost."
            }
        }
    }

    # ----- Backup uploads (M) - avant NSSM/Docker ---------------------------
    if ($launchChoice -in @('2','3')) {
        Write-Host ""
        $doBackup = if ($Backup) { 'o' } else {
            Read-Choice -Prompt "Sauvegarder app/static/uploads/ avant lancement ? (o/n)" -Default 'n' -Choices @('o','n')
        }
        if ($doBackup -eq 'o') {
            $b = Backup-Uploads
            if ($b -and $b.Skipped) {
                Write-Info2 "Backup non necessaire (uploads vide)"
            } elseif ($b) {
                Write-Ok "Backup : $($b.Count) elements -> $($b.Path)"
            }
        }
    }

    # ----- Question Cloudflared ---------------------------------------------
    Write-Host ""
    $tunnelChoice = Read-Choice -Prompt "Voulez-vous aussi exposer via Cloudflare Tunnel ? (o/n)" -Default 'n' -Choices @('o','n')

    Write-Host ""
    switch ($launchChoice) {
        '1' {
            # Mode dev : uvicorn bloque la console
            # 1. Lancer le tunnel CF d'abord (background si demande)
            if ($tunnelChoice -eq 'o') { Start-CloudflaredTunnel -VPort $Port }
            # 2. Recap AVANT le lancement (puis blocage)
            Show-LaunchSummary -VPort $Port -Mode $modeLabel
            # 3. Programmer l'ouverture du navigateur (I) en differe (le serveur ne repondra pas instantanement)
            if (-not $NoBrowser) {
                Start-Job -ScriptBlock {
                    param($port, $timeout)
                    $deadline = (Get-Date).AddSeconds($timeout)
                    while ((Get-Date) -lt $deadline) {
                        try {
                            $r = Invoke-WebRequest -Uri "http://localhost:$port/home" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
                            if ($r.StatusCode -eq 200) { Start-Process "http://localhost:$port"; return }
                        } catch { Start-Sleep -Milliseconds 400 }
                    }
                } -ArgumentList $Port, 30 | Out-Null
            }
            # 4. Lancement uvicorn (bloquant)
            Write-Host ""
            Start-DevLocal
        }
        '2' {
            Start-NssmMode
            # Le service tourne en background, on peut continuer
            Write-Host ""
            $hcUrl = Get-HealthUrl -VPort $Port
            Write-Step "Healthcheck sur $hcUrl (timeout 60s)..."
            if (Wait-AppReady -VPort $Port -TimeoutSec 60) {
                Write-Ok "Service repond sur le port $Port"
                Open-AppInBrowser -VPort $Port
            } else {
                Write-Warn "Pas de reponse - voir logs : Get-Content logs\$NssmServiceName.err.log -Tail 50"
            }
            if ($tunnelChoice -eq 'o') { Start-CloudflaredTunnel -VPort $Port }
            $tunnelLabel = if ($tunnelChoice -eq 'o') { 'oui' } else { '' }
            Show-LaunchSummary -VPort $Port -Mode $modeLabel -TunnelMode $tunnelLabel
        }
        '3' {
            Start-DockerMode
            Write-Host ""
            $hcUrl = Get-HealthUrl -VPort $Port
            Write-Step "Healthcheck sur $hcUrl (timeout 60s)..."
            if (Wait-AppReady -VPort $Port -TimeoutSec 60) {
                Write-Ok "Container repond sur le port $Port"
                Open-AppInBrowser -VPort $Port
            } else {
                Write-Warn "Pas de reponse - voir logs : docker logs $DockerContainerName --tail 50"
            }
            if ($tunnelChoice -eq 'o') { Start-CloudflaredTunnel -VPort $Port }
            $tunnelLabel = if ($tunnelChoice -eq 'o') { 'oui' } else { '' }
            Show-LaunchSummary -VPort $Port -Mode $modeLabel -TunnelMode $tunnelLabel
        }
    }
}

function Task-Info {
    Write-Title "Versions des outils"

    $uvPath = Resolve-Uv

    Write-Host "  uv            : " -NoNewline
    if ($uvPath) { (& $uvPath --version) | Write-Host -ForegroundColor Green }
    else { Write-Host "non installe" -ForegroundColor Red }

    Write-Host "  python (uv)   : " -NoNewline
    if ($uvPath) {
        try { (& $uvPath run python --version) | Write-Host -ForegroundColor Green }
        catch { Write-Host "erreur" -ForegroundColor Red }
    } else { Write-Host "indisponible" -ForegroundColor Red }

    Write-Host "  Tailwind CLI  : " -NoNewline
    $bin = Join-Path $ProjectRoot 'tools\tailwindcss.exe'
    if (Test-Path $bin) {
        $line = (& $bin --help 2>&1 | Where-Object { $_ -match 'tailwindcss' } | Select-Object -First 1)
        if ($line) { Write-Host $line -ForegroundColor Green }
        else { Write-Host "installe (version inconnue)" -ForegroundColor Green }
    }
    else { Write-Host "non installe (lancer .\makefile.ps1 install)" -ForegroundColor Red }

    Write-Host "  ruff (uv)     : " -NoNewline
    if ($uvPath) {
        try { (& $uvPath run ruff --version) | Write-Host -ForegroundColor Green }
        catch { Write-Host "non installe (uv add --dev ruff)" -ForegroundColor Yellow }
    } else { Write-Host "indisponible" -ForegroundColor Red }

    Write-Host "  CSS compile   : " -NoNewline
    $css = Join-Path $ProjectRoot 'app\static\css\tailwind.css'
    if (Test-Path $css) {
        $size = [Math]::Round((Get-Item $css).Length / 1KB, 1)
        Write-Host "$size Ko" -ForegroundColor Green
    } else { Write-Host "absent (lancer .\makefile.ps1 build-css)" -ForegroundColor Red }

    Write-Host "  Police icones : " -NoNewline
    $font = Join-Path $ProjectRoot 'app\static\fonts\MaterialSymbolsOutlined.woff2'
    if (Test-Path $font) {
        $size = [Math]::Round((Get-Item $font).Length / 1KB, 1)
        Write-Host "$size Ko" -ForegroundColor Green
    } else { Write-Host "absente" -ForegroundColor Red }
}

# ----------------------------------------------------------------------------
# DISPATCHER
# ----------------------------------------------------------------------------
# Tente d'exposer uv au PATH des l'entree du script. Silencieux : si uv n'est
# pas trouve, les taches concernees (start/dev/serve/...) afficheront le bon
# message d'erreur et proposeront l'installation auto.
[void](Resolve-Uv)

switch ($Task.ToLower()) {
    'help'       { Show-Help }
    ''           { Show-Help }

    'start'      { Task-Start }
    'install'    { Task-Install }
    'dev'        { Task-Dev   -VHost $BindHost -VPort $Port }
    'run'        { Task-Dev   -VHost $BindHost -VPort $Port }
    'serve'      { Task-Serve -VHost $BindHost -VPort $Port }

    'build-css'  { Task-BuildCss }
    'build_css'  { Task-BuildCss }
    'buildcss'   { Task-BuildCss }
    'watch-css'  { Task-WatchCss }
    'watch_css'  { Task-WatchCss }
    'watchcss'   { Task-WatchCss }
    'icons'      { Task-Icons }

    'lint'       { Task-Lint }
    'format'     { Task-Format }
    'check'      { Task-Check }

    'clean'      { Task-Clean -DoForce:$Force }
    'tree'       { Task-Tree }
    'info'       { Task-Info }

    'nssm-install'   { Task-NssmInstall }
    'nssm_install'   { Task-NssmInstall }
    'install-nssm'   { Task-NssmInstall }
    'nssm-recreate'  { Task-NssmInstall }
    'nssm_recreate'  { Task-NssmInstall }

    'nssm-start'     { Task-NssmStart }
    'nssm_start'     { Task-NssmStart }
    'start-nssm'     { Task-NssmStart }

    'nssm-stop'      { Task-NssmStop }
    'nssm_stop'      { Task-NssmStop }
    'stop-nssm'      { Task-NssmStop }

    'nssm-restart'   { Task-NssmRestart }
    'nssm_restart'   { Task-NssmRestart }
    'restart-nssm'   { Task-NssmRestart }

    'nssm-status'    { Task-NssmStatus }
    'nssm_status'    { Task-NssmStatus }
    'status-nssm'    { Task-NssmStatus }

    'nssm-remove'    { Remove-NssmService }
    'nssm_remove'    { Remove-NssmService }
    'remove-nssm'    { Remove-NssmService }

    default {
        Write-Err2 "Tache inconnue : '$Task'"
        Show-Help
        exit 1
    }
}
