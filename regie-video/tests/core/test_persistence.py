import json
import os
from pathlib import Path

import pytest

from app.core.cue_manager import CueManager, name_from_file
from app.models import Cue, EndBehavior, EndOfShowBehavior, Show
from app.persistence.app_settings import AppSettings
from app.persistence.autosave import AutosaveStore
from app.persistence.project_repository import ProjectError, load_show, save_show


def touch(path: Path, data: bytes = b"x") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path)


def sample_show(root: Path, n=12) -> Show:
    show = Show(name="Gala 2027")
    for i in range(n):
        show.cues.append(
            Cue(
                name=f"Artiste {i + 1}",
                video_path=touch(root / "medias" / f"artiste{i + 1}.mp4"),
                image_path=touch(root / "medias" / f"artiste{i + 1}.png"),
                volume=50 + i,
                duration_ms=1000 * (i + 1),
            )
        )
    show.settings.end_of_show = EndOfShowBehavior.BLACK
    return show


def test_roundtrip_preserves_order_and_fields(tmp_path):
    show = sample_show(tmp_path)
    CueManager(show).move(0, 5)
    expected = [(c.id, c.name, c.video_path, c.image_path, c.volume) for c in show.cues]
    path = save_show(show, tmp_path / "gala_2027.regievideo")
    loaded = load_show(path)
    assert loaded.name == "Gala 2027"
    assert [(c.id, c.name, c.video_path, c.image_path, c.volume) for c in loaded.cues] == expected
    assert loaded.settings.end_of_show is EndOfShowBehavior.BLACK
    assert loaded.cues[0].duration_ms == show.cues[0].duration_ms


def test_media_inside_project_folder_is_saved_relative(tmp_path):
    show = sample_show(tmp_path, 1)
    path = save_show(show, tmp_path / "spectacle.regievideo")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == "regie-video-show"
    assert data["format_version"] == 1
    assert data["cues"][0]["video"] == "medias/artiste1.mp4"


def test_project_folder_is_transportable(tmp_path):
    src = tmp_path / "clé USB"
    show = sample_show(src, 2)
    save_show(show, src / "spectacle.regievideo")
    moved = tmp_path / "autre PC"
    os.rename(src, moved)
    loaded = load_show(moved / "spectacle.regievideo")
    assert all(Path(c.video_path).is_file() for c in loaded.cues)


def test_media_outside_project_folder_stays_absolute(tmp_path):
    outside = touch(tmp_path / "ailleurs" / "film.mp4")
    show = Show(cues=[Cue(name="A", video_path=outside)])
    path = save_show(show, tmp_path / "projet" / "s.regievideo")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert Path(data["cues"][0]["video"]).is_absolute()
    assert load_show(path).cues[0].video_path == os.path.normpath(outside)


def test_windows_absolute_path_is_kept(tmp_path):
    path = tmp_path / "s.regievideo"
    save_show(Show(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cues"] = [{"name": "A", "video": "D:\\Spectacle\\a.mp4"}]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert load_show(path).cues[0].video_path.startswith("D:")


@pytest.mark.parametrize("content, fragment", [
    ("{pas du json", "endommagé"),
    ('{"format": "autre"}', "n'est pas un spectacle"),
    ('{"format": "regie-video-show", "format_version": 99, "cues": []}', "plus récente"),
    ('{"format": "regie-video-show", "format_version": 1, "cues": "x"}', "illisible"),
    ('[1, 2]', "n'est pas un spectacle"),
])
def test_invalid_project_raises_french_error(tmp_path, content, fragment):
    path = tmp_path / "bad.regievideo"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ProjectError) as err:
        load_show(path)
    assert fragment in str(err.value)


def test_missing_project_file(tmp_path):
    with pytest.raises(ProjectError, match="introuvable"):
        load_show(tmp_path / "nope.regievideo")


def test_unknown_enum_values_fall_back(tmp_path):
    path = tmp_path / "s.regievideo"
    path.write_text(json.dumps({
        "format": "regie-video-show", "format_version": 1,
        "settings": {"end_of_show": "???"},
        "cues": [{"id": "a", "name": "A", "end_behavior": "???", "volume": "fort"},
                 {"id": "a", "name": "B"}],  # identifiant dupliqué
    }), encoding="utf-8")
    show = load_show(path)
    assert show.cues[0].end_behavior is EndBehavior.IMAGE
    assert show.cues[0].volume == 100
    assert show.cues[0].id != show.cues[1].id


def test_save_is_atomic_and_leaves_no_temp_files(tmp_path):
    path = tmp_path / "s.regievideo"
    save_show(sample_show(tmp_path, 3), path)
    save_show(sample_show(tmp_path, 4), path)
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".tmp")] == []
    assert len(load_show(path).cues) == 4


