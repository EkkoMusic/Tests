# Régie Vidéo

**Application Windows de régie vidéo pour spectacles vivants.**

Régie Vidéo sert à préparer la conduite d'un spectacle (une vidéo de présentation par artiste, suivie d'une image finale) puis à la déclencher en direct, au clavier, en plein écran, sans qu'aucun élément technique ne soit visible par le public.

- **Mode préparation** : interface sombre et complète pour créer, ordonner, vérifier et prévisualiser les séquences.
- **Mode spectacle** : la projection seule, en plein écran, curseur masqué. La flèche droite lance la séquence suivante ; à la fin de la vidéo, l'image finale reste affichée aussi longtemps que nécessaire. **Jamais d'enchaînement automatique.**

Version : 1.1.0 — fonctionne hors ligne, sans compte, sans serveur, sans abonnement.

**Nouveautés 1.1 — diffusion haute qualité** (détails et mesures : [docs/QUALITE_DIFFUSION.md](docs/QUALITE_DIFFUSION.md)) :

- **Rendu vidéo accéléré par la carte graphique.** Les images décodées ne passent plus par le processeur : la 4K30 et le 3289 × 1480 sont lus en temps réel là où la 1.0 décrochait.
- **Lecture directe des fichiers d'origine**, sans réencodage, sans réduction de résolution, sans changement de cadence, sans filtre, sans amplification du son.
- **Informations média** pour chaque vidéo : résolution exacte, format, cadence (y compris 23,976 / 29,97 / 59,94), codec et profil, débit, taille, couleurs (BT.709/2020, SDR/HDR, plage, profondeur) et audio (codec, canaux, fréquence, débit). Un schéma montre le placement du média dans l'écran de projection.
- **Indicateur de compatibilité** fondé sur le contenu réel du fichier et un décodage effectif, jamais sur son extension.
- **Mise à l'échelle** : adapter (défaut), remplir ou taille native, avec leurs conséquences expliquées.
- **« Vérifier la diffusion »** : diagnostic avant spectacle (médias, écran et fréquence, sortie audio), avec test de lecture réel invisible et inaudible.

---

## Sommaire

