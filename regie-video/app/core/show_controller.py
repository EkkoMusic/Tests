"""Logique de conduite du mode spectacle.

Le contrôleur décide *quoi* faire ; il ne sait pas *comment* l'afficher.
Le rendu est délégué à un objet qui implémente :class:`ShowOutput`
(la fenêtre de projection en production, un faux objet dans les tests).

Les événements du moteur multimédia (démarrage, fin, erreur) reviennent avec
le jeton fourni au lancement : un événement tardif d'une vidéo précédente est
ainsi ignoré au lieu de perturber la séquence en cours.
"""

from __future__ import annotations

import logging
from typing import Callable, Protocol, Sequence

from app.models import Cue, EndOfShowBehavior

from .cue_state import CueStateMachine, ShowState

log = logging.getLogger(__name__)


class ShowOutput(Protocol):
    """Ce que le contrôleur demande à la sortie de projection."""

    def show_standby(self) -> None:
        """Afficher l'image d'attente (ou du noir)."""

    def play_cue(self, cue: Cue, token: int) -> None:
        """Charger puis lire la vidéo. L'affichage précédent reste visible
        jusqu'à la première image de la nouvelle vidéo."""

    def show_cue_end(self, cue: Cue, live: bool) -> None:
        """Afficher l'état de fin de la séquence. ``live`` indique que la vidéo
        vient réellement de se terminer (la dernière image est donc disponible)."""

    def show_error(self, cue: Cue | None) -> None:
        """Sortie visuelle de secours après un incident de lecture."""

    def show_end_of_show(self, behavior: EndOfShowBehavior) -> None: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self) -> None: ...

    def set_blackout(self, enabled: bool) -> None: ...


