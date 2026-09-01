# Vidra

Vidra keeps a durable SQLite queue of videos, analysis runs, transcript
artifacts, and HTML report registrations under `~/.vidra` (or `VIDRA_HOME`).
The accompanying `video-analyzer` skill writes transcripts and frame samples
into the same artifact tree.

The CLI deliberately separates queueing from analysis: adding a video never
starts work. A report can be registered only after an explicit `analyze begin`
and only when a non-empty transcript exists. Removing a queue/report record
preserves files on disk.

```bash
python -m pip install -e tools/vidra
vidra init
vidra queue add 'https://www.youtube.com/watch?v=...'
vidra queue list
vidra analyze begin VIDEO --user-approved
vidra analyze fail VIDEO --error 'transcription unavailable'
vidra doctor
vidra serve
```

## Web interface

The complete React and Mantine application lives in `tools/vidra/web`. Its
catalog transformations are kept in pure functions; rendering and network I/O
stay at the UI boundary.

```bash
cd tools/vidra/web
npm ci
npm run check
npm run build
rsync -a --delete dist/ "${VIDRA_HOME:-$HOME/.vidra}/web/"
```

`vidra serve` exposes the resulting static build and the read-only
`/api/videos` catalog from the same origin.
