# Protocole de tests — Régie Vidéo

## 1. Tests automatisés

```bat
set QT_QPA_PLATFORM=offscreen
python -m pytest -q
```

| Domaine | Fichier | Exemples de comportements vérifiés |
|---|---|---|
| Machine à états | `tests/core/test_state_machine.py` | transitions autorisées / interdites |
| Conduite | `tests/core/test_show_controller.py` | Flèche droite lance la bonne séquence ; ignorée en PLAYING, LOADING et PAUSED ; Espace pause/reprise ; fin de vidéo → HOLDING sans enchaînement ; HOLDING attend une action ; R relance ; BLACKOUT réversible (y compris pendant un chargement ou une fin de vidéo) ; Flèche gauche ; erreurs ; dernier cue sans dépassement ; conduite vide ; 40 séquences ; relance du spectacle |
| Clavier | `tests/core/test_keyboard.py` | répétition automatique filtrée, touche maintenue, anti-rebond, double frappe de sortie, raccourcis réservés par Windows refusés |
| Persistance | `tests/core/test_persistence.py` | ordre conservé après sauvegarde, chemins relatifs/absolus, dossier transportable, JSON invalide, version future, valeurs inconnues, écriture atomique, autosauvegarde, paramètres |
| Validation | `tests/core/test_validator.py` | vidéo absente, fichier vide, image absente, codec illisible |
| Moteur réel | `tests/ui/test_projection_media.py` | lecture MP4 avec/sans audio, image finale après EndOfMedia, **aucun rafraîchissement noir entre vidéo et image**, image portrait sans déformation, fichier corrompu, fichier absent, pause prolongée, noir, R, sortie par double raccourci, Alt+F4 refusé, trois spectacles consécutifs |
| Interface | `tests/ui/test_main_window.py` | 12 séquences ajoutées, réordonnées, enregistrées et rouvertes à l'identique ; confirmation de suppression ; médias manquants ; lancement et sortie du mode spectacle |

Ces tests tournent aussi sur **Windows** dans la CI GitHub, qui compile ensuite `RegieVideo.exe` et exécute `RegieVideo.exe --self-test`.

## 2. Vérification manuelle sur le matériel réel

Ce qui ne peut pas être automatisé : rendu sur le vidéoprojecteur, fluidité réelle, son, comportement de Windows. À faire **sur le PC de régie**, avec le vidéoprojecteur de la salle si possible.

Préparez un spectacle de test avec : une vidéo 1920×1080 avec son, une sans son, une vidéo 4K ou très longue (> 10 min), une vidéo verticale, une image finale 16:9, une image verticale, et 30 à 50 séquences (copies).

| # | Test | Résultat attendu | OK |
|---|---|---|---|
| 1 | Lancer en 1920×1080, mise à l'échelle 100 % | Projection plein écran, aucune bordure, curseur invisible | ☐ |
| 2 | Recommencer en 125 % puis 150 % | Identique ; image nette, proportions conservées | ☐ |
| 3 | Mode « Dupliquer » avec le vidéoprojecteur | Même image sur les deux écrans, aucune interface visible | ☐ |
| 4 | Flèche droite → vidéo → fin | **Aucun flash** (bureau, blanc, noir) entre la dernière image vidéo et l'image finale. Filmer l'écran au ralenti avec un téléphone pour le confirmer | ☐ |
| 5 | Flèche droite entre l'image finale et la vidéo suivante | Pas de noir intermédiaire | ☐ |
| 6 | Flèche droite pendant la lecture, maintenue enfoncée | Rien ne se passe | ☐ |
| 7 | Espace, attendre 10 minutes, Espace | La vidéo reprend au même endroit | ☐ |
| 8 | Image finale affichée 15 minutes | Image stable, pas de veille, pas d'économiseur | ☐ |
| 9 | B pendant une vidéo, puis B | Noir immédiat ; la vidéo reprend là où elle était | ☐ |
| 10 | R pendant la lecture, en pause, sur l'image finale | La vidéo repart du début | ☐ |
| 11 | Flèche gauche sur l'image finale | Fin de la séquence précédente affichée, sans lecture | ☐ |
| 12 | Vidéo avec son / sans son | Son correct / aucune erreur | ☐ |
| 13 | Débrancher le casque ou la carte son USB pendant la lecture | La lecture continue, le son bascule sur la sortie par défaut | ☐ |
| 14 | Renommer une vidéo avant le lancement | Signalée dans la vérification ; en spectacle, image finale ou noir, conduite non bloquée | ☐ |
| 15 | 50 séquences | Interface fluide (défilement, glisser-déposer), conduite complète jouée | ☐ |
| 16 | Ctrl+Maj+Q une fois, attendre 5 s, une fois | Aucune sortie | ☐ |
| 17 | Ctrl+Maj+Q deux fois | Retour à la préparation | ☐ |
| 18 | Relancer le spectacle trois fois de suite | Chaque fois depuis l'image d'attente, sans redémarrer | ☐ |
| 19 | Alt+F4 en mode spectacle | Sans effet | ☐ |
| 20 | Fermer Régie Vidéo par le Gestionnaire des tâches avec des modifications, relancer | Proposition de récupération de l'autosauvegarde | ☐ |
| 21 | Vidéo 4K / H.265 / ProRes | Lecture fluide, ou signalée « Illisible » avant le spectacle | ☐ |

Notez la version de Windows, la carte graphique, le modèle de vidéoprojecteur et la résolution utilisée. En cas d'écart, joignez `%APPDATA%\RegieVideo\logs\regie-video.log`.
