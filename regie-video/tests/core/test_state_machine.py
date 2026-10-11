import pytest

from app.core.cue_state import ALLOWED_TRANSITIONS, CueStateMachine, InvalidTransition, ShowState


def test_every_state_has_transitions():
    assert set(ALLOWED_TRANSITIONS) == set(ShowState)


def test_valid_transition_notifies_listeners():
    sm = CueStateMachine()
    seen = []
    sm.add_listener(lambda old, new: seen.append((old, new)))
    sm.transition(ShowState.LOADING)
    sm.transition(ShowState.PLAYING)
    assert sm.state is ShowState.PLAYING
    assert seen == [(ShowState.IDLE, ShowState.LOADING), (ShowState.LOADING, ShowState.PLAYING)]


def test_invalid_transition_raises():
    sm = CueStateMachine()
    with pytest.raises(InvalidTransition):
        sm.transition(ShowState.PLAYING)  # IDLE → PLAYING sans chargement


def test_end_of_video_never_leads_directly_to_loading_next():
    # PLAYING peut aller vers LOADING uniquement pour « recommencer » (R) ;
    # la fin de vidéo, elle, mène à HOLDING (vérifié dans test_show_controller).
    assert ShowState.HOLDING in ALLOWED_TRANSITIONS[ShowState.PLAYING]
    assert ShowState.LOADING not in ALLOWED_TRANSITIONS[ShowState.LOADING]
