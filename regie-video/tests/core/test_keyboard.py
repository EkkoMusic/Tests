from app.core.keyboard_controller import (
    DEFAULT_BINDINGS,
    ExitGuard,
    KeyboardController,
    ShowAction,
    bindings_from_config,
    describe_key,
)


def kb(interval=400):
    return KeyboardController(dict(DEFAULT_BINDINGS), interval)


def test_default_bindings_cover_all_actions():
    assert set(DEFAULT_BINDINGS.values()) == set(ShowAction)
    assert "Ctrl+Shift+Esc" not in DEFAULT_BINDINGS  # réservé par Windows


def test_mapping():
    k = kb(0)
    for key, action in [("Right", ShowAction.GO), ("Space", ShowAction.PAUSE_TOGGLE), ("R", ShowAction.RESTART),
                        ("B", ShowAction.BLACKOUT_TOGGLE), ("Left", ShowAction.BACK)]:
        assert k.press(key, False, 0) is action
        k.release(key, False)
    assert k.press("X", False, 0) is None


def test_auto_repeat_is_filtered():
    k = kb(0)
    assert k.press("Right", False, 0) is ShowAction.GO
    assert k.press("Right", True, 30) is None
    assert k.press("Right", True, 60) is None


def test_held_key_without_repeat_flag_fires_once():
    k = kb(0)
    assert k.press("Right", False, 0) is ShowAction.GO
    assert k.press("Right", False, 500) is None  # pas de relâchement entre les deux
    k.release("Right", False)
    assert k.press("Right", False, 600) is ShowAction.GO


def test_repeat_protection_interval():
    k = kb(400)
    assert k.press("Right", False, 0) is ShowAction.GO
    k.release("Right", False)
    assert k.press("Right", False, 150) is None
    k.release("Right", False)
    assert k.press("Right", False, 450) is ShowAction.GO


def test_focus_loss_reset():
    k = kb(0)
    k.press("Right", False, 0)
    k.reset()
    assert k.press("Right", False, 10) is ShowAction.GO


def test_exit_guard_requires_double_press():
    g = ExitGuard(confirm=True, window_ms=3000)
    assert not g.request(0)
    assert g.armed
    assert g.request(1000)
    assert not g.armed


def test_exit_guard_expires():
    g = ExitGuard(confirm=True, window_ms=3000)
    assert not g.request(0)
    assert not g.request(5000)  # trop tard : réarmé
    assert g.request(6000)


def test_exit_guard_without_confirmation():
    assert ExitGuard(confirm=False).request(0)


def test_bindings_from_config_fallbacks():
    assert bindings_from_config(None) == DEFAULT_BINDINGS
    assert bindings_from_config({"Right": "nope"}) == DEFAULT_BINDINGS
    custom = {k: a.value for k, a in DEFAULT_BINDINGS.items()}
    custom.pop("Right")
    custom["PgDown"] = "go"  # télécommande de présentation
    assert bindings_from_config(custom)["PgDown"] is ShowAction.GO
    reserved = dict(custom, **{"Ctrl+Shift+Esc": "exit"})
    reserved.pop("Ctrl+Shift+Q")
    assert bindings_from_config(reserved) == DEFAULT_BINDINGS


def test_describe_key_in_french():
    assert describe_key("Ctrl+Shift+Q") == "Ctrl + Maj + Q"
    assert describe_key("Right") == "Flèche droite"
