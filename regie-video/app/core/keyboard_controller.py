"""Traduction des touches en commandes de spectacle.

Le module ne dépend pas de Qt : les touches sont décrites par leur texte
portable (« Right », « Space », « Ctrl+Shift+Q »...), ce qui permet
d'enregistrer des raccourcis personnalisés dans les paramètres.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ShowAction(str, Enum):
    GO = "go"
    PAUSE_TOGGLE = "pause_toggle"
    RESTART = "restart"
    BLACKOUT_TOGGLE = "blackout_toggle"
    BACK = "back"
    EXIT = "exit"

    @property
    def label(self) -> str:
        return {
            ShowAction.GO: "Lancer la séquence suivante",
            ShowAction.PAUSE_TOGGLE: "Pause / reprise",
            ShowAction.RESTART: "Recommencer la vidéo actuelle",
            ShowAction.BLACKOUT_TOGGLE: "Écran noir (activer / désactiver)",
            ShowAction.BACK: "Revenir à la séquence précédente, sans la lancer",
            ShowAction.EXIT: "Quitter le mode spectacle",
        }[self]


#: Ctrl+Maj+Échap est réservé par Windows (Gestionnaire des tâches) : il
#: n'atteint jamais l'application. La sortie utilise donc Ctrl+Maj+Q,
#: à presser deux fois (voir ExitGuard).
DEFAULT_BINDINGS: dict[str, ShowAction] = {
    "Right": ShowAction.GO,
    "Space": ShowAction.PAUSE_TOGGLE,
    "R": ShowAction.RESTART,
    "B": ShowAction.BLACKOUT_TOGGLE,
    "Left": ShowAction.BACK,
    "Ctrl+Shift+Q": ShowAction.EXIT,
}

#: Combinaisons interceptées par Windows, inutilisables comme raccourcis.
RESERVED_BY_SYSTEM = frozenset({"Ctrl+Shift+Esc", "Ctrl+Alt+Del", "Alt+Tab", "Alt+F4", "Meta+L", "Meta+D"})

KEY_LABELS_FR = {
    "Right": "Flèche droite",
    "Left": "Flèche gauche",
    "Space": "Espace",
    "Ctrl": "Ctrl",
    "Shift": "Maj",
    "Esc": "Échap",
}


def describe_key(key_text: str) -> str:
    """« Ctrl+Shift+Q » → « Ctrl + Maj + Q »."""
    return " + ".join(KEY_LABELS_FR.get(part, part) for part in key_text.split("+"))


@dataclass
class KeyboardController:
    """Filtre les répétitions et associe une touche à une action.

    * Les répétitions automatiques (touche maintenue) sont toujours ignorées.
    * ``min_interval_ms`` : délai minimal entre deux déclenchements de la même
      action (protection contre les doubles appuis involontaires).
    """

    bindings: dict[str, ShowAction]
    min_interval_ms: int = 400

    def __post_init__(self) -> None:
        self._last_fired: dict[ShowAction, float] = {}
        self._held: set[str] = set()

    def press(self, key_text: str, is_auto_repeat: bool, now_ms: float) -> ShowAction | None:
        if is_auto_repeat or key_text in self._held:
            return None
        action = self.bindings.get(key_text)
        if action is None:
            return None
        self._held.add(key_text)
        last = self._last_fired.get(action)
        if last is not None and now_ms - last < self.min_interval_ms:
            return None
        self._last_fired[action] = now_ms
        return action

    def release(self, key_text: str, is_auto_repeat: bool) -> None:
        if not is_auto_repeat:
            self._held.discard(key_text)

    def reset(self) -> None:
        """À appeler quand la fenêtre perd le focus : les relâchements sont perdus."""
        self._held.clear()


@dataclass
class ExitGuard:
    """Sortie volontaire : le raccourci doit être pressé deux fois de suite.

    Aucune boîte de dialogue n'est affichée : en mode « Dupliquer », elle
    serait vue par le public. Le second appui doit intervenir dans la fenêtre
    ``window_ms`` ; sinon le premier appui est oublié.
    """

    confirm: bool = True
    window_ms: int = 3000

    def __post_init__(self) -> None:
        self._armed_at: float | None = None

    @property
    def armed(self) -> bool:
        return self._armed_at is not None

    def request(self, now_ms: float) -> bool:
        if not self.confirm:
            return True
        if self._armed_at is not None and now_ms - self._armed_at <= self.window_ms:
            self._armed_at = None
            return True
        self._armed_at = now_ms
        return False

    def cancel(self) -> None:
        self._armed_at = None


def bindings_from_config(config: dict[str, str] | None) -> dict[str, ShowAction]:
    """Construit la table touche → action depuis les paramètres enregistrés.

    Une configuration invalide, incomplète ou utilisant une combinaison
    réservée par Windows est remplacée par les raccourcis par défaut.
    """
    if not config:
        return dict(DEFAULT_BINDINGS)
    bindings: dict[str, ShowAction] = {}
    for key, value in config.items():
        try:
            action = ShowAction(value)
        except ValueError:
            return dict(DEFAULT_BINDINGS)
        if key in RESERVED_BY_SYSTEM:
            return dict(DEFAULT_BINDINGS)
        bindings[key] = action
    if set(bindings.values()) != set(ShowAction):
        return dict(DEFAULT_BINDINGS)
    return bindings


def keys_for(bindings: dict[str, ShowAction], action: ShowAction) -> list[str]:
    return [k for k, a in bindings.items() if a is action]
