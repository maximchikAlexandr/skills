#!/usr/bin/env python3
"""Vidra queue, analysis lifecycle, report registry, and catalog server."""

import datetime as dt
import hashlib
import json
import mimetypes
import os
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import typer

from .domain import CATEGORY_LIMIT, normalize_category, normalize_source, report_hash, require_transition

ROOT = Path(os.environ.get("VIDRA_HOME", Path.home() / ".vidra")).expanduser()
DB = ROOT / "vidra.sqlite3"
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"
WEB = ROOT / "web"
DIRS = (
    ARTIFACTS,
    REPORTS,
    WEB,
    ROOT / "logs",
    ROOT / "run",
    ROOT / "runtime",
    ROOT / "bin",
)


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def init():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    ROOT.chmod(0o700)
    for d in DIRS:
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        d.chmod(0o700)


def source_key(value):
    source = normalize_source(value)
    return source.key, source.url, source.slug


def db():
    init()
    conn = sqlite3.connect(DB, timeout=10)
    DB.chmod(0o600)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS videos(id INTEGER PRIMARY KEY,source_key TEXT NOT NULL UNIQUE,source_url TEXT NOT NULL,source_slug TEXT NOT NULL,title TEXT NOT NULL,request TEXT NOT NULL DEFAULT '',status TEXT NOT NULL CHECK(status IN ('queued','analyzing','analyzed','failed')),artifact_dir TEXT,report_title TEXT,report_concept TEXT,report_path TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,started_at TEXT,completed_at TEXT);CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,error TEXT);CREATE INDEX IF NOT EXISTS videos_status_idx ON videos(status,updated_at);"""
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(videos)")}
    if "report_hash" not in columns:
        conn.execute("ALTER TABLE videos ADD COLUMN report_hash TEXT")
    if "category" not in columns:
        conn.execute("ALTER TABLE videos ADD COLUMN category TEXT NOT NULL DEFAULT 'uncategorized'")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS videos_report_hash_idx ON videos(report_hash)"
    )
    for row in conn.execute(
        "SELECT DISTINCT report_path FROM videos WHERE report_path IS NOT NULL AND report_hash IS NULL"
    ):
        legacy_hash = hashlib.sha256(Path(row["report_path"]).name.encode()).hexdigest()[:12]
        conn.execute(
            "UPDATE videos SET report_hash=? WHERE report_path=?",
            (legacy_hash, row["report_path"]),
        )
    conn.commit()
    return conn


def get(conn, value):
    if value.isdigit():
        row = conn.execute("SELECT * FROM videos WHERE id=?", (int(value),)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM videos WHERE source_key=?", (source_key(value)[0],)
        ).fetchone()
    if row is None:
        raise SystemExit(f"video not found: {value}")
    return row


def view(row):
    out = dict(row)
    report = out.pop("report_path", None)
    out.pop("source_key", None)
    out.pop("artifact_dir", None)
    out["report_url"] = (
        f"reports/{Path(report).relative_to(REPORTS).as_posix()}" if report else None
    )
    return out


def with_report_identity(source: Path, identity: str) -> bytes:
    """Insert or replace the visible report identity banner."""
    marker = '<aside data-vidra-report-id="true"'
    html = source.read_text(encoding="utf-8")
    if marker in html:
        start = html.index(marker)
        end = html.index("</aside>", start) + len("</aside>")
        html = html[:start] + html[end:]
    banner = (
        f'{marker} style="position:relative;margin:12px auto;max-width:1200px;'
        'padding:10px 14px;border:1px solid #d7e2e0;border-radius:10px;'
        'font:600 13px/1.4 ui-monospace,SFMono-Regular,monospace;color:#315b55;'
        'background:#f4faf8">Vidra report <code style="user-select:all">'
        f'{identity}</code></aside>'
    )
    body = html.lower().find("<body")
    if body < 0:
        raise SystemExit("report HTML must contain <body>")
    close = html.find(">", body)
    return (html[: close + 1] + banner + html[close + 1 :]).encode("utf-8")


def emit(payload, pretty=False):
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None))


def category_warning(conn, category):
    count = conn.execute(
        "SELECT count(DISTINCT report_hash) FROM videos WHERE status='analyzed' AND category=?",
        (category,),
    ).fetchone()[0]
    if count < CATEGORY_LIMIT:
        return None
    return {
        "code": "category_reindex_required",
        "category": category,
        "report_count": count,
        "limit": CATEGORY_LIMIT,
        "instructions": "skills/education/video-analyzer/references/category-reindexing.md",
    }


def queue_add(
    source: str,
    title: Optional[str] = typer.Option(None),
    request: str = typer.Option(""),
    allow_reanalysis: bool = typer.Option(False),
):
    conn = db()
    key, url, slug = source_key(source)
    old = conn.execute("SELECT * FROM videos WHERE source_key=?", (key,)).fetchone()
    stamp = now()
    if old:
        if old["status"] == "analyzed" and not allow_reanalysis:
            emit({"result": "already_analyzed", "video": view(old)})
            return
        if old["status"] in {"queued", "analyzing"}:
            emit({"result": "already_" + old["status"], "video": view(old)})
            return
        conn.execute(
            "UPDATE videos SET title=?,request=?,status='queued',error=NULL,started_at=NULL,updated_at=? WHERE id=?",
            (title or old["title"], request, stamp, old["id"]),
        )
        conn.commit()
        emit({"result": "requeued", "video": view(get(conn, str(old["id"])))})
    else:
        cur = conn.execute(
            "INSERT INTO videos(source_key,source_url,source_slug,title,request,status,created_at,updated_at) VALUES(?,?,?,?,?,'queued',?,?)",
            (key, url, slug, title or url, request, stamp, stamp),
        )
        conn.commit()
        emit({"result": "queued", "video": view(get(conn, str(cur.lastrowid)))})


def list_rows(json_output=False, all_rows=False, report=False, category=None):
    conn = db()
    where = (
        "status='analyzed'"
        if report
        else (
            "1=1"
            if all_rows
            else "status IN ('queued','analyzing','failed')"
        )
    )
    if category:
        where += " AND category=?"
    rows = [
        view(r)
        for r in conn.execute(
            f"SELECT * FROM videos WHERE {where} ORDER BY created_at",
            (category,) if category else (),
        )
    ]
    if report:
        rows = list({row["report_hash"]: row for row in rows}.values())
    if json_output:
        emit(rows, True)
    elif not rows:
        print("No reports" if report else "Queue is empty")
    else:
        for r in rows:
            print(
                f'{r["id"]}\t{r["status"]}\t{r["report_title"] or r["title"]}\t{r["source_url"]}'
            )


def queue_remove(video: str, yes: bool = typer.Option(False)):
    conn = db()
    row = get(conn, video)
    payload = {
        "id": row["id"],
        "status": row["status"],
        "title": row["title"],
        "report_path": row["report_path"],
        "artifact_dir": row["artifact_dir"],
    }
    if not yes:
        emit(
            {
                "result": "confirmation_required",
                "will_remove_from_database": payload,
                "files_will_be_preserved": True,
            }
        )
        raise typer.Exit(2)
    with conn:
        conn.execute("DELETE FROM runs WHERE video_id=?", (row["id"],))
        conn.execute("DELETE FROM videos WHERE id=?", (row["id"],))
    emit({"result": "removed", "removed": payload, "files_preserved": True})


def retry(video: str):
    conn = db()
    row = get(conn, video)
    if row["status"] != "failed":
        raise SystemExit(f'expected failed, got {row["status"]}')
    require_transition(row["status"], "queued")
    conn.execute(
        "UPDATE videos SET status='queued',error=NULL,updated_at=? WHERE id=?",
        (now(), row["id"]),
    )
    conn.commit()
    emit({"result": "queued", "video": view(get(conn, str(row["id"])))})


def show(video: str, json_output: bool = typer.Option(False, "--json")):
    row = view(get(db(), video))
    (
        emit(row, True)
        if json_output
        else [print(f"{k}: {v}") for k, v in row.items() if v is not None]
    )


def begin(video: str, user_approved: bool = typer.Option(False)):
    if not user_approved:
        raise SystemExit(
            "requires a separate explicit user request and --user-approved"
        )
    conn = db()
    row = get(conn, video)
    if row["status"] != "queued":
        raise SystemExit(f'expected queued, got {row["status"]}')
    require_transition(row["status"], "analyzing")
    directory = ARTIFACTS / row["source_slug"]
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = now()
    with conn:
        conn.execute(
            "UPDATE videos SET status='analyzing',artifact_dir=?,started_at=?,updated_at=?,error=NULL WHERE id=?",
            (str(directory), stamp, stamp, row["id"]),
        )
        run = conn.execute(
            "INSERT INTO runs(video_id,status,started_at) VALUES(?,'analyzing',?)",
            (row["id"], stamp),
        )
    emit(
        {
            "result": "analyzing",
            "video_id": row["id"],
            "run_id": run.lastrowid,
            "source_url": row["source_url"],
            "artifact_dir": str(directory),
        }
    )


def complete(
    video: str,
    transcript_file: List[Path] = typer.Option(...),
    report_file: Path = typer.Option(...),
    title: str = typer.Option(...),
    also: Optional[List[str]] = typer.Option(None),
    concept: str = typer.Option(""),
    category: str = typer.Option("uncategorized"),
):
    conn = db()
    rows = [get(conn, video)] + [get(conn, value) for value in (also or [])]
    unique = {row["id"]: row for row in rows}
    rows = list(unique.values())
    bad = [
        f'{row["id"]}:{row["status"]}' for row in rows if row["status"] != "analyzing"
    ]
    if bad:
        raise SystemExit("expected analyzing: " + ", ".join(bad))
    try:
        category = normalize_category(category)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--category") from error
    source = report_file.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".html":
        raise SystemExit("--report-file must be an existing HTML file")
    transcripts = [value.expanduser().resolve() for value in transcript_file]
    if len(transcripts) < len(rows):
        raise SystemExit(
            "one non-empty --transcript-file is required for every covered video"
        )
    invalid = [
        str(path)
        for path in transcripts
        if not path.is_file() or path.stat().st_size < 100
    ]
    if invalid:
        raise SystemExit("missing or empty transcript: " + ", ".join(invalid))
    stamp = now()
    identity = report_hash(
        source.read_bytes(), tuple(row["source_key"] for row in rows), stamp
    )
    name = f"{identity}.html"
    report_dir = REPORTS / category
    report_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = report_dir / name
    target.write_bytes(with_report_identity(source, identity))
    target.chmod(0o600)
    with conn:
        for row in rows:
            conn.execute(
                "UPDATE videos SET status='analyzed',report_title=?,report_concept=?,report_path=?,report_hash=?,category=?,completed_at=?,updated_at=?,error=NULL WHERE id=?",
                (title, concept, str(target), identity, category, stamp, stamp, row["id"]),
            )
            conn.execute(
                "UPDATE runs SET status='analyzed',finished_at=? WHERE id=(SELECT id FROM runs WHERE video_id=? AND status='analyzing' ORDER BY id DESC LIMIT 1)",
                (stamp, row["id"]),
            )
    payload = {
            "result": "analyzed",
            "video_ids": [row["id"] for row in rows],
            "report_hash": identity,
            "report_url": f"reports/{category}/{name}",
        }
    warning = category_warning(conn, category)
    if warning:
        payload["warning"] = warning
    emit(payload)


def report_add(
    report: str,
    source: str,
    transcript_file: Path = typer.Option(...),
    report_file: Path = typer.Option(...),
    title: Optional[str] = typer.Option(None),
):
    """Attach one newly transcribed video to an existing updated report."""
    conn = db()
    members = conn.execute(
        "SELECT * FROM videos WHERE report_hash=? ORDER BY id", (report,)
    ).fetchall()
    if not members:
        raise SystemExit(f"report not found: {report}")
    transcript = transcript_file.expanduser().resolve()
    if not transcript.is_file() or transcript.stat().st_size < 100:
        raise SystemExit("--transcript-file must be an existing non-empty transcript")
    updated = report_file.expanduser().resolve()
    if not updated.is_file() or updated.suffix.lower() != ".html":
        raise SystemExit("--report-file must be an existing HTML file")
    key, url, slug = source_key(source)
    video = conn.execute("SELECT * FROM videos WHERE source_key=?", (key,)).fetchone()
    if video and video["report_hash"] == report:
        emit({"result": "already_attached", "video": view(video)})
        return
    if video and video["report_hash"]:
        raise SystemExit(f'video already belongs to report {video["report_hash"]}')
    target = Path(members[0]["report_path"])
    if not target.is_file():
        raise SystemExit(f"registered report file is missing: {target}")
    target.write_bytes(with_report_identity(updated, report))
    target.chmod(0o600)
    artifact_dir = ARTIFACTS / slug
    transcript_dir = artifact_dir / "transcription"
    transcript_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored_transcript = transcript_dir / transcript.name
    if transcript != stored_transcript:
        stored_transcript.write_bytes(transcript.read_bytes())
        stored_transcript.chmod(0o600)
    stamp = now()
    report_title = members[0]["report_title"]
    category = members[0]["category"]
    with conn:
        if video:
            conn.execute(
                "UPDATE videos SET source_url=?,source_slug=?,title=?,status='analyzed',artifact_dir=?,report_title=?,report_concept=?,report_path=?,report_hash=?,category=?,error=NULL,completed_at=?,updated_at=? WHERE id=?",
                (url, slug, title or video["title"], str(artifact_dir), report_title, members[0]["report_concept"], str(target), report, category, stamp, stamp, video["id"]),
            )
            video_id = video["id"]
        else:
            cur = conn.execute(
                "INSERT INTO videos(source_key,source_url,source_slug,title,status,artifact_dir,report_title,report_concept,report_path,report_hash,category,created_at,updated_at,completed_at) VALUES(?,?,?,?,'analyzed',?,?,?,?,?,?,?,?,?)",
                (key, url, slug, title or url, str(artifact_dir), report_title, members[0]["report_concept"], str(target), report, category, stamp, stamp, stamp),
            )
            video_id = cur.lastrowid
    payload = {
            "result": "attached",
            "video_id": video_id,
            "report_hash": report,
            "report_url": f"reports/{target.relative_to(REPORTS).as_posix()}",
        }
    warning = category_warning(conn, category)
    if warning:
        payload["warning"] = warning
    emit(payload)


def normalize_reports():
    """Give legacy reports short filenames and a visible stable identifier."""
    conn = db()
    changed = []
    rows = conn.execute(
        "SELECT DISTINCT report_hash,report_path FROM videos WHERE report_path IS NOT NULL"
    ).fetchall()
    for row in rows:
        identity = row["report_hash"]
        source = Path(row["report_path"])
        category = conn.execute(
            "SELECT category FROM videos WHERE report_hash=? LIMIT 1", (identity,)
        ).fetchone()[0]
        target_dir = REPORTS / category
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = target_dir / f"{identity}.html"
        if not source.is_file():
            raise SystemExit(f"registered report file is missing: {source}")
        target.write_bytes(with_report_identity(source, identity))
        target.chmod(0o600)
        with conn:
            conn.execute(
                "UPDATE videos SET report_path=? WHERE report_path=?",
                (str(target), str(source)),
            )
        changed.append(
            {
                "report_hash": identity,
                "previous": str(source),
                "report_url": f"reports/{target.relative_to(REPORTS).as_posix()}",
            }
        )
    emit({"result": "normalized", "reports": changed}, True)


def move_report(report: str, category: str):
    """Move a report into a real category directory and update its records."""
    conn = db()
    try:
        category = normalize_category(category)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="category") from error
    rows = conn.execute(
        "SELECT * FROM videos WHERE report_hash=? ORDER BY id", (report,)
    ).fetchall()
    if not rows:
        raise SystemExit(f"report not found: {report}")
    sources = {row["report_path"] for row in rows}
    if len(sources) != 1:
        raise SystemExit("report records disagree on file path")
    source = Path(sources.pop())
    if not source.is_file():
        raise SystemExit(f"registered report file is missing: {source}")
    directory = REPORTS / category
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / f"{report}.html"
    if source != target:
        source.replace(target)
        target.chmod(0o600)
    with conn:
        conn.execute(
            "UPDATE videos SET category=?,report_path=?,updated_at=? WHERE report_hash=?",
            (category, str(target), now(), report),
        )
    payload = {
        "result": "moved",
        "report_hash": report,
        "category": category,
        "report_url": f"reports/{target.relative_to(REPORTS).as_posix()}",
    }
    warning = category_warning(conn, category)
    if warning:
        payload["warning"] = warning
    emit(payload)


def category_tree(json_output: bool = typer.Option(False, "--json")):
    """List real report directories and their report counts."""
    conn = db()
    rows = conn.execute(
        "SELECT category,count(DISTINCT report_hash) AS reports FROM videos WHERE status='analyzed' GROUP BY category ORDER BY category"
    ).fetchall()
    payload = [dict(row) for row in rows]
    if json_output:
        emit(payload, True)
    elif not payload:
        print("No categories")
    else:
        for row in payload:
            print(f'{row["category"]}\t{row["reports"]}')


def invalidate_report(video: str, error: str = typer.Option(...)):
    conn = db()
    row = get(conn, video)
    if row["status"] != "analyzed":
        raise SystemExit(f'expected analyzed, got {row["status"]}')
    preserved = row["report_path"]
    with conn:
        conn.execute(
            "UPDATE videos SET status='failed',report_title=NULL,report_concept=NULL,report_path=NULL,error=?,completed_at=NULL,updated_at=? WHERE id=?",
            (error, now(), row["id"]),
        )
    emit(
        {
            "result": "failed",
            "video_id": row["id"],
            "error": error,
            "report_removed_from_catalog": True,
            "report_file_preserved": preserved,
        }
    )


def finish_state(video: str, status: str, error: Optional[str] = None):
    conn = db()
    row = get(conn, video)
    if row["status"] != "analyzing":
        raise SystemExit(f'expected analyzing, got {row["status"]}')
    require_transition(row["status"], status)
    stamp = now()
    error = error if status == "failed" else None
    with conn:
        conn.execute(
            "UPDATE videos SET status=?,error=?,updated_at=? WHERE id=?",
            (status, error, stamp, row["id"]),
        )
        conn.execute(
            "UPDATE runs SET status=?,error=?,finished_at=? WHERE id=(SELECT id FROM runs WHERE video_id=? AND status='analyzing' ORDER BY id DESC LIMIT 1)",
            (status, error, stamp, row["id"]),
        )
    emit({"result": status, "video_id": row["id"]})


def doctor():
    conn = db()
    checks = {
        "database": conn.execute("PRAGMA quick_check").fetchone()[0],
        "web_build": (WEB / "index.html").is_file(),
        "home_mode": oct(ROOT.stat().st_mode & 0o777),
        "database_mode": oct(DB.stat().st_mode & 0o777),
        "queue": conn.execute(
            "SELECT count(*) FROM videos WHERE status!='analyzed'"
        ).fetchone()[0],
        "reports": conn.execute(
            "SELECT count(*) FROM videos WHERE status='analyzed'"
        ).fetchone()[0],
    }
    checks["ok"] = (
        checks["database"] == "ok"
        and checks["web_build"]
        and checks["home_mode"] == "0o700"
        and checks["database_mode"] == "0o600"
    )
    emit(checks, True)
    raise SystemExit(0 if checks["ok"] else 1)


class Handler(BaseHTTPRequestHandler):
    def hdr(self, ctype):
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Referrer-Policy", "no-referrer")

    def payload(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.hdr("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def file(self, path):
        if not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.hdr(mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/health":
            self.payload({"status": "ok"})
            return
        if path == "/api/videos":
            conn = db()
            queue = [
                view(r)
                for r in conn.execute(
                    "SELECT * FROM videos WHERE status IN ('queued','analyzing','failed') ORDER BY created_at"
                )
            ]
            grouped = {}
            for raw in conn.execute(
                "SELECT * FROM videos WHERE status='analyzed' ORDER BY completed_at DESC"
            ):
                item = view(raw)
                key = item["report_url"] or f'video:{item["id"]}'
                if key not in grouped:
                    grouped[key] = {
                        **item,
                        "source_urls": [item["source_url"]],
                        "source_count": 1,
                    }
                else:
                    grouped[key]["source_urls"].append(item["source_url"])
                    grouped[key]["source_count"] += 1
            self.payload(
                {
                    "queue": queue,
                    "reports": list(grouped.values()),
                    "generated_at": now(),
                }
            )
            return
        if path.startswith("/reports/"):
            candidate = (REPORTS / path.removeprefix("/reports/")).resolve()
            if REPORTS.resolve() not in candidate.parents:
                self.send_error(403)
                return
            self.file(candidate)
            return
        candidate = (WEB / (path.lstrip("/") or "index.html")).resolve()
        if WEB.resolve() not in candidate.parents and candidate != WEB.resolve():
            self.send_error(403)
            return
        self.file(candidate if candidate.is_file() else WEB / "index.html")

    def log_message(self, fmt, *args):
        print(f"{self.log_date_time_string()} {fmt%args}", file=sys.stderr)


def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(49373),
):
    init()
    ThreadingHTTPServer((host, port), Handler).serve_forever()


app = typer.Typer(help=__doc__, no_args_is_help=True)
queue_app = typer.Typer(help="Manage the video queue.", no_args_is_help=True)
report_app = typer.Typer(help="Inspect and invalidate reports.", no_args_is_help=True)
analyze_app = typer.Typer(help="Manage explicit analysis runs.", no_args_is_help=True)
combine_app = typer.Typer(help="Prepare combined video analysis.", no_args_is_help=True)
category_app = typer.Typer(help="Inspect report directories.", no_args_is_help=True)

app.add_typer(queue_app, name="queue")
app.add_typer(report_app, name="report")
app.add_typer(analyze_app, name="analyze")
app.add_typer(combine_app, name="combine")
app.add_typer(category_app, name="category")


@app.command("init")
def init_command():
    """Initialize Vidra's private data directories and database."""
    db().close()
    typer.echo(ROOT)


