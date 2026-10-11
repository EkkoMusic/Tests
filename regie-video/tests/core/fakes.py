from app.models import Cue, EndOfShowBehavior


class FakeOutput:
    """Enregistre les ordres de rendu donnés par le contrôleur."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.blackout = False

    def show_standby(self):
        self.calls.append(("standby",))

    def play_cue(self, cue: Cue, token: int):
        self.calls.append(("play", cue.name, token))

    def show_cue_end(self, cue: Cue, live: bool):
        self.calls.append(("end", cue.name, live))

    def show_error(self, cue):
        self.calls.append(("error", cue.name if cue else None))

    def show_end_of_show(self, behavior: EndOfShowBehavior):
        self.calls.append(("end_of_show", behavior))

    def pause(self):
        self.calls.append(("pause",))

    def resume(self):
        self.calls.append(("resume",))

    def stop(self):
        self.calls.append(("stop",))

    def set_blackout(self, enabled: bool):
        self.blackout = enabled
        self.calls.append(("blackout", enabled))

    @property
    def last(self):
        return self.calls[-1] if self.calls else None

    def names(self):
        return [c[0] for c in self.calls]