1. [Installation](#installation)
2. [Utilisation rapide](#utilisation-rapide)
3. [Commandes du mode spectacle](#commandes-du-mode-spectacle)
4. [Fichiers de spectacle `.regievideo`](#fichiers-de-spectacle-regievideo)
5. [Limites connues de Windows](#limites-connues-de-windows)
6. [Architecture](#architecture)
7. [Développement, tests et compilation](#développement-tests-et-compilation)

Documents complémentaires :

- [Guide d'exploitation et checklist avant spectacle](docs/GUIDE_EXPLOITATION.md)
- [Protocole de tests sur le matériel réel](docs/PROTOCOLE_TESTS.md)
- [Notes techniques (choix, machine à états, risques)](docs/NOTES_TECHNIQUES.md)
- [Qualité de diffusion : audit, mesures, limites](docs/QUALITE_DIFFUSION.md)

---

## Installation

### Avec l'exécutable (recommandé)

1. Récupérez le dossier `RegieVideo` (compilé avec `build_windows.bat`, ou téléchargé depuis l'onglet *Actions* du dépôt GitHub : artefact **RegieVideo-windows**).
2. Copiez **tout le dossier** `RegieVideo` sur le PC de régie, par exemple dans `C:\Programmes\RegieVideo`. L'exécutable a besoin des fichiers placés à côté de lui (bibliothèques Qt et FFmpeg).
3. Lancez `RegieVideo.exe`. Vous pouvez créer un raccourci sur le Bureau (clic droit → *Envoyer vers* → *Bureau*).

Windows SmartScreen peut afficher « Windows a protégé votre ordinateur » au premier lancement, car l'exécutable n'est pas signé : cliquez sur *Informations complémentaires* puis *Exécuter quand même*.

Configuration conseillée : Windows 10 ou 11 (64 bits), 8 Go de RAM, vidéos MP4 (H.264 + AAC) en 1920×1080.

### Depuis les sources

Python 3.12 (64 bits) requis.

```bat
cd regie-video
run_dev.bat
```

Le script crée un environnement virtuel `.venv`, installe les dépendances (`requirements-dev.txt`) puis lance l'application. Sous macOS ou Linux (développement uniquement) : `./run_dev.sh`.

---

## Utilisation rapide

1. **Nouveau** (Ctrl+N), puis cliquez sur le nom du spectacle en haut pour le renommer.
2. **Ajouter des vidéos** (Ctrl+I) ou glissez-déposez vos fichiers MP4 dans la conduite.
   Une image (PNG/JPG) portant **le même nom** que la vidéo, dans le même dossier, est associée automatiquement comme image finale (`artiste1.mp4` → `artiste1.png`).
3. **Réorganisez** par glisser-déposer (poignée ⠿) ou avec Alt+↑ / Alt+↓.
4. Dans **Propriétés**, pour chaque séquence : nom, vidéo, volume, et ce qui s'affiche à la fin :
   - **Image** : l'image finale choisie (sans image, du noir) ;
   - **Noir** : écran noir ;
   - **Figer** : la dernière image de la vidéo reste affichée.
5. **Prévisualisez** dans la zone dédiée : lecture, pause, position, volume et aperçu de la fin. La prévisualisation n'a aucun effet sur la conduite.
6. **Enregistrer** (Ctrl+S) : un fichier `nom_du_spectacle.regievideo` est créé.
7. **Vérifier la diffusion** (bouton en haut à droite) sur le PC du spectacle, vidéoprojecteur branché : activez le test de lecture réel pour mesurer la fluidité de chaque vidéo.
8. **Lancer le spectacle** (bouton en haut à droite ou F5). Régie Vidéo vérifie d'abord tous les fichiers et signale les problèmes ; la fenêtre de préparation disparaît ensuite et seule la projection reste.

Paramètres (Ctrl+,) : écran de projection et écrans détectés, mise à l'échelle, rendu vidéo, image d'attente, comportement en fin de spectacle, rubrique « Audio et diffusion » (sortie utilisée et son format, volume général), protections clavier.

### Informations média et compatibilité

Sélectionnez une séquence : la section **Informations média** des propriétés affiche les valeurs lues dans le fichier. Une valeur que le fichier ne fournit pas est indiquée « Non disponible » : rien n'est inventé. L'indicateur peut prendre ces valeurs :

| Indicateur | Signification |
|---|---|
| Compatible et vérifié | Caractéristiques connues, décodage réel réussi, aucun risque identifié |
| Compatible présumé, test nécessaire | Lisible, mais un point mérite un test (HDR, cadence variable, entrelacement, couleurs 4:2:2/4:4:4, codec rare…) |
| Risque de performances | Charge de décodage élevée : 4K60, au-delà des limites du décodage matériel, codec de production (ProRes, DNxHR), débit très élevé… |
| Média non pris en charge | Le moteur ne parvient pas à décoder le fichier |
| Analyse impossible | Le fichier n'a pas pu être analysé |

La liste des séquences reste centrée sur la conduite : seule la résolution y est ajoutée, discrètement.

---

## Commandes du mode spectacle

| Touche | Action |
|---|---|
| **Flèche droite** | Lancer la séquence suivante — uniquement quand l'image finale (ou le noir, ou l'image d'attente) est affichée |
| **Espace** | Pause / reprise de la vidéo |
| **R** | Recommencer la vidéo actuelle depuis le début |
| **B** | Écran noir immédiat / retour à l'état précédent |
| **Flèche gauche** | Revenir à la séquence précédente **sans la lancer** (affiche sa fin) |
| **Ctrl + Maj + Q**, deux fois en moins de 3 s | Quitter le mode spectacle |

Règles de sécurité :

- Flèche droite est **ignorée pendant la lecture et pendant la pause** : impossible de couper une vidéo par erreur.
- Une touche maintenue enfoncée ne déclenche qu'une seule action (répétition automatique du clavier filtrée), et un second appui sur la même touche dans les 400 ms est ignoré (réglable).
- Pendant le noir (B), seules B et la sortie sont actives. Une vidéo en lecture est mise en pause et reprend à la sortie du noir ; une vidéo en pause reste en pause.
- Flèche gauche est ignorée pendant la lecture et la pause.

**Pourquoi pas Ctrl + Maj + Échap ?** Cette combinaison ouvre le Gestionnaire des tâches de Windows : elle est interceptée par le système et n'arrive jamais à l'application. La sortie utilise donc **Ctrl + Maj + Q pressé deux fois** : aucune fenêtre de confirmation ne s'affiche, puisqu'en mode « Dupliquer » le public la verrait. La double frappe peut être désactivée dans *Paramètres → Sécurité*. Alt+F4 est sans effet pendant le spectacle.

L'architecture prévoit la personnalisation des raccourcis (table touche → action enregistrée dans les paramètres) ; elle sera exposée dans l'interface dans une prochaine version.

---

## Fichiers de spectacle `.regievideo`

Un spectacle est un fichier JSON lisible et versionné (`"format": "regie-video-show"`, `"format_version": 1`) : nom, dates, réglages, et la liste ordonnée des séquences avec identifiants stables, noms, chemins des vidéos et images, volume, comportement de fin et durée détectée.

- Les médias situés **dans le dossier du fichier projet** (ou un sous-dossier) sont enregistrés en **chemins relatifs** : le dossier entier peut être copié sur une clé USB ou un autre PC.
- Les médias situés ailleurs sont enregistrés en chemins absolus.
- Régie Vidéo **ne copie, ne déplace et ne supprime jamais** vos vidéos et images.
- Si des fichiers ont été déplacés, utilisez *Plus d'actions → Rechercher les fichiers manquants…* : les fichiers sont retrouvés par leur nom dans le dossier indiqué.
- L'enregistrement est atomique (fichier temporaire puis remplacement) : une coupure pendant l'enregistrement ne corrompt pas le spectacle.
- Une **autosauvegarde de secours** est écrite toutes les 30 secondes en cas de modifications non enregistrées. Après un incident, elle est proposée au démarrage suivant.

Organisation recommandée :

```
Gala 2027\
├── gala_2027.regievideo
└── medias\
    ├── 01_lea-martin.mp4
    ├── 01_lea-martin.png
    ├── 02_les-pitchounes.mp4
    └── 02_les-pitchounes.png
```

Données de l'application : `%APPDATA%\RegieVideo\` (paramètres `settings.json`, `autosave\`, journaux `logs\regie-video.log`).

---

## Limites connues de Windows

Régie Vidéo masque tout ce qui lui appartient. En revanche, une application ne peut pas tout contrôler dans Windows :

- **Notifications système** (Windows Update, antivirus, messageries, « Ne pas déranger » désactivé…) : elles peuvent apparaître par-dessus la projection. Activez l'**Assistant de concentration / Ne pas déranger**, fermez les autres logiciels et coupez le Wi-Fi si possible.
- **Perte du focus clavier** : si une autre fenêtre prend le focus (notification cliquée, logiciel qui s'ouvre), les touches n'arrivent plus à Régie Vidéo. La projection reste affichée au premier plan ; cliquez une fois dessus (le curseur est invisible mais le clic fonctionne) pour reprendre la main. L'incident est noté dans le journal.
- **Duplication d'écran** : en mode « Dupliquer », le vidéoprojecteur affiche exactement l'écran du portable. La résolution commune est souvent celle du projecteur ; réglez-la dans Windows avant le spectacle et vérifiez les proportions.
- **Mise en veille** : Régie Vidéo empêche la mise en veille de l'écran et de l'ordinateur pendant le mode spectacle. Branchez tout de même le portable sur secteur.
- **Touches système** : Windows (touche ⊞), Alt+Tab, Ctrl+Alt+Suppr et Ctrl+Maj+Échap ne peuvent pas être bloquées.

---

## Architecture

```
regie-video/
├── main.py                       point d'entrée (+ --self-test)
├── app/
│   ├── core/                     logique métier, sans interface
│   │   ├── cue_state.py          machine à états (IDLE, LOADING, PLAYING, PAUSED, HOLDING, BLACKOUT, ERROR, FINISHED)
│   │   ├── show_controller.py    décisions de conduite ; rendu délégué à ShowOutput
│   │   ├── cue_manager.py        édition de la conduite
│   │   └── keyboard_controller.py touches → actions, anti-répétition, double frappe de sortie
│   ├── media/                    lecture et vérification des médias
│   │   ├── playback_engine.py    contrat PlaybackEngine + implémentation Qt Multimedia (+ télémétrie)
│   │   ├── media_info.py         caractéristiques des médias (FFprobe, repli Qt), formatage français
│   │   ├── analyzer.py           analyse en arrière-plan
│   │   ├── compatibility.py      verdict de compatibilité / performances, cadence et écran
│   │   ├── system_info.py        écrans (résolution, fréquence, échelle), sorties audio
│   │   ├── telemetry.py          images sautées, délai de démarrage, régularité
│   │   ├── playback_tester.py    test de lecture réel invisible et inaudible
│   │   ├── diagnostic.py         bilan « Vérifier la diffusion »
│   │   ├── media_validator.py    vérification avant spectacle
│   │   ├── thumbnail_service.py  durée, miniature, détection des vidéos illisibles
│   │   └── image_loader.py       décodage des images en arrière-plan
│   ├── models/                   Show, Cue
│   ├── persistence/              fichiers .regievideo, autosauvegarde, paramètres
│   ├── ui/                       interface PySide6
│   │   ├── main_window.py, cue_list.py, cue_editor.py, preview_panel.py
│   │   ├── projection_window.py  fenêtre du mode spectacle
│   │   ├── settings_dialog.py, dialogs.py
│   │   ├── media_panel.py, diagnostic_dialog.py
│   │   ├── widgets/              composants, surfaces vidéo (GPU Qt Quick / processeur)
│   │   └── theme/                design system : jetons, feuille de style, icônes
│   └── utils/                    chemins, journaux, veille, formatage
├── assets/                       logo, icône .ico, scène QML de projection, vidéo d'auto-test
├── tests/                        tests métier (core) et tests interface/média (ui)
├── RegieVideo.spec               configuration PyInstaller
├── build_windows.bat             compilation Windows complète
└── run_dev.bat / run_dev.sh      lancement en développement
```

Voir [docs/NOTES_TECHNIQUES.md](docs/NOTES_TECHNIQUES.md) pour la machine à états, la transition vidéo → image et les risques identifiés.

---

## Développement, tests et compilation

```bat
cd regie-video
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

rem Tests (affichage virtuel, aucune fenêtre ne s'ouvre)
set QT_QPA_PLATFORM=offscreen
python -m pytest -q

rem Compilation complète + auto-test de l'exécutable
build_windows.bat
```

- `tests/core` : logique métier pure (machine à états, conduite, clavier, persistance, validation).
- `tests/ui` : interface et moteur vidéo réel, avec de très courts fichiers de test (`tests/fixtures`) : 1080p, 4K, 3289 × 1480, vertical, cadences 24 à 60 i/s et fractionnaires, audio stéréo, 5.1 et PCM 96 kHz, HDR10, plage complète, rotation, pixels non carrés, ProRes, codec inconnu, fichier sans métadonnées, fichier de plus de 2 Go, fichier à haut débit.
- Tests du rendu GPU (`-m gpu`) : ils nécessitent un vrai rendu graphique (`REGIE_VIDEO_QPA=windows` sous Windows, ou Xvfb sous Linux) et sont ignorés en affichage virtuel.
- `RegieVideo.exe --self-test` lit la vidéo embarquée, vérifie la détection de fin de média, le rendu GPU et l'analyse FFprobe, puis écrit `%APPDATA%\RegieVideo\logs\selftest.txt` : c'est la preuve que les bibliothèques multimédias sont bien présentes dans la distribution.
- La CI GitHub (`.github/workflows/regie-video.yml`) exécute les tests, compile l'exécutable et lance cet auto-test **sur une machine Windows** à chaque modification du dossier `regie-video/`, puis publie le dossier `RegieVideo` en artefact téléchargeable.

Dépendance d'exécution : **PySide6 6.12.0** (Qt 6, LGPL v3), qui embarque Qt Multimedia, Qt Quick et FFmpeg (LGPL v2.1+).

**FFprobe** sert au diagnostic des médias (la lecture reste assurée par Qt Multimedia). La version Windows embarque `ffprobe.exe`, issu d'un build **LGPL** de BtbN et téléchargé par `tools/get_ffprobe.ps1`, avec sa licence dans `_internal\ffmpeg\`. En développement, le FFprobe du système est utilisé. Sans FFprobe, l'analyse se limite aux métadonnées de Qt.

Médias de test : `python tools/make_test_media.py` régénère `tests/fixtures/media` (FFmpeg avec libx264/libx265 requis). Les icônes de l'interface sont dessinées pour Régie Vidéo dans l'esprit des jeux d'icônes à trait.
