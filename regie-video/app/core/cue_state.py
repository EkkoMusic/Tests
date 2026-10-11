"""Machine à états explicite du mode spectacle.

Aucune décision de conduite ne repose sur des booléens dispersés : l'état
courant et la table des transitions autorisées sont la seule source de vérité.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Callable

log = logging.getLogger(__name__)


class ShowState(str, Enum):
    IDLE = "IDLE"            # mode spectacle initialisé, en attente du premier départ
    LOADING = "LOADING"      # chargement du média de la séquence
    PLAYING = "PLAYING"      # vidéo en lecture
    PAUSED = "PAUSED"        # vidéo en pause
    HOLDING = "HOLDING"      # image finale / noir / dernière image affiché, en attente
    BLACKOUT = "BLACKOUT"    # projection masquée, état précédent mémorisé
    ERROR = "ERROR"          # incident de lecture, sortie visuelle de secours
    FINISHED = "FINISHED"    # conduite terminée


S = ShowState

#: Transitions autorisées. Toute autre transition est un bug et lève une exception.
ALLOWED_TRANSITIONS: dict[ShowState, frozenset[ShowState]] = {
    S.IDLE: frozenset({S.LOADING, S.BLACKOUT, S.FINISHED}),
    S.LOADING: frozenset({S.PLAYING, S.HOLDING, S.ERROR, S.BLACKOUT}),
    S.PLAYING: frozenset({S.PAUSED, S.HOLDING, S.ERROR, S.BLACKOUT, S.LOADING}),
    S.PAUSED: frozenset({S.PLAYING, S.HOLDING, S.ERROR, S.BLACKOUT, S.LOADING}),
    S.HOLDING: frozenset({S.LOADING, S.HOLDING, S.IDLE, S.FINISHED, S.BLACKOUT}),
    # La sortie du noir restaure l'état mémorisé, quel qu'il soit.
    S.BLACKOUT: frozenset({S.IDLE, S.LOADING, S.PLAYING, S.PAUSED, S.HOLDING, S.ERROR, S.FINISHED}),
    S.ERROR: frozenset({S.LOADING, S.HOLDING, S.IDLE, S.FINISHED, S.BLACKOUT}),
    S.FINISHED: frozenset({S.HOLDING, S.IDLE, S.BLACKOUT}),
}


class InvalidTransition(RuntimeError):
    pass


StateListener = Callable[[ShowState, ShowState], None]


class CueStateMachine:
    """Porte l'état courant et vérifie chaque transition."""

    def __init__(self, initial: ShowState = ShowState.IDLE) -> None:
        self._state = initial
        self._listeners: list[StateListener] = []

    @property
    def state(self) -> ShowState:
        return self._state

    def can(self, target: ShowState) -> bool:
        return target in ALLOWED_TRANSITIONS[self._state]

    def transition(self, target: ShowState) -> None:
        if not self.can(target):
            raise InvalidTransition(f"Transition interdite : {self._state.value} → {target.value}")
        previous, self._state = self._state, target
        log.debug("État : %s → %s", previous.value, target.value)
        for listener in list(self._listeners):
            listener(previous, target)

    def reset(self, state: ShowState = ShowState.IDLE) -> None:
        self._state = state

    def add_listener(self, listener: StateListener) -> None:
        self._listeners.append(listener)
