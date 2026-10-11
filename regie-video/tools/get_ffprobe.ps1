# Télécharge FFprobe (build LGPL de BtbN, sans composant GPL) dans vendor\ffmpeg.
# FFprobe sert uniquement au diagnostic des médias ; la lecture utilise Qt Multimedia.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "vendor\ffmpeg"
if (Test-Path (Join-Path $dest "ffprobe.exe")) { Write-Host "FFprobe déjà présent."; exit 0 }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-lgpl.zip"
$zip = Join-Path $env:TEMP "ffmpeg-lgpl.zip"
Write-Host "Téléchargement de $url"
Invoke-WebRequest -Uri $url -OutFile $zip
$tmp = Join-Path $env:TEMP "ffmpeg-lgpl"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Expand-Archive -Path $zip -DestinationPath $tmp
$bin = Get-ChildItem -Path $tmp -Recurse -Filter "ffprobe.exe" | Select-Object -First 1
Copy-Item $bin.FullName $dest
# ffmpeg.exe sert seulement aux tests (génération d'un fichier à haut débit) ; il n'est pas livré.
$ff = Get-ChildItem -Path $tmp -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if ($ff) { Copy-Item $ff.FullName $dest }
$lic = Get-ChildItem -Path $tmp -Recurse -Filter "LICENSE.txt" | Select-Object -First 1
if ($lic) { Copy-Item $lic.FullName (Join-Path $dest "LICENSE.txt") }
Set-Content -Path (Join-Path $dest "README.txt") -Encoding UTF8 -Value "FFprobe (FFmpeg, build LGPL de BtbN : https://github.com/BtbN/FFmpeg-Builds) - licence LGPL v2.1 ou ultérieure, voir LICENSE.txt. Source : https://ffmpeg.org"
& (Join-Path $dest "ffprobe.exe") -version | Select-Object -First 1
