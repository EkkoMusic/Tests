import pytest

from app.core.cue_state import ShowState
from app.core.show_controller import ShowController
from app.models import Cue, EndOfShowBehavior

from .fakes import FakeOutput


def make(n=3, end=EndOfShowBehavior.HOLD):
    out = FakeOutput()
    cues = [Cue(name=f"Artiste {i + 1}", video_path=f"/v/{i + 1}.mp4") for i in range(n)]
    ctl = ShowController(cues, out, end)
    ctl.start()
    return ctl, out


def play_to_end(ctl):
    ctl.go()
    ctl.on_media_started(ctl.token)
    ctl.on_media_ended(ctl.token)


def test_start_shows_standby_and_waits():
    ctl, out = make()
    assert ctl.state is ShowState.IDLE
    assert out.calls == [("standby",)]
    assert ctl.position == -1


def test_right_arrow_launches_first_cue():
    ctl, out = make()
    assert ctl.go()
    assert ctl.state is ShowState.LOADING
    assert out.last == ("play", "Artiste 1", 1)
    ctl.on_media_started(1)
    assert ctl.state is ShowState.PLAYING


def test_right_arrow_ignored_while_playing():
    ctl, out = make()
    ctl.go()
    ctl.on_media_started(ctl.token)
    n = len(out.calls)
    assert not ctl.go()
    assert ctl.state is ShowState.PLAYING
    assert len(out.calls) == n


def test_right_arrow_ignored_while_loading():
    ctl, _ = make()
    ctl.go()
    assert not ctl.go()
    assert ctl.position == 0


def test_space_pauses_and_resumes():
    ctl, out = make()
    ctl.go()
    ctl.on_media_started(ctl.token)
    assert ctl.toggle_pause()
    assert ctl.state is ShowState.PAUSED and out.last == ("pause",)
    assert ctl.toggle_pause()
    assert ctl.state is ShowState.PLAYING and out.last == ("resume",)


def test_right_arrow_ignored_while_paused():
    ctl, _ = make()
    ctl.go()
    ctl.on_media_started(ctl.token)
    ctl.toggle_pause()
    assert not ctl.go()
    assert ctl.state is ShowState.PAUSED


def test_space_ignored_outside_playback():
    ctl, _ = make()
    assert not ctl.toggle_pause()
    assert ctl.state is ShowState.IDLE


def test_end_of_video_goes_to_holding_without_auto_advance():
    ctl, out = make()
    play_to_end(ctl)
    assert ctl.state is ShowState.HOLDING
    assert out.last == ("end", "Artiste 1", True)
    assert [c for c in out.calls if c[0] == "play"] == [("play", "Artiste 1", 1)]


def test_holding_waits_for_manual_go():
    ctl, out = make()
    play_to_end(ctl)
    ctl.on_media_ended(ctl.token)  # un événement en double ne change rien
    assert ctl.state is ShowState.HOLDING
    assert ctl.go()
    assert out.last == ("play", "Artiste 2", 2)


def test_full_show_sequence_in_order():
    ctl, out = make(3)
    for _ in range(3):
        play_to_end(ctl)
    assert [c[1] for c in out.calls if c[0] == "play"] == ["Artiste 1", "Artiste 2", "Artiste 3"]
    assert ctl.state is ShowState.HOLDING


def test_last_cue_does_not_go_out_of_bounds():
    ctl, out = make(2, EndOfShowBehavior.BLACK)
    play_to_end(ctl)
    play_to_end(ctl)
    assert ctl.go()
    assert ctl.state is ShowState.FINISHED
    assert out.last == ("end_of_show", EndOfShowBehavior.BLACK)
    assert not ctl.go()  # rien après la fin
    assert ctl.state is ShowState.FINISHED
    assert ctl.next_cue is None


def test_restart_replays_current_video_from_start():
    ctl, out = make()
    ctl.go()
    ctl.on_media_started(ctl.token)
    assert ctl.restart()
    assert ctl.state is ShowState.LOADING
    assert out.last == ("play", "Artiste 1", 2)
    ctl.on_media_started(2)
    assert ctl.state is ShowState.PLAYING


def test_restart_from_pause_and_holding():
    ctl, out = make()
    ctl.go(); ctl.on_media_started(ctl.token); ctl.toggle_pause()
    assert ctl.restart() and out.last[1] == "Artiste 1"
    ctl.on_media_started(ctl.token); ctl.on_media_ended(ctl.token)
    assert ctl.restart() and out.last[1] == "Artiste 1"


def test_restart_ignored_before_first_cue():
    ctl, _ = make()
    assert not ctl.restart()


def test_stale_events_from_previous_video_are_ignored():
    ctl, _ = make()
    ctl.go(); ctl.on_media_started(1)
    ctl.restart()  # jeton 2
    ctl.on_media_ended(1)  # fin tardive de la première lecture
    assert ctl.state is ShowState.LOADING
    ctl.on_media_error(1, "ancien")
    assert ctl.state is ShowState.LOADING


