# Reprendre le projet Régie Vidéo sur un PC (instructions pour une IA)

Ce document s'adresse à une IA de développement (Claude Code, Codex, etc.) qui doit poursuivre le travail sur le PC Windows de l'utilisateur.

## 1. Récupérer le projet

Dans PowerShell :

```powershell
$s = Join-Path $env:TEMP "recuperer_projet.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/EkkoMusic/Tests/claude/intelligent-allen-vbegky/regie-video/tools/recuperer_projet.ps1" -OutFile $s
powershell -NoProfile -ExecutionPolicy Bypass -File $s -Destination "$HOME\Documents\RegieVideo"
```

Le script :
- clone le dépôt public `EkkoMusic/Tests`, branche `claude/intelligent-allen-vbegky`, en ne gardant que `regie-video/` et `.github/` (archive ZIP si Git est absent) ;
- crée `.venv` et installe les dépendances ;
- télécharge FFprobe ;
- lance les tests.

Il peut être relancé pour mettre à jour le projet (`git pull`).

Prérequis : Windows 10/11, Python 3.12 64 bits (python.org), Git conseillé.

## 2. Ce qu'il faut savoir avant de modifier

- **Projet** : application Windows PySide6 (Qt 6.12) de régie vidéo pour spectacles vivants, entièrement en français. Code dans `regie-video/`.
- **À lire d'abord** :
  - `README.md` : fonctionnalités, architecture ;
  - `docs/NOTES_TECHNIQUES.md` : machine à états, transitions ;
  - `docs/QUALITE_DIFFUSION.md` : rendu GPU, mesures, limites ;
  - `docs/PROTOCOLE_TESTS.md`.
- **Architecture** : la logique métier pure (`app/core`, `app/models`, `app/persistence`) est séparée des médias (`app/media`) et de l'interface (`app/ui`). Le mode spectacle repose sur la machine à états `app/core/cue_state.py` ; ne pas la contourner avec des booléens.
- **Exigences à préserver** :
  - aucune interface visible par le public en mode spectacle ;
  - jamais d'enchaînement automatique : la fin de vidéo mène toujours à HOLDING ;
  - pas de flash entre la vidéo et l'image finale ;
  - aucun réencodage ni traitement de l'image ou du son ;
  - interface en français, thème sombre (jetons dans `app/ui/theme/tokens.py`).
- **Lancer** : `run_dev.bat`.
- **Tests** : `.venv\Scripts\python -m pytest -q` avec `QT_QPA_PLATFORM=offscreen`. Pour les tests de rendu GPU : `set REGIE_VIDEO_QPA=windows`, puis `python -m pytest -m gpu`.
- **Compiler** : `build_windows.bat`, qui produit `dist\RegieVideo\RegieVideo.exe` et lance `--self-test`.
- **Git** : la CI GitHub (`.github/workflows/regie-video.yml`) teste et compile sous Windows à chaque push touchant `regie-video/`. Pousser exige des droits d'écriture sur le dépôt ; sans eux, travailler localement et committer sans pousser.
