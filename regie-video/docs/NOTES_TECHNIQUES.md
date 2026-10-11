# Notes techniques — Régie Vidéo

## Choix techniques

| Besoin | Choix | Raison |
|---|---|---|
| Langage | Python 3.12 | Stable, PySide6 officiellement pris en charge |
| Interface | PySide6 6.12 (Qt 6) | Qt Widgets natif Windows, haute densité, feuilles de style. Le paquet complet est requis : sous Windows, Qt Multimedia est livré dans « PySide6-Addons » et non dans « Essentials » (détecté par la CI Windows) |
| Vidéo | Qt Multimedia, backend FFmpeg | Inclus dans PySide6, décodage H.264/AAC, matériel quand disponible ; événement `EndOfMedia` fiable |
| Projets | JSON versionné | Lisible, diagnostiquable, migrable |
| Distribution | PyInstaller *onedir* | Plus simple à diagnostiquer avec les plugins Qt et les DLL FFmpeg |
| Tests | pytest + pytest-qt | Logique pure + interface/moteur réels en affichage virtuel |

## Machine à états

```
IDLE ──GO──▶ LOADING ──1re image──▶ PLAYING ──fin de média──▶ HOLDING ──GO──▶ LOADING …
               │                     │  ▲                         │
               │                     ▼  │ Espace                  ├─GO (dernier)──▶ FINISHED
               │                    PAUSED                        └─Flèche gauche──▶ HOLDING (précédente) / IDLE
               └──erreur──▶ ERROR ◀──erreur── PLAYING / PAUSED
   R : PLAYING / PAUSED / HOLDING / ERROR ──▶ LOADING (même séquence)
   B : tout état ──▶ BLACKOUT (état précédent mémorisé) ──B──▶ état précédent
```

- La table `ALLOWED_TRANSITIONS` (`app/core/cue_state.py`) est la seule source de vérité ; une transition non prévue lève une exception (et un test).
- **Fin de vidéo → HOLDING, toujours.** Aucun chemin ne mène de la fin d'une vidéo au lancement de la suivante.
- **BLACKOUT** mémorise l'état précédent au lieu de le détruire. Une vidéo en lecture est mise en pause et reprend à la sortie du noir ; si le noir est demandé pendant un chargement, la vidéo est figée dès sa première image ; si la vidéo se termine pendant le noir, l'état restauré devient HOLDING.
- Chaque lecture reçoit un **jeton** ; les événements du moteur portent ce jeton. Un événement tardif d'une lecture précédente (fin, erreur) est ignoré.
- Le contrôleur (`show_controller.py`) ne connaît pas Qt : il donne des ordres à une interface `ShowOutput`, implémentée par `ProjectionPresenter`. Les tests de conduite utilisent un faux `ShowOutput`.

> **Version 1.1** : le rendu par défaut est désormais accéléré par la carte graphique (Qt Quick), et la surface décrite ci-dessous devient le rendu « Compatibilité ». Les mesures, les choix et les limites de fidélité sont dans [QUALITE_DIFFUSION.md](QUALITE_DIFFUSION.md). Les garanties de transition (pas de noir, pas de flash, dernière image conservée) sont identiques dans les deux rendus et testées.

## Transition vidéo → image finale

Le risque principal d'un tel logiciel est le « flash » au changement de média (bureau visible, noir, fenêtre vidéo native qui se reconstruit). Solution retenue :

1. **Une seule surface de dessin** (`ui/widgets/video_surface.py`) pour la vidéo, les images fixes et le noir. Les images décodées par Qt Multimedia arrivent par un `QVideoSink` et sont peintes par la surface ; il n'y a ni `QVideoWidget` (fenêtre native), ni changement de widget.
2. L'image finale est **décodée en arrière-plan dès le lancement de la vidéo**, et sa mise à l'échelle est mise en cache.
3. À l'événement `EndOfMedia`, la surface remplace la dernière image vidéo par l'image finale au prochain rafraîchissement. Les images invalides que Qt émet à l'arrêt sont ignorées.
4. Au départ de la séquence suivante, l'image finale reste affichée **jusqu'à la première image** de la nouvelle vidéo : pas de noir intermédiaire.

Un test automatique (`test_transitions_never_paint_black_in_between`) enregistre chaque rafraîchissement de la surface et vérifie la séquence VIDÉO → IMAGE → VIDÉO → IMAGE, sans noir. Il tourne en affichage virtuel : **la validation visuelle sur le vrai vidéoprojecteur reste nécessaire** (protocole, test 4).

« Figer » (conserver la dernière image) est fiable avec cette architecture, puisque la dernière image est copiée en mémoire par l'application elle-même.

## Moteur interchangeable

`PlaybackEngine` (`app/media/playback_engine.py`) définit le contrat : `load(path, jeton)`, `play`, `pause`, `stop`, `seek`, volume, sortie audio, et les signaux `started`, `ended`, `failed`, `frameReady`. Si Qt Multimedia se révélait insuffisant sur certains PC (codecs exotiques, 4K60), un moteur **libmpv** pourrait être ajouté derrière ce contrat sans modifier la conduite ni l'interface.

## Robustesse

- Aucune boîte de dialogue depuis la fenêtre de projection ; les erreurs sont journalisées (`%APPDATA%\RegieVideo\logs`), la projection affiche l'image finale ou du noir.
- Délai de chargement maximal (12 s) : une vidéo bloquée bascule en ERROR au lieu de figer la conduite.
- Vérification avant spectacle : présence, droits de lecture, taille non nulle, extension ; analyse de chaque vidéo en préparation (durée, miniature) qui détecte les codecs non pris en charge et les fichiers corrompus.
- Les vidéos ne sont jamais chargées entièrement en mémoire : seule la séquence en cours est ouverte. Les images finales sont gardées dans un petit cache (séquence en cours et suivante).
- Sortie audio disparue : repli automatique sur la sortie par défaut.
- Mise en veille de l'écran bloquée pendant le spectacle (`SetThreadExecutionState`).
- Exceptions non gérées journalisées.

## Risques et parades

| Risque | Parade |
|---|---|
| Flash entre vidéo et image | Surface unique, image préchargée, test automatique + vérification manuelle filmée |
| Commande déclenchée deux fois | Filtre des répétitions automatiques + anti-rebond par action |
| Sortie accidentelle du mode spectacle | Double frappe Ctrl+Maj+Q en 3 s, Alt+F4 refusé |
| Ctrl+Maj+Échap intercepté par Windows | Remplacé par Ctrl+Maj+Q (documenté) |
| Codec non pris en charge découvert en direct | Analyse en préparation + vérification au lancement |
| Notifications / perte de focus Windows | Documenté ; fenêtre au premier plan ; réinitialisation de l'état clavier à la perte de focus |
| Conversion d'image par le processeur en 4K | Résolu en 1.1 : rendu GPU par défaut, sans conversion (mesures dans QUALITE_DIFFUSION.md) |
| Chrominance 4:2:2/4:4:4 réduite par Qt | Signalé par le diagnostic ; moteur libmpv possible derrière `PlaybackEngine` |
| DLL FFmpeg absentes de l'exécutable | `RegieVideo.exe --self-test` exécuté dans la CI Windows après chaque compilation |

## Ce qui reste à vérifier sous Windows, sur le matériel réel

- Absence de flash visible sur le vidéoprojecteur (protocole, tests 4 et 5).
- Fluidité de vidéos 1080p50/60 et 4K sur le PC de régie (décodage matériel D3D11).
- Comportement en mise à l'échelle 125 % / 150 % et en duplication.
- Bascule audio lors du débranchement d'un périphérique.
