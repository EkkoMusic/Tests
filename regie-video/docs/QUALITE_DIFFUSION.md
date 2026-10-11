# Qualité de diffusion — audit, choix et limites (version 1.1)

Ce document rend compte de l'évolution « diffusion vidéo et audio haute qualité » : ce qui a été mesuré, ce qui a changé, ce qui est vérifié et ce qui ne l'est pas encore.

Environnements de mesure :
- conteneur Linux à 4 cœurs, **sans carte graphique** (rendu OpenGL logiciel Mesa sous Xvfb, décodage logiciel FFmpeg) ;
- CI GitHub **Windows Server 2025** (Direct3D 11 logiciel WARP, sans GPU).

Les valeurs absolues seront meilleures sur un PC équipé d'une carte graphique. Ce sont les écarts entre les deux rendus qui comptent.

---

## 1. Audit du moteur 1.0

| Point vérifié | Constat |
|---|---|
| Lecture | `QMediaPlayer` (Qt 6.12, backend FFmpeg 9), lecture progressive depuis le disque : aucune vidéo n'est chargée en mémoire. |
| Rendu 1.0 | Chaque image décodée était convertie en `QImage` (`QVideoFrame.toImage()`), puis mise à l'échelle et peinte par le processeur, sur le fil de l'interface. Sous Windows, avec décodage matériel, cela implique en plus une recopie GPU → CPU de chaque image. |
| Résolutions non standard | Acceptées (3289 × 1480, 4:4:4, largeur impaire). La rotation et les pixels non carrés sont appliqués par Qt (vérifié). |
| Accélération matérielle | Qt utilise D3D11VA/DXVA2 sous Windows quand le codec et la résolution le permettent, avec repli automatique sur le décodage logiciel. Qt n'expose pas d'API indiquant lequel est utilisé (seulement un message de journal). |
| Média suivant | Chargé au moment du GO. Délai mesuré jusqu'à la première image : 8 à 48 ms, du 320 × 180 à la 4K. L'image précédente reste affichée pendant ce temps, donc aucun noir. Un préchargement (double lecteur) n'apporterait rien de mesurable : il n'a pas été ajouté. |

### Mesure de la limite du rendu 1.0 (Xvfb, 1920 × 1080)

Coût sur le fil principal = temps passé par image décodée à l'afficher.

| Vidéo (5 s) | Rendu processeur 1.0 : coût / image | Durée réelle de lecture | Rendu GPU 1.1 : coût / image | Durée réelle de lecture |
|---|---|---|---|---|
| 1920 × 1080, 60 i/s | 22 ms (p95 46 ms) | 8,2 s | 0,04 ms | 5,3 s |
| 3288 × 1480, 25 i/s, 43 Mbit/s | 55 ms (p95 164 ms) | 9,1 s | 0,06 ms | 5,2 s |
| 3840 × 2160, 30 i/s, 65 Mbit/s | 81 ms (p95 258 ms) | **15,9 s** | 0,06 ms | **5,2 s** |

Conclusion : le rendu 1.0 ne tenait pas le temps réel au-delà du 1080p sur cette machine. Le changement de technique de rendu apporte donc un avantage concret, et il est démontré.

---

## 2. Ce qui a changé

### Rendu accéléré (nouveau, par défaut)

- **Surface Qt Quick** (`assets/qml/ProjectionSurface.qml`, `app/ui/widgets/quick_surface.py`) : les images décodées sont confiées telles quelles au `VideoOutput` de Qt.
  - Aucune conversion ni mise à l'échelle par le processeur.
  - Aucune recopie GPU → CPU quand le décodage est matériel : la texture est partagée.
  - La conversion YUV → RVB est faite par les shaders de Qt Multimedia.
