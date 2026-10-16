# Lyrics Karaoke

A [feedBack](https://github.com/got-feedback/feedBack) plugin that makes a song karaoke-ready. It aligns plain lyric text against the song's isolated vocals stem, extracts the pitch of every syllable, and draws a scrolling pitch ribbon above the highway while the song plays.

It replaces the older standalone Lyrics Sync plugin. The alignment and save steps that Lyrics Sync used to do now live here.

## Features

- **One-screen setup.** Pick a song, see what's missing, paste the lyrics, click **Build Karaoke**. Alignment is skipped when the song already has synced lyrics.
- **Whisper alignment.** Sends the vocals stem and your lyric text to the demucs server's `/align` endpoint. Syllable, word, or line granularity, with an optional language hint.
- **Per-syllable pitch.** Uses the demucs server's `/pitch` endpoint (CREPE) when it's available. Otherwise it falls back to local `librosa.pyin`.
- **Saved into the song.** Writes `lyrics.json` and `vocal_pitch.json` into the song package and updates its manifest. A zipped package is re-zipped, with a one-time `.bak` copy of the original.
- **In-player karaoke ribbon.** A **Karaoke** button toggles between the normal lyrics and a pitch ribbon: one bar per syllable, placed by pitch, with the syllable text and a sweeping playhead.
- **Live mic feedback.** A 🎤 button next to the Karaoke toggle draws your sung pitch over the ribbon (YIN, in the browser).
- **LRC export.** Download the alignment as a standard `.lrc` file.

## Requirements

- **A `.feedpak` or `.sloppak` song with a vocals stem.** The manifest needs a stem with id `vocals`. Songs without one can be split with the Stem Splitter plugin.
- **A running [feedBack Demucs Server](https://github.com/got-feedBack/feedBack-demucs-server) with the `/align` endpoint.** Alignment always goes through the server. The `/pitch` endpoint is optional.
- **The server URL in the app config (`demucs_server_url`).** Set it in **Settings → Audio → Demucs server**. If you run the managed local server from the Stem Splitter plugin, tick **Use for the whole app** in the Stem Splitter settings and it fills in this URL for you.
- **Python libraries for the local pitch fallback:** `librosa`, `numpy` and `soundfile` (see `requirements.txt`).

Archive-format songs are not supported. The Karaoke button stays hidden for them.

## Install

Lyrics Karaoke is bundled with the feedBack Desktop app, so desktop users already have it.

For a self-hosted (Docker) install:

```bash
cd /path/to/feedBack/plugins
git clone https://github.com/got-feedBack/feedBack-plugin-lyrics-karaoke.git lyrics_karaoke
docker compose restart
```

The directory name must be `lyrics_karaoke` to match the `id` in `plugin.json`.

## Usage

### Build karaoke for a song

1. Open **Plugins** in the sidebar and click **Lyrics Karaoke**.
2. Check the banner at the top. It tells you if the alignment server is unreachable or not configured.
3. Search for a song and pick it. Only songs with split stems are listed. The checklist shows whether the song has a vocals stem, synced lyrics and per-syllable pitch.
4. If the song has no synced lyrics yet, paste the lyrics (one line per line) or upload a `.txt` file. Set the language hint and granularity if needed.
5. Click **Build Karaoke**. The plugin aligns the lyrics, saves them, then extracts pitch. Pitch extraction can take a minute.
6. When it shows **Karaoke ready ✓**, click **Open in player**, **Download .lrc**, or **Re-extract pitch**. **Download .lrc** needs an alignment from this session.

### Sing along

1. Play the song.
2. Click **Karaoke** in the player. In the v3 UI it sits in the **Plugin controls** popover on the player rail.
   - If the song has synced lyrics and a vocals stem but no pitch yet, the button reads **Generate Karaoke** and runs pitch extraction first.
   - The button stays disabled when the song has no synced lyrics or no vocals stem. Hover it to see why.
3. Click 🎤 to turn on live mic feedback. Click **Karaoke** again to go back to the normal lyrics.

## API routes

All routes live under `/api/plugins/lyrics_karaoke/`.

| Route | Method | Purpose |
|---|---|---|
| `status?filename=…` | GET | Per-song flags: `is_sloppak`, `has_vocals`, `has_lyrics`, `has_pitch`, `pitch_count` |
| `server-status` | GET | Checks the configured server's `/health` |
| `data?filename=…` | GET | Merged `[{t, d, w, midi?}]` tokens for the in-player ribbon |
| `align` | POST | Sends the vocals stem + `lyrics_text` (+ `language`, `granularity`) to the server's `/align` and returns its segments |
| `save-lyrics` | POST | Saves alignment `segments` as the song's `lyrics.json` |
| `generate-pitch` | POST | Extracts per-syllable pitch and saves `vocal_pitch.json` |
| `export` | POST | Returns the given `segments` as a downloadable `.lrc` file |

## Troubleshooting

| Message | What to do |
|---|---|
| "No demucs server configured" | Set `demucs_server_url` (see Requirements). |
| "Cannot connect to alignment server" / "Alignment request timed out" | Check that the demucs server is running and reachable at that URL. Alignment requests time out after 300 s. |
| "No vocals stem — split stems with Demucs first." | Split the song with the Stem Splitter plugin, then pick it again. |
| "No synced lyrics — align lyrics first." | Run the alignment step (paste lyrics, then **Build Karaoke**) before extracting pitch. |
| "Pitch extraction produced no voiced syllables" | The vocals stem is probably silent or noise only. Re-split the song or try another one. |
| "Not a sloppak" | The song is not a `.feedpak` / `.sloppak` package. |

If the server has no `/pitch` endpoint, pitch extraction falls back to local pYIN on its own and logs `/pitch not available on demucs server, using local pYIN`.

## Tests

`tests/test_helpers.py` covers the module-level helpers: manifest IO, lyrics and pitch persistence, LRC formatting and tokenizing. CI runs it through the org's reusable workflow. To run it locally:

```bash
pip install pytest fastapi pyyaml -r requirements.txt
python -m pytest tests
```
