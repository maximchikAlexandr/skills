# Vidra

Vidra is the shared local registry and web catalog for analyzed information
sources. Video reports and GitHub project reports have separate lifecycle and
database tables, while sharing one protected index and artifact home.

Register a completed GitHub report:

```bash
vidra project register owner/repository --report-file report.html \
  --title "Project" --revision COMMIT_SHA --summary "Short description" --stars 123 \
  --category developer-tools/example
```

Register an analyzed AI skill in the same GitHub-project section (one repository
may contribute multiple skill reports):

```bash
vidra project register-skill owner/repository \
  --skill-path skills/example/SKILL.md --report-file report.html \
  --title "Example skill" --revision COMMIT_SHA --summary "Behavioral contract" \
  --stars 123 --category ai/skills/example
```

The command validates the GitHub identity, assigns a stable 12-character report
hash, stores `<hash>.html`, injects a `Все проекты` return link, and exposes the
record through the catalog API. `vidra project list --json` is the canonical
deduplication registry for GitHub research.

Queue project research without starting it:

```bash
vidra project queue-add owner/repository
vidra project queue-list --json
vidra project queue-begin owner/repository --user-approved
vidra project queue-fail owner/repository --error "reason"
```

Project analysis has its own SQLite lifecycle, while the web catalog merges
project and video items into one chronological source queue. Registering a
project report completes the matching queue item automatically.

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
vidra report add-video REPORT_HASH 'https://www.youtube.com/watch?v=...'
vidra report add REPORT_HASH VIDEO --transcript-file transcript.vtt --report-file updated.html
vidra report additions REPORT_HASH
vidra report validate REPORT_HASH
vidra report normalize
vidra report move REPORT_HASH ai/code-review
vidra report list --category ai
vidra category tree
vidra doctor
vidra serve
```

Completed reports use a stable 12-character hash as both their filename and
lookup key. `report add` accepts that key, verifies the new video's transcript,
validates that every source has a player, preserves a backup, atomically
replaces the report with the supplied integrated HTML, and associates the new
video without reprocessing existing transcripts. `report add-video` creates a
resumable addition manifest and records its target report; `report additions`
lists pending and completed additions. `report normalize` upgrades
legacy filenames while preserving the old files on disk.

Reports live in real slash-separated category directories. The web interface
renders those directories as a navigable hierarchy. Vidra warns when a leaf
directory reaches 10 reports; follow the skill's `category-reindexing.md`
workflow and use `report move` so the filesystem and SQLite stay consistent.

GitHub project reports use the same real-directory model under `projects/`.
Use `vidra project list --category ...`, `vidra project move HASH CATEGORY`, and
`vidra project category-tree`. Registration warns after a project leaf exceeds
15 reports and links to the project-analysis reindexing instructions.

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