def test_blackout_is_reversible_while_playing():
    ctl, out = make()
    ctl.go(); ctl.on_media_started(ctl.token)
    assert ctl.toggle_blackout()
    assert ctl.state is ShowState.BLACKOUT and out.blackout
    assert ("pause",) in out.calls
    ctl.toggle_blackout()
    assert ctl.state is ShowState.PLAYING and not out.blackout
    assert out.last == ("resume",)


def test_blackout_restores_pause_without_resuming():
    ctl, out = make()
    ctl.go(); ctl.on_media_started(ctl.token); ctl.toggle_pause()
    ctl.toggle_blackout(); ctl.toggle_blackout()
    assert ctl.state is ShowState.PAUSED
    assert out.calls.count(("resume",)) == 0


def test_blackout_restores_holding_and_idle():
    ctl, _ = make()
    ctl.toggle_blackout(); ctl.toggle_blackout()
    assert ctl.state is ShowState.IDLE
    play_to_end(ctl)
    ctl.toggle_blackout()
    assert not ctl.go()  # aucune commande de conduite pendant le noir
    ctl.toggle_blackout()
    assert ctl.state is ShowState.HOLDING


def test_blackout_during_loading_freezes_video_until_restore():
    ctl, out = make()
    ctl.go()
    ctl.toggle_blackout()
    ctl.on_media_started(ctl.token)
    assert out.last == ("pause",)
    assert ctl.state_before_blackout is ShowState.PLAYING
    ctl.toggle_blackout()
    assert ctl.state is ShowState.PLAYING and out.last == ("resume",)


def test_video_ending_during_blackout_restores_to_holding():
    ctl, out = make()
    ctl.go(); ctl.on_media_started(ctl.token)
    ctl.toggle_blackout()
    ctl.on_media_ended(ctl.token)  # fin survenue juste avant la pause
    assert ctl.state is ShowState.BLACKOUT and out.blackout
    ctl.toggle_blackout()
    assert ctl.state is ShowState.HOLDING
    assert ("resume",) not in out.calls


def test_back_goes_to_previous_cue_without_playing():
    ctl, out = make()
    play_to_end(ctl); play_to_end(ctl)
    plays = out.names().count("play")
    assert ctl.back()
    assert ctl.state is ShowState.HOLDING and ctl.position == 0
    assert out.last == ("end", "Artiste 1", False)
    assert out.names().count("play") == plays
    ctl.go()
    assert out.last == ("play", "Artiste 2", ctl.token)


def test_back_from_first_cue_returns_to_standby():
    ctl, out = make()
    play_to_end(ctl)
    assert ctl.back()
    assert ctl.state is ShowState.IDLE and out.last == ("standby",)
    assert not ctl.back()  # déjà au début : rien


def test_back_ignored_during_playback():
    ctl, _ = make()
    play_to_end(ctl)
    ctl.go(); ctl.on_media_started(ctl.token)
    assert not ctl.back()
    ctl.toggle_pause()
    assert not ctl.back()
    assert ctl.position == 1


def test_back_from_finished():
    ctl, out = make(1)
    play_to_end(ctl); ctl.go()
    assert ctl.state is ShowState.FINISHED
    assert ctl.back()
    assert ctl.state is ShowState.HOLDING and out.last == ("end", "Artiste 1", False)


def test_media_error_goes_to_error_with_safe_visual_and_go_continues():
    ctl, out = make()
    ctl.go()
    ctl.on_media_error(ctl.token, "codec")
    assert ctl.state is ShowState.ERROR
    assert out.calls[-2:] == [("stop",), ("error", "Artiste 1")]
    assert ctl.go()
    assert out.last == ("play", "Artiste 2", ctl.token)


def test_error_during_playback_and_retry():
    ctl, _ = make()
    ctl.go(); ctl.on_media_started(ctl.token)
    ctl.on_media_error(ctl.token, "lecture interrompue")
    assert ctl.state is ShowState.ERROR
    assert ctl.restart()
    assert ctl.state is ShowState.LOADING


def test_empty_show_does_not_crash():
    ctl, out = make(0)
    assert ctl.go()
    assert ctl.state is ShowState.FINISHED
    assert not ctl.restart()
    assert ctl.back()
    assert ctl.state is ShowState.IDLE


def test_show_can_be_restarted():
    ctl, out = make(2)
    play_to_end(ctl); play_to_end(ctl); ctl.go()
    ctl.start()
    assert ctl.state is ShowState.IDLE and ctl.position == -1
    ctl.go()
    assert out.last[1] == "Artiste 1"


@pytest.mark.parametrize("n", [1, 40])
def test_many_cues(n):
    ctl, out = make(n)
    for _ in range(n):
        play_to_end(ctl)
    assert out.names().count("play") == n