class ShowController:
    """Pilote la conduite à partir des commandes opérateur et des événements média."""

    def __init__(
        self,
        cues: Sequence[Cue],
        output: ShowOutput,
        end_of_show: EndOfShowBehavior = EndOfShowBehavior.HOLD,
    ) -> None:
        self._cues = list(cues)
        self._out = output
        self._end_of_show = end_of_show
        self._sm = CueStateMachine()
        self._position = -1          # séquence affichée / jouée (-1 : avant la première)
        self._token = 0
        self._before_blackout: ShowState | None = None
        self._resume_after_blackout = False
        self.on_state_changed: Callable[[ShowState, ShowState], None] | None = None
        self._sm.add_listener(self._notify)

    # ------------------------------------------------------------------ état
    @property
    def state(self) -> ShowState:
        return self._sm.state

    @property
    def position(self) -> int:
        return self._position

    @property
    def current_cue(self) -> Cue | None:
        if 0 <= self._position < len(self._cues):
            return self._cues[self._position]
        return None

    @property
    def next_cue(self) -> Cue | None:
        nxt = self._position + 1
        return self._cues[nxt] if nxt < len(self._cues) else None

    @property
    def token(self) -> int:
        return self._token

    @property
    def state_before_blackout(self) -> ShowState | None:
        return self._before_blackout

    def _notify(self, old: ShowState, new: ShowState) -> None:
        if self.on_state_changed:
            self.on_state_changed(old, new)

    # -------------------------------------------------------------- démarrage
    def start(self) -> None:
        self._sm.reset(ShowState.IDLE)
        self._position = -1
        self._before_blackout = None
        self._resume_after_blackout = False
        self._out.show_standby()
        log.info("Mode spectacle prêt : %d séquence(s)", len(self._cues))

    # -------------------------------------------------------------- commandes
    def go(self) -> bool:
        """Flèche droite : lance la séquence suivante si (et seulement si) on attend."""
        if self.state not in (ShowState.IDLE, ShowState.HOLDING, ShowState.ERROR):
            return False
        target = self._position + 1
        if target >= len(self._cues):
            self._finish()
            return True
        self._launch(target)
        return True

    def toggle_pause(self) -> bool:
        if self.state is ShowState.PLAYING:
            self._sm.transition(ShowState.PAUSED)
            self._out.pause()
            return True
        if self.state is ShowState.PAUSED:
            self._sm.transition(ShowState.PLAYING)
            self._out.resume()
            return True
        return False

    def restart(self) -> bool:
        """R : relance la vidéo de la séquence courante depuis le début."""
        if self.state not in (ShowState.PLAYING, ShowState.PAUSED, ShowState.HOLDING, ShowState.ERROR):
            return False
        if self.current_cue is None:
            return False
        self._launch(self._position)
        return True

    def back(self) -> bool:
        """Flèche gauche : revient à la séquence précédente sans la lancer.

        Jamais pendant une lecture, une pause ou un chargement.
        """
        state = self.state
        if state is ShowState.FINISHED:
            if self.current_cue is None:
                self._position = -1
                self._sm.transition(ShowState.IDLE)
                self._out.show_standby()
            else:
                self._sm.transition(ShowState.HOLDING)
                self._out.show_cue_end(self.current_cue, live=False)
            return True
        if state not in (ShowState.HOLDING, ShowState.ERROR):
            return False
        if self._position <= 0:
            self._position = -1
            self._sm.transition(ShowState.IDLE)
            self._out.show_standby()
        else:
            self._position -= 1
            self._sm.transition(ShowState.HOLDING)
            self._out.show_cue_end(self._cues[self._position], live=False)
        return True

    def toggle_blackout(self) -> bool:
        if self.state is ShowState.BLACKOUT:
            restored = self._before_blackout or ShowState.IDLE
            self._before_blackout = None
            self._sm.transition(restored)
            self._out.set_blackout(False)
            if self._resume_after_blackout and restored is ShowState.PLAYING:
                self._out.resume()
            self._resume_after_blackout = False
            return True
        previous = self.state
        self._before_blackout = previous
        self._resume_after_blackout = previous is ShowState.PLAYING
        self._sm.transition(ShowState.BLACKOUT)
        self._out.set_blackout(True)
        if previous is ShowState.PLAYING:
            self._out.pause()
        return True

    # ------------------------------------------------------ événements média
    def on_media_started(self, token: int) -> None:
        if token != self._token:
            return
        if self.state is ShowState.LOADING:
            self._sm.transition(ShowState.PLAYING)
        elif self.state is ShowState.BLACKOUT and self._before_blackout is ShowState.LOADING:
            # Le noir a été demandé pendant le chargement : on fige la vidéo
            # et on la relancera à la sortie du noir.
            self._out.pause()
            self._before_blackout = ShowState.PLAYING
            self._resume_after_blackout = True

    def on_media_ended(self, token: int) -> None:
        if token != self._token or self.current_cue is None:
            return
        if self.state in (ShowState.PLAYING, ShowState.LOADING, ShowState.PAUSED):
            # Fin de vidéo → maintien. Jamais d'enchaînement automatique.
            self._sm.transition(ShowState.HOLDING)
            self._out.show_cue_end(self.current_cue, live=True)
        elif self.state is ShowState.BLACKOUT and self._before_blackout in (
            ShowState.PLAYING, ShowState.LOADING, ShowState.PAUSED
        ):
            self._before_blackout = ShowState.HOLDING
            self._resume_after_blackout = False
            self._out.show_cue_end(self.current_cue, live=True)

    def on_media_error(self, token: int, message: str = "") -> None:
        if token != self._token:
            return
        log.error("Erreur de lecture (séquence %s) : %s", self._position + 1, message)
        if self.state in (ShowState.LOADING, ShowState.PLAYING, ShowState.PAUSED):
            self._sm.transition(ShowState.ERROR)
            self._out.stop()
            self._out.show_error(self.current_cue)
        elif self.state is ShowState.BLACKOUT and self._before_blackout in (
            ShowState.LOADING, ShowState.PLAYING, ShowState.PAUSED
        ):
            self._before_blackout = ShowState.ERROR
            self._resume_after_blackout = False
            self._out.stop()
            self._out.show_error(self.current_cue)

    # --------------------------------------------------------------- interne
    def _launch(self, index: int) -> None:
        self._position = index
        self._token += 1
        self._sm.transition(ShowState.LOADING)
        cue = self._cues[index]
        log.info("GO séquence %02d « %s »", index + 1, cue.name)
        self._out.play_cue(cue, self._token)

    def _finish(self) -> None:
        if self.state is ShowState.FINISHED:
            return
        self._sm.transition(ShowState.FINISHED)
        self._out.show_end_of_show(self._end_of_show)
        log.info("Conduite terminée")