queue_app.command("add")(queue_add)


@queue_app.command("list")
def queue_list(
    json_output: bool = typer.Option(False, "--json"),
    all_rows: bool = typer.Option(False, "--all"),
):
    """List queued, active, and failed videos."""
    list_rows(json_output=json_output, all_rows=all_rows)


queue_app.command("remove")(queue_remove)
queue_app.command("retry")(retry)
app.command("show")(show)


@report_app.command("list")
def report_list(
    json_output: bool = typer.Option(False, "--json"),
    category: Optional[str] = typer.Option(None),
):
    """List completed reports."""
    normalized = normalize_category(category) if category else None
    list_rows(json_output=json_output, report=True, category=normalized)


report_app.command("invalidate")(invalidate_report)
report_app.command("add")(report_add)
report_app.command("normalize")(normalize_reports)
report_app.command("move")(move_report)
category_app.command("tree")(category_tree)
analyze_app.command("begin")(begin)
analyze_app.command("complete")(complete)


@analyze_app.command("fail")
def analyze_fail(video: str, error: str = typer.Option(...)):
    """Record a failed analysis while retaining the video in the queue."""
    finish_state(video, "failed", error)


@analyze_app.command("cancel")
def analyze_cancel(video: str):
    """Return an active analysis to the queue."""
    finish_state(video, "queued")


