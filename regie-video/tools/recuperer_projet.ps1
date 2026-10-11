<#
.SYNOPSIS
    Télécharge et installe le projet Régie Vidéo sur ce PC Windows, prêt à être développé.

.DESCRIPTION
    1. Récupère le code depuis GitHub (dépôt public EkkoMusic/Tests) :
       - avec Git si disponible (clone partiel : seulement regie-video/ et .github/),
       - sinon en téléchargeant l'archive ZIP de la branche.
    2. Crée l'environnement Python (.venv) et installe les dépendances.
    3. Télécharge FFprobe (build LGPL) dans regie-video\vendor\ffmpeg.
    4. Lance les tests automatisés pour vérifier que tout fonctionne.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File recuperer_projet.ps1
    powershell -ExecutionPolicy Bypass -File recuperer_projet.ps1 -Destination "D:\Projets\RegieVideo"
#>
param(
    [string]$Destination = (Join-Path $HOME "Documents\RegieVideo"),
    [string]$Branche = "claude/intelligent-allen-vbegky",
    [switch]$SansTests
)

$ErrorActionPreference = "Stop"
$Depot = "https://github.com/EkkoMusic/Tests"

function Etape($texte) { Write-Host "`n==> $texte" -ForegroundColor Cyan }
function Echec($texte) { Write-Host "`nERREUR : $texte" -ForegroundColor Red; exit 1 }

# ------------------------------------------------------------------ 1. Code
Etape "Récupération du code ($Branche) dans $Destination"
$projet = Join-Path $Destination "regie-video"
if (Test-Path $projet) {
    Write-Host "Le dossier existe déjà."
    if (Test-Path (Join-Path $Destination ".git")) {
        Write-Host "Mise à jour avec git pull…"
        git -C $Destination pull --ff-only origin $Branche
        if ($LASTEXITCODE -ne 0) { Echec "git pull a échoué (modifications locales ?)." }
    }
} elseif (Get-Command git -ErrorAction SilentlyContinue) {
    New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
    git clone --filter=blob:none --sparse --branch $Branche "$Depot.git" $Destination
    if ($LASTEXITCODE -ne 0) { Echec "git clone a échoué. Vérifiez la connexion Internet et le nom de branche." }
    git -C $Destination sparse-checkout set regie-video .github
    if ($LASTEXITCODE -ne 0) { Echec "sparse-checkout a échoué." }
} else {
    Write-Host "Git absent : téléchargement de l'archive ZIP (pas d'historique Git)."
    $zip = Join-Path $env:TEMP "regie-video-source.zip"
    $tmp = Join-Path $env:TEMP "regie-video-source"
    Invoke-WebRequest -Uri "$Depot/archive/refs/heads/$Branche.zip" -OutFile $zip
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Path $zip -DestinationPath $tmp
    $racine = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -Recurse -Force (Join-Path $racine.FullName "regie-video") $Destination
    $gh = Join-Path $racine.FullName ".github"
    if (Test-Path $gh) { Copy-Item -Recurse -Force $gh $Destination }
}
if (-not (Test-Path (Join-Path $projet "main.py"))) { Echec "regie-video\main.py introuvable après téléchargement." }

# ---------------------------------------------------------------- 2. Python
Etape "Environnement Python"
$python = $null
foreach ($candidat in @(@("py", "-3.12"), @("py", "-3"), @("python"))) {
    try {
        $v = & $candidat[0] $candidat[1..9] -c "import sys; print(sys.version_info[:2] >= (3, 10))" 2>$null
        if ($v -eq "True") { $python = $candidat; break }
    } catch { }
}
if (-not $python) { Echec "Python 3.10+ introuvable. Installez Python 3.12 (64 bits) depuis python.org en cochant « Add to PATH »." }
Push-Location $projet
try {
    if (-not (Test-Path ".venv")) { & $python[0] $python[1..9] -m venv .venv }
    $py = Join-Path $projet ".venv\Scripts\python.exe"
    & $py -m pip install --upgrade pip --quiet
    & $py -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { Echec "Installation des dépendances impossible." }

    # ----------------------------------------------------------- 3. FFprobe
    Etape "FFprobe (diagnostic des médias)"
    & (Join-Path $projet "tools\get_ffprobe.ps1")
    $env:PATH = (Join-Path $projet "vendor\ffmpeg") + ";" + $env:PATH

    # ------------------------------------------------------------- 4. Tests
    if (-not $SansTests) {
        Etape "Tests automatisés"
        $env:QT_QPA_PLATFORM = "offscreen"
        & $py -m pytest -q
        $resultat = $LASTEXITCODE
        Remove-Item Env:QT_QPA_PLATFORM
        if ($resultat -ne 0) { Write-Host "Des tests ont échoué : voir ci-dessus." -ForegroundColor Yellow }
    }
} finally {
    Pop-Location
}

Etape "Terminé"
Write-Host "Projet : $projet"
Write-Host "Lancer l'application : $projet\run_dev.bat"
Write-Host "Compiler l'exécutable : $projet\build_windows.bat"
Write-Host "À lire d'abord : README.md, docs\NOTES_TECHNIQUES.md, docs\QUALITE_DIFFUSION.md"
