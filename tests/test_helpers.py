"""Module-level pure(ish) helpers: manifest IO, lyrics/pitch persistence,
LRC export, tokenizing. No setup() required — these are plain functions."""

import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import routes  # noqa: E402


# ── manifest helpers ─────────────────────────────────────────────────────────

def test_manifest_path_prefers_yaml_over_yml(tmp_path):
    (tmp_path / "manifest.yaml").write_text("a: 1\n")
    (tmp_path / "manifest.yml").write_text("a: 2\n")
    assert routes._manifest_path(tmp_path).name == "manifest.yaml"


def test_manifest_path_falls_back_to_yml(tmp_path):
    (tmp_path / "manifest.yml").write_text("a: 1\n")
    assert routes._manifest_path(tmp_path).name == "manifest.yml"


def test_read_write_manifest_roundtrip(tmp_path):
    (tmp_path / "manifest.yaml").write_text("schema: 1\n")
    manifest = routes._read_manifest(tmp_path)
    assert manifest == {"schema": 1}
    manifest["lyrics"] = "lyrics.json"
    routes._write_manifest(tmp_path, manifest)
    assert routes._read_manifest(tmp_path) == {"schema": 1, "lyrics": "lyrics.json"}


def test_vocals_rel_path_finds_by_id_case_insensitive(tmp_path):
    manifest = {"stems": [{"id": "Drums", "file": "d.wem"}, {"id": "VOCALS", "file": "v.wem"}]}
    assert routes._vocals_rel_path(manifest) == "v.wem"


def test_vocals_rel_path_none_when_absent(tmp_path):
    assert routes._vocals_rel_path({"stems": [{"id": "drums", "file": "d.wem"}]}) is None
    assert routes._vocals_rel_path({}) is None


# ── lyrics tokens ─────────────────────────────────────────────────────────────

def test_lyrics_tokens_empty_without_manifest_key(tmp_path):
    assert routes._lyrics_tokens(tmp_path, {}) == []


def test_lyrics_tokens_empty_when_file_missing(tmp_path):
    assert routes._lyrics_tokens(tmp_path, {"lyrics": "lyrics.json"}) == []


def test_lyrics_tokens_parses_and_filters_nonpositive_duration(tmp_path):
    (tmp_path / "lyrics.json").write_text(json.dumps([
        {"t": 1.0, "d": 0.5, "w": "hel"},
        {"t": 1.5, "d": 0.0, "w": "skip"},   # d<=0 dropped
        {"t": 2.0, "d": -1, "w": "skip2"},   # negative dropped
        "not a dict",                         # dropped
        {"t": "bad", "d": 1.0, "w": "x"},     # non-numeric t dropped
    ]), encoding="utf-8")
    tokens = routes._lyrics_tokens(tmp_path, {"lyrics": "lyrics.json"})
    assert tokens == [{"t": 1.0, "d": 0.5, "w": "hel"}]


def test_lyrics_tokens_empty_on_corrupt_json(tmp_path):
    (tmp_path / "lyrics.json").write_text("{not json", encoding="utf-8")
    assert routes._lyrics_tokens(tmp_path, {"lyrics": "lyrics.json"}) == []


def test_lyrics_tokens_empty_when_not_a_list(tmp_path):
    (tmp_path / "lyrics.json").write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert routes._lyrics_tokens(tmp_path, {"lyrics": "lyrics.json"}) == []


# ── pitch file ────────────────────────────────────────────────────────────────

def test_read_pitch_file_none_without_manifest_key(tmp_path):
    assert routes._read_pitch_file(tmp_path, {}) is None


def test_read_pitch_file_none_when_missing_or_corrupt(tmp_path):
    assert routes._read_pitch_file(tmp_path, {"vocal_pitch": "vocal_pitch.json"}) is None
    (tmp_path / "vocal_pitch.json").write_text("{not json", encoding="utf-8")
    assert routes._read_pitch_file(tmp_path, {"vocal_pitch": "vocal_pitch.json"}) is None


def test_read_pitch_file_returns_dict(tmp_path):
    (tmp_path / "vocal_pitch.json").write_text(json.dumps({"version": 1, "notes": []}), encoding="utf-8")
    assert routes._read_pitch_file(tmp_path, {"vocal_pitch": "vocal_pitch.json"}) == {"version": 1, "notes": []}


