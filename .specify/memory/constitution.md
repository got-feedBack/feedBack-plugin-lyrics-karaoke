# Lyrics Karaoke Plugin Constitution

This plugin turns a sloppak song into a karaoke target: per-syllable
alignment + per-syllable pitch, rendered as a falling-bar ribbon over
the highway. It superseded the standalone `lyrics_sync` plugin and
absorbed its alignment endpoints.

## Principles

### 1. Sloppak Only, Vocals Stem Required

The two-stage pipeline (Whisper alignment + pYIN/CREPE pitch) requires
an isolated vocals stem. archive songs are rejected up front with a
clear error. Both `lyrics.json` and `vocal_pitch.json` are persisted
*inside* the sloppak (manifest is patched, zip-form is re-zipped with
a one-time `.bak`).

### 2. Two-Stage Pipeline, Independently Recoverable

`Build Karaoke` is conceptually one button, but the two stages
(alignment, pitch) MUST be independently runnable. If alignment
already exists, only pitch needs running. If a user wants to re-run
pitch (e.g. after a server upgrade with better /pitch quality), the
plugin MUST allow that without re-aligning.

### 3. Server-First, Local Fallback for Pitch

Pitch extraction prefers the demucs server's CREPE-backed `/pitch`
endpoint when available (CREPE on GPU is dramatically more accurate
than CPU pYIN). On any failure (transport error, 404, 501,
`NotImplementedError`) the plugin MUST fall back transparently to
local pYIN so users without the server still work. The chosen
extractor is reported in the API response
(`extractor: "server-crepe" | "local-pyin"`).

### 4. pYIN Quality Heuristics Are Documented

The local pitch path applies three heuristics whose rationale lives in
`routes.py:_extract_pitch_per_syllable`:

- two-pass narrow-range search (discover singer's centre, then narrow
  ±1 octave around the median midi);
- per-syllable mode of semitone-rounded pitches (not Hz median);
- local-neighbour octave-error correction (snap only for >12 semitone
  outliers, ≥2 neighbours, ≥6-semitone improvement).

Future changes MUST preserve those guards or document why they were
relaxed.

### 5. Atomic Writes, Recoverable Re-Zips

All file writes use a `.tmp` + `replace` pattern. Re-zipping a
sloppak first writes a one-time `.bak` of the original, then
atomically replaces. A crash mid-zip leaves the original intact via
the `.bak`.

### 6. Per-Filename Job Lock

Heavy work (pitch extraction) runs in the default executor with a
per-filename `threading.Lock`. Two simultaneous "Generate" presses on
the same song serialize, never race on the same files.

## Inherits from Slopsmith Core Constitution

- `setup(app, context)` contract; uses `config_dir`, `get_dlc_dir`,
  `get_sloppak_cache_dir`.
- Routes under `/api/plugins/lyrics_karaoke/...`.
- Sloppak module for resolution, manifest, source dir.
- Plugin loader serves only the files referenced by `plugin.json`
  (`screen.html`, `screen.js`, `routes.py`); other files (e.g.
  `requirements.txt`) are dev / packaging only.

Where this plugin's principles disagree with the core constitution,
the core wins.