def test_autosave_roundtrip(tmp_path):
    store = AutosaveStore(tmp_path / "autosave")
    show = sample_show(tmp_path, 3)
    store.write("session-1", show, str(tmp_path / "s.regievideo"))
    entries = store.entries()
    assert len(entries) == 1 and entries[0].cue_count == 3
    recovered = AutosaveStore.load(entries[0])
    assert [c.id for c in recovered.cues] == [c.id for c in show.cues]
    store.discard("session-1")
    assert store.entries() == []


def test_autosave_ignores_corrupt_files(tmp_path):
    store = AutosaveStore(tmp_path)
    (tmp_path / "x.autosave.json").write_text("corrompu", encoding="utf-8")
    assert store.entries() == []


def test_app_settings_roundtrip_and_validation(tmp_path):
    s = AppSettings()
    s.push_recent("/a.regievideo"); s.push_recent("/b.regievideo"); s.push_recent("/a.regievideo")
    s.master_volume = 80
    s.save(tmp_path / "settings.json")
    loaded = AppSettings.load(tmp_path / "settings.json")
    assert loaded.recent_projects[:2] == [str(Path("/a.regievideo")), str(Path("/b.regievideo"))]
    assert loaded.master_volume == 80
    bad = AppSettings.from_dict({"master_volume": 500, "confirm_exit": "oui", "repeat_interval_ms": 1})
    assert bad.master_volume == 100 and bad.confirm_exit is True and bad.repeat_interval_ms == 100
    assert AppSettings.load(tmp_path / "absent.json") == AppSettings()


def test_cue_manager_operations(tmp_path):
    video = touch(tmp_path / "03_marie-dupont.mp4")
    touch(tmp_path / "03_marie-dupont.png")
    ignored = touch(tmp_path / "notes.txt")
    show = Show()
    m = CueManager(show)
    created = m.add_videos([video, ignored, touch(tmp_path / "b.mp4")])
    assert [c.name for c in created] == ["Marie Dupont", "B"]
    assert created[0].image_path.endswith(".png") and created[0].end_behavior is EndBehavior.IMAGE
    assert created[1].end_behavior is EndBehavior.BLACK
    dup = m.duplicate(created[0].id)
    assert show.cues[1] is dup and dup.id != created[0].id
    assert m.move(0, 2) and show.cues[2] is created[0]
    assert not m.move(0, 9)
    assert m.rename(dup.id, "  Nouveau nom ") and dup.name == "Nouveau nom"
    assert not m.rename(dup.id, "   ")
    assert m.remove(dup.id) >= 0 and len(show.cues) == 2
    assert m.remove("inconnu") == -1


def test_relink_missing_files(tmp_path):
    show = Show(cues=[Cue(name="A", video_path=str(tmp_path / "old" / "a.mp4"))])
    new = touch(tmp_path / "nouveau" / "sous" / "a.mp4")
    assert CueManager(show).relink_missing(str(tmp_path / "nouveau")) == 1
    assert show.cues[0].video_path == os.path.normpath(new)


def test_name_from_file():
    assert name_from_file("01 - jean_paul.MP4") == "Jean Paul"
    assert name_from_file("DJ McFly.mp4") == "DJ McFly"