- **Fin de vidéo sans flash.** Branché directement sur le lecteur, le `VideoOutput` devient noir *avant* l'événement de fin (mesuré). Régie Vidéo relaie donc lui-même les images et ne transmet jamais l'image vide de fin. La dernière image reste à l'écran jusqu'à la bascule vers l'image finale. Vidéo, image fixe et noir sont trois couches d'une même scène : la bascule est atomique.
- **Images finales.** Elles sont décodées et mises à la taille exacte de l'écran dans un fil d'arrière-plan (filtre lissé, jamais d'agrandissement par le processeur), puis envoyées au GPU pendant la vidéo.
- **Repli explicite.** Le rendu « Compatibilité (processeur) » de la 1.0 reste disponible (Paramètres → Projection). Il est utilisé automatiquement, et journalisé, si Qt Quick ne peut pas démarrer.

### Mise à l'échelle

| Mode | Conséquence |
|---|---|
| Adapter à l'écran (défaut) | Toute l'image visible, sans déformation, bandes noires si les formats diffèrent. |
| Remplir l'écran | Écran rempli, sans déformation ; les bords qui dépassent sont coupés. |
| Taille native (1:1) | Aucune mise à l'échelle : 1 pixel du média = 1 pixel physique. Un média plus grand que l'écran est coupé. Utile seulement à la résolution exacte du projecteur. |

Aucune déformation n'est possible : les proportions viennent de la taille d'affichage du média (rotation et pixels non carrés compris).

### Analyse et diagnostic

- **FFprobe** est exécuté dans un processus séparé, avec un délai maximal, depuis un fil d'arrière-plan : un fichier corrompu ne peut pas bloquer l'interface. Sous Windows, FFprobe est livré dans `RegieVideo\_internal\ffmpeg\` (build LGPL de BtbN). Sans FFprobe, l'analyse se replie sur les métadonnées Qt, et le panneau l'indique comme « partielle ».
- **Verdict par média** : « Compatible et vérifié », « Compatible présumé, test nécessaire », « Risque de performances », « Média non pris en charge » ou « Analyse impossible ».
  - Il combine le codec, le profil, la profondeur, la chrominance, la résolution par rapport aux limites des décodeurs matériels, la cadence, le débit, l'entrelacement, la cadence variable, le HDR et l'espace colorimétrique.
  - Il intègre aussi un **décodage réel** par le moteur et les capacités du système (écran, sortie audio).
  - L'extension du fichier n'est jamais un critère.
- **Télémétrie de lecture** : délai de démarrage, images sautées (déduites des horodatages des images livrées par le moteur), écart maximal entre deux images, vitesse réelle. Elle est journalisée à chaque séquence du spectacle.
- **« Vérifier la diffusion »** : bilan *Prêt pour le spectacle* / *Vérification matérielle recommandée* / *Problèmes bloquants*.
  - Le test de lecture réel est optionnel, avec plusieurs passages à différentes positions. Il se fait sans aucune image affichée et le son coupé.
  - « Prêt » n'est donné que si ce test a été fait et réussi : une compatibilité *détectée* n'est pas une fluidité *mesurée*.

---

## 3. Fidélité de l'image : mesures

### Couleurs (source RVB 200, 60, 40 encodée en H.264 sans perte visible)

| Fichier | Rendu accéléré (GPU) | Rendu processeur |
|---|---|---|
| BT.709, plage limitée (cas courant HD/4K) | 198, 59, 39 ✅ | 198, 59, 39 ✅ |
| BT.709, plage complète | 201, 60, 42 ✅ | 190, 45, 45 ❌ |
| Non étiqueté (HD) | 198, 59, 39 ✅ | 187, 45, 42 ❌ |
| BT.601 étiqueté (SD) | 213, 73, 37 ❌ | 202, 60, 41 ✅ |
| HDR10 (PQ, BT.2020) | affiché, converti en SDR | **image noire** ❌ |

L'écart BT.601 du rendu GPU correspond exactement à l'application de la matrice BT.709. C'est une limite de Qt 6.12, qu'on ne peut pas corriger depuis l'application. Le diagnostic la signale (« Fichier étiqueté BT.601… »). Les exports d'animation HD et 4K sont en BT.709 dans l'immense majorité des cas.

### Autres constats

- **Chrominance.** Qt Multimedia convertit les vidéos 4:2:2 et 4:4:4 (ProRes 422/4444, H.264 High 4:4:4, PNG…) en 4:2:0 avant l'affichage. La luminance est intacte, mais la définition des couleurs est réduite de moitié, surtout visible sur les contours très saturés. C'est signalé dans le diagnostic. Seul un autre moteur (libmpv) pourrait l'éviter.
- **HDR.** Le HDR10 et le HLG sont convertis en SDR par les shaders de Qt. La qualité de cette conversion **n'a pas été vérifiée sur un vrai projecteur** : le diagnostic demande une vérification visuelle.
- **Aucun traitement ajouté par Régie Vidéo** : pas de netteté, pas de débruitage, pas de réencodage, pas de modification de cadence, pas de désentrelacement. Les vidéos entrelacées sont signalées.
- **Cadence et fréquence de l'écran.** Le diagnostic compare la cadence de chaque vidéo à la fréquence annoncée par Windows. Par exemple, 25 i/s sur un écran 60 Hz donne un rythme irrégulier (alternance 2-3), et le diagnostic suggère 50 Hz. Une vidéo à 59,94 i/s sur 60 Hz saute ou répète une image environ toutes les 17 s. Régie Vidéo ne change jamais lui-même la fréquence de l'écran.

---

## 4. Fidélité du son

| Exigence | État |
|---|---|
| Lecture sans réencodage du fichier | ✅ décodage direct par FFmpeg |
| Hauteur et vitesse inchangées | ✅ aucune modification de vitesse ; la synchronisation se fait sur l'horloge audio (comportement de Qt) |
| Pas d'égaliseur, de compresseur ni de normalisation | ✅ aucun traitement dans Régie Vidéo |
| Volume 100 % par défaut, sans amplification | ✅ le gain appliqué est plafonné à 1,0 (volume séquence × volume général) |
| Multicanal | Lu par Qt. S'il y a plus de canaux que la sortie, Windows ou Qt font le mixage réduit (signalé) |
| Fréquences courantes (44,1 / 48 / 96 kHz) | Lues (test sur 48 kHz AAC, 5.1 AAC, PCM 24 bits 96 kHz) |
| Sortie absente ou débranchée | Détectée et signalée (barre d'état, diagnostic) ; repli automatique sur la sortie par défaut |
| **Sortie bit à bit** | **Non garantie.** Qt utilise WASAPI en mode partagé : Windows mixe et peut rééchantillonner à la fréquence de la sortie. Le diagnostic signale les différences de fréquence. Conseil : régler la sortie Windows sur la fréquence des fichiers (souvent 48 kHz). |

---

## 5. Ce qui est vérifié, et où

| Vérification | Linux (Xvfb, OpenGL logiciel) | CI Windows | À faire sur le PC du spectacle |
|---|---|---|---|
| Tests métier et interface (offscreen) | ✅ | ✅ | — |
| Rendu GPU : proportions, bandes noires, remplir, natif, noir, dernière image, image finale | ✅ | ✅ (Direct3D 11 WARP) | Vérification visuelle |
| Analyse FFprobe de tous les médias de test | ✅ | ✅ (FFprobe livré) | — |
| Exécutable : lecture, rendu GPU, FFprobe (`--self-test`) | ✅ (build Linux) | ✅ | Lancer `RegieVideo.exe --self-test` |
| Décodage matériel D3D11VA | ❌ (pas de GPU) | ❌ (pas de GPU) | **Protocole de performance** |
| 4K60, HEVC 10 bits, gros débits sur le portable | ❌ | ❌ | **Protocole de performance** |
| Absence de flash sur le projecteur, HDR, couleurs | ❌ | ❌ | **Protocole visuel** |

## 6. Limites restantes et pistes

1. **Chrominance 4:2:2 / 4:4:4 réduite en 4:2:0 par Qt** : piste libmpv. Le contrat `PlaybackEngine` est prêt à accueillir un moteur libmpv, à n'intégrer que si cette limite gêne visiblement sur vos films.
2. **BT.601 en rendu GPU** : exporter en BT.709, ou utiliser le rendu « Compatibilité » si toutes les vidéos sont en SD BT.601.
3. **Télémétrie** : elle mesure les images livrées par le décodeur, pas leur présentation finale par l'écran (synchronisation verticale), qui n'est pas accessible depuis Qt.
4. **Décodage matériel** : son utilisation effective n'est pas exposée par Qt. Elle se déduit indirectement du test de lecture (vitesse 1,00×, aucune image sautée).
5. **Fréquence d'affichage** : elle est lue, mais jamais modifiée par l'application.