def test_read_pitch_file_none_when_not_a_dict(tmp_path):
    (tmp_path / "vocal_pitch.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert routes._read_pitch_file(tmp_path, {"vocal_pitch": "vocal_pitch.json"}) is None


# ── job locks ─────────────────────────────────────────────────────────────────

def test_job_lock_for_returns_same_lock_for_same_filename():
    a = routes._job_lock_for("song.sloppak")
    b = routes._job_lock_for("song.sloppak")
    assert a is b


def test_job_lock_for_returns_different_locks_for_different_filenames():
    a = routes._job_lock_for("one.sloppak")
    b = routes._job_lock_for("two.sloppak")
    assert a is not b


# ── atomic json write ───────────────────────────────────────────────────────

def test_atomic_write_json_writes_and_cleans_tmp(tmp_path):
    target = tmp_path / "out.json"
    routes._atomic_write_json(target, {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert not target.with_suffix(".json.tmp").exists()


# ── lyrics/pitch persistence ─────────────────────────────────────────────────

def test_persist_lyrics_writes_file_and_updates_manifest(tmp_path):
    (tmp_path / "manifest.yaml").write_text("schema: 1\n")
    manifest = {"schema": 1}
    segments = [
        {"start": 1.0, "end": 1.5, "text": "hel"},
        {"start": 1.5, "end": 1.4, "text": "bad"},  # end<start -> d<=0, dropped
        {"start": 2.0, "text": "no end"},            # missing key, dropped
        {"start": 3.0, "end": 3.5},                  # no text -> ""
    ]
    count = routes._persist_lyrics(tmp_path, manifest, segments, tmp_path / "song.sloppak", is_zip=False)
    assert count == 2

    lyrics = json.loads((tmp_path / "lyrics.json").read_text(encoding="utf-8"))
    assert lyrics == [
        {"t": 1.0, "d": 0.5, "w": "hel"},
        {"t": 3.0, "d": 0.5, "w": ""},
    ]
    assert manifest["lyrics"] == "lyrics.json"
    assert routes._read_manifest(tmp_path)["lyrics"] == "lyrics.json"


def test_persist_lyrics_rezips_when_sloppak_is_zip_form(tmp_path):
    source_dir = tmp_path / "song_src"
    source_dir.mkdir()
    (source_dir / "manifest.yaml").write_text("schema: 1\n")
    dlc_path = tmp_path / "song.sloppak"
    with zipfile.ZipFile(dlc_path, "w") as zf:
        zf.writestr("manifest.yaml", "schema: 1\n")

    routes._persist_lyrics(source_dir, {"schema": 1}, [{"start": 0, "end": 1, "text": "hi"}],
                            dlc_path, is_zip=True)

    with zipfile.ZipFile(dlc_path) as zf:
        names = zf.namelist()
    assert "lyrics.json" in names


def test_persist_pitch_writes_versioned_payload_and_updates_manifest(tmp_path):
    (tmp_path / "manifest.yaml").write_text("schema: 1\n")
    manifest = {"schema": 1}
    notes = [{"t": 0.0, "d": 0.5, "midi": 60}]
    routes._persist_pitch(tmp_path, manifest, notes, tmp_path / "song.sloppak", is_zip=False)

    payload = json.loads((tmp_path / "vocal_pitch.json").read_text(encoding="utf-8"))
    assert payload == {"version": 1, "notes": notes}
    assert manifest["vocal_pitch"] == "vocal_pitch.json"


# ── LRC export ────────────────────────────────────────────────────────────────

def test_format_lrc_basic_timestamps():
    segments = [
        {"start": 0.0, "text": "Hello"},
        {"start": 65.5, "text": "World"},
    ]
    lrc = routes._format_lrc(segments)
    assert lrc == "[00:00.00]Hello\n[01:05.50]World\n"


def test_format_lrc_skips_malformed_segments():
    segments = [{"text": "no start"}, "not a dict", {"start": 1.0}]
    lrc = routes._format_lrc(segments)
    assert lrc == "[00:01.00]\n"


def test_format_lrc_empty_segments_yields_trailing_newline_only():
    assert routes._format_lrc([]) == "\n"