@combine_app.command("plan")
def combine_plan(
    sources: List[str] = typer.Argument(...),
    classification: str = typer.Option(...),
    title: Optional[str] = typer.Option(None),
    variant: Optional[List[str]] = typer.Option(None),
):
    """Create an unregistered manifest for a multi-video report."""
    allowed_classifications = {"theory", "practice", "mixed"}
    if classification not in allowed_classifications:
        raise typer.BadParameter(
            "must be theory, practice, or mixed", param_hint="--classification"
        )

    normalized = []
    seen = set()
    for value in sources:
        key, url, slug = source_key(value)
        if key not in seen:
            seen.add(key)
            normalized.append(
                {"source_key": key, "source_url": url, "source_slug": slug}
            )
    if len(normalized) < 2:
        raise typer.BadParameter("requires at least two distinct sources")

    defaults = (
        ["cornell", "concept-atlas", "layered-synthesis"]
        if classification == "theory"
        else ["playbook"]
    )
    variants = tuple(dict.fromkeys(variant or defaults))
    allowed_variants = {"cornell", "concept-atlas", "layered-synthesis", "playbook"}
    unknown = sorted(set(variants) - allowed_variants)
    if unknown:
        raise typer.BadParameter(
            "unknown values: " + ", ".join(unknown), param_hint="--variant"
        )

    payload = {
        "schema_version": 1,
        "kind": "combined-video-analysis",
        "title": title or "Combined video analysis",
        "classification": classification,
        "sources": normalized,
        "variants": variants,
        "sqlite_registration": False,
        "created_at": now(),
    }
    identity = {
        "classification": classification,
        "sources": [item["source_key"] for item in normalized],
        "variants": variants,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()[:16]
    directory = ARTIFACTS / "combined" / digest
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = directory / "manifest.json"
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest.chmod(0o600)
    emit(
        {
            "result": "combined_plan_created",
            "manifest": str(manifest),
            "artifact_dir": str(directory),
            **payload,
        },
        True,
    )


app.command("doctor")(doctor)
app.command("serve")(serve)


def main():
    """Run the Vidra command-line interface."""
    app()


if __name__ == "__main__":
    main()
