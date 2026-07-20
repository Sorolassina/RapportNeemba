# =============================================================================
# Script de build / watch Tailwind CSS pour LiuGong Academy.
#
# Usage :
#   .\scripts\tailwind.ps1 install     # Télécharge le binaire si absent
#   .\scripts\tailwind.ps1 build       # Compile en production (minifié)
#   .\scripts\tailwind.ps1 watch       # Mode dev (recompile à chaque sauvegarde)
# =============================================================================

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'build', 'watch')]
    [string]$Command = 'build'
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BinPath     = Join-Path $ProjectRoot 'tools\tailwindcss.exe'
$ConfigPath  = Join-Path $ProjectRoot 'tailwind.config.js'
$InputPath   = Join-Path $ProjectRoot 'app\static\css\tailwind.input.css'
$OutputPath  = Join-Path $ProjectRoot 'app\static\css\tailwind.css'

$TailwindVersion = '3.4.17'
$DownloadUrl     = "https://github.com/tailwindlabs/tailwindcss/releases/download/v$TailwindVersion/tailwindcss-windows-x64.exe"

function Install-Tailwind {
    if (Test-Path $BinPath) {
        Write-Host "Tailwind CLI déjà présent : $BinPath" -ForegroundColor Green
        & $BinPath --help | Select-Object -First 1
        return
    }

    Write-Host "Téléchargement Tailwind CLI v$TailwindVersion..." -ForegroundColor Cyan
    $toolsDir = Split-Path -Parent $BinPath
    if (-not (Test-Path $toolsDir)) {
        New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
    }
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $BinPath -UseBasicParsing
    $size = [Math]::Round((Get-Item $BinPath).Length / 1MB, 1)
    Write-Host "Installé : $BinPath ($size MB)" -ForegroundColor Green
}

function Assert-Tailwind {
    if (-not (Test-Path $BinPath)) {
        Write-Host "Tailwind CLI introuvable, installation automatique..." -ForegroundColor Yellow
        Install-Tailwind
    }
}

switch ($Command) {
    'install' {
        Install-Tailwind
    }
    'build' {
        Assert-Tailwind
        Write-Host "Build Tailwind (production, minifié)..." -ForegroundColor Cyan
        & $BinPath -c $ConfigPath -i $InputPath -o $OutputPath --minify
        if ($LASTEXITCODE -eq 0) {
            $size = [Math]::Round((Get-Item $OutputPath).Length / 1KB, 1)
            Write-Host "OK -> $OutputPath ($size Ko)" -ForegroundColor Green
        }
    }
    'watch' {
        Assert-Tailwind
        Write-Host "Watch Tailwind (Ctrl+C pour quitter)..." -ForegroundColor Cyan
        & $BinPath -c $ConfigPath -i $InputPath -o $OutputPath --watch
    }
}
