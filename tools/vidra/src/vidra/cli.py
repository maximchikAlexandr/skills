#!/usr/bin/env python3
"""Vidra queue, analysis lifecycle, report registry, and catalog server."""

import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import typer

from .domain import (
    CATEGORY_LIMIT,
    PROJECT_CATEGORY_LIMIT,
    normalize_category,
    normalize_github_repository,
    normalize_rating,
    normalize_source,
    project_report_hash,
    report_hash,
    report_validation_errors,
    require_transition,
)

ROOT = Path(os.environ.get("VIDRA_HOME", Path.home() / ".vidra")).expanduser()
DB = ROOT / "vidra.sqlite3"
ARTIFACTS = ROOT / "artifacts"
REPORTS = ROOT / "reports"
PROJECT_REPORTS = ROOT / "projects"
WEB = ROOT / "web"
DIRS = (
    ARTIFACTS,
    REPORTS,
    PROJECT_REPORTS,
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
        """CREATE TABLE IF NOT EXISTS videos(id INTEGER PRIMARY KEY,source_key TEXT NOT NULL UNIQUE,source_url TEXT NOT NULL,source_slug TEXT NOT NULL,title TEXT NOT NULL,request TEXT NOT NULL DEFAULT '',status TEXT NOT NULL CHECK(status IN ('queued','analyzing','analyzed','failed')),artifact_dir TEXT,report_title TEXT,report_concept TEXT,report_path TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,started_at TEXT,completed_at TEXT);CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),status TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,error TEXT);CREATE INDEX IF NOT EXISTS videos_status_idx ON videos(status,updated_at);CREATE TABLE IF NOT EXISTS project_registry(id INTEGER PRIMARY KEY,repository_key TEXT NOT NULL UNIQUE COLLATE NOCASE,repository_url TEXT,display_name TEXT NOT NULL,first_seen_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS project_queue(id INTEGER PRIMARY KEY,repository_key TEXT NOT NULL UNIQUE COLLATE NOCASE,repository_url TEXT NOT NULL,title TEXT NOT NULL,request TEXT NOT NULL DEFAULT '',status TEXT NOT NULL CHECK(status IN ('queued','analyzing','analyzed','failed')),error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,started_at TEXT,completed_at TEXT);CREATE INDEX IF NOT EXISTS project_queue_status_idx ON project_queue(status,updated_at);CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,repository_key TEXT NOT NULL UNIQUE COLLATE NOCASE,repository_url TEXT NOT NULL,owner TEXT NOT NULL,name TEXT NOT NULL,title TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '',stars INTEGER,revision TEXT NOT NULL,report_hash TEXT NOT NULL UNIQUE,report_path TEXT NOT NULL,preview_url TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);CREATE INDEX IF NOT EXISTS projects_updated_idx ON projects(updated_at DESC);"""
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(videos)")}
    if "report_hash" not in columns:
        conn.execute("ALTER TABLE videos ADD COLUMN report_hash TEXT")
    if "category" not in columns:
        conn.execute(
            "ALTER TABLE videos ADD COLUMN category TEXT NOT NULL DEFAULT 'uncategorized'"
        )
    if "target_report_hash" not in columns:
        conn.execute("ALTER TABLE videos ADD COLUMN target_report_hash TEXT")
    if "rating" not in columns:
        conn.execute(
            "ALTER TABLE videos ADD COLUMN rating INTEGER CHECK(rating BETWEEN 1 AND 5)"
        )
    project_columns = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
    if "category" not in project_columns:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN category TEXT NOT NULL DEFAULT 'uncategorized'"
        )
    if "rating" not in project_columns:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN rating INTEGER CHECK(rating BETWEEN 1 AND 5)"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS videos_report_hash_idx ON videos(report_hash)"
    )
    for row in conn.execute(
        "SELECT DISTINCT report_path FROM videos WHERE report_path IS NOT NULL AND report_hash IS NULL"
    ):
        legacy_hash = hashlib.sha256(
            Path(row["report_path"]).name.encode()
        ).hexdigest()[:12]
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


def _without_report_identity(html: str) -> str:
    """Remove the injected control without confusing its nested spans."""
    marker = 'data-vidra-report-id="true"'
    marker_at = html.find(marker)
    if marker_at < 0:
        return html
    start = html.rfind("<span", 0, marker_at)
    if start < 0:
        start = html.rfind("<aside", 0, marker_at)
        end = html.find("</aside>", marker_at)
        return (
            html[:start] + html[end + len("</aside>") :]
            if start >= 0 and end >= 0
            else html
        )
    depth = 0
    for tag in re.finditer(r"</?span\b[^>]*>", html[start:], flags=re.IGNORECASE):
        depth += -1 if tag.group().startswith("</") else 1
        if depth == 0:
            end = start + tag.end()
            html = html[:start] + html[end:]
            break
    return re.sub(
        r'<span\s+style="display:inline-flex;align-items:center;overflow:hidden[^>]*>'
        r".*?data-copy-report-id.*?</span>",
        "",
        html,
        flags=re.DOTALL,
    )


def library_href(report_path: Path) -> str:
    """Return a relative link from a categorized report to the catalog root."""
    relative = report_path.resolve().relative_to(REPORTS.resolve())
    return "../" * len(relative.parts)


def with_report_identity(
    source: Path, identity: str, catalog_href: str = "../"
) -> bytes:
    """Place a copyable report id after a repaired catalog link."""
    html = source.read_text(encoding="utf-8")
    html = _without_report_identity(html)
    html = re.sub(
        r'<script\s+data-vidra-report-copy="true">.*?</script>',
        "",
        html,
        flags=re.DOTALL,
    )
    control = (
        '<span data-vidra-report-id="true" style="display:inline-flex;align-items:center;'
        'gap:7px;min-width:0;margin-left:10px;font:600 12px/1.2 system-ui,sans-serif">'
        '<span style="white-space:nowrap;opacity:.78">ID отчёта</span>'
        '<span style="display:inline-flex;align-items:center;overflow:hidden;border:1px solid '
        'currentColor;border-radius:7px;background:#fff;color:#315b55">'
        f'<code style="padding:5px 8px;user-select:all">{identity}</code>'
        '<button type="button" data-copy-report-id aria-label="Скопировать ID отчёта" '
        'title="Скопировать ID отчёта" style="display:grid;place-items:center;width:30px;height:28px;'
        'padding:0;border:0;border-left:1px solid #c7d7d3;background:#edf6f3;color:#315b55;cursor:pointer">'
        '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M8 8h11v11H8zM5 16H4V5h11v1" '
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>'
        "</button></span></span>"
    )
    library_link = re.search(
        r"(<a\b[^>]*>[^<]*(?:Все видео|All videos)[^<]*</a>)",
        html,
        flags=re.IGNORECASE,
    )
    if library_link:
        anchor = library_link.group(1)
        if re.search(r"\bhref\s*=", anchor, flags=re.IGNORECASE):
            anchor = re.sub(
                r"\bhref\s*=\s*(['\"]).*?\1",
                f'href="{catalog_href}"',
                anchor,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            anchor = anchor.replace("<a", f'<a href="{catalog_href}"', 1)
        html = html[: library_link.start()] + anchor + html[library_link.end() :]
        library_link = re.search(
            r"(<a\b[^>]*>[^<]*(?:Все видео|All videos)[^<]*</a>)",
            html,
            flags=re.IGNORECASE,
        )
        assert library_link is not None
        position = library_link.end()
        html = html[:position] + control + html[position:]
    else:
        body = html.lower().find("<body")
        if body < 0:
            raise SystemExit("report HTML must contain <body>")
        position = html.find(">", body) + 1
        html = html[:position] + control + html[position:]

    copy_script = (
        '<script data-vidra-report-copy="true">(()=>{const b=document.querySelector('
        "'[data-copy-report-id]'),c=document.querySelector('[data-vidra-report-id] code');"
        "if(!b||!c)return;b.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(c.textContent);"
        "const t=b.title;b.title='Скопировано';b.setAttribute('aria-label','Скопировано');setTimeout(()=>{b.title=t;"
        "b.setAttribute('aria-label','Скопировать ID отчёта')},1200)}catch{const r=document.createRange();"
        "r.selectNodeContents(c);const s=getSelection();s.removeAllRanges();s.addRange(r)}})})();</script>"
    )
    body_close = html.lower().rfind("</body>")
    html = (
        html[:body_close] + copy_script + html[body_close:]
        if body_close >= 0
        else html + copy_script
    )
    html = html.replace(
        "default-src 'none'; style-src",
        "default-src 'none'; script-src 'unsafe-inline'; style-src",
    )
    return html.encode("utf-8")


def project_library_href(report_path: Path) -> str:
    """Return a relative link from a categorized project report to the catalog."""
    relative = report_path.resolve().relative_to(PROJECT_REPORTS.resolve())
    return "../" * len(relative.parts) + "#projects"


def with_project_navigation(source: Path, catalog_href: str = "../#projects") -> bytes:
    """Inject an idempotent link from a project report to the project catalog."""
    html = source.read_text(encoding="utf-8")
    html = re.sub(
        r'<a\b[^>]*data-vidra-projects-link="true"[^>]*>.*?</a>',
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    link = (
        f'<a data-vidra-projects-link="true" href="{catalog_href}" '
        'style="display:inline-flex;align-items:center;gap:7px;margin:16px;'
        "padding:8px 12px;border:1px solid currentColor;border-radius:7px;"
        'font:600 13px/1.2 system-ui,sans-serif;color:#315b55;text-decoration:none">'
        '<span aria-hidden="true">←</span> Все проекты</a>'
    )
    body = html.lower().find("<body")
    if body < 0:
        raise SystemExit("project report HTML must contain <body>")
    position = html.find(">", body) + 1
    return (html[:position] + link + html[position:]).encode("utf-8")


def project_view(row):
    item = dict(row)
    report_path = Path(item.pop("report_path"))
    item["report_url"] = (
        f"projects/{report_path.relative_to(PROJECT_REPORTS).as_posix()}"
    )
    return item


def project_queue_view(row):
    item = dict(row)
    item["source_type"] = "github_project"
    item["source_url"] = item["repository_url"]
    return item


def project_queue_get(conn, repository):
    repo = normalize_github_repository(repository)
    row = conn.execute(
        "SELECT * FROM project_queue WHERE repository_key=? COLLATE NOCASE", (repo.key,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"queued project not found: {repo.key}")
    return row


def project_queue_add(
    repository: str,
    title: Optional[str] = typer.Option(None),
    request: str = typer.Option(""),
):
    """Add a GitHub repository to the project-analysis queue."""
    conn = db()
    repo = normalize_github_repository(repository)
    stamp = now()
    report = conn.execute(
        "SELECT * FROM projects WHERE repository_key=? COLLATE NOCASE", (repo.key,)
    ).fetchone()
    if report:
        emit({"result": "already_analyzed", "project": project_view(report)})
        return
    old = conn.execute(
        "SELECT * FROM project_queue WHERE repository_key=? COLLATE NOCASE", (repo.key,)
    ).fetchone()
    if old and old["status"] in {"queued", "analyzing"}:
        emit({"result": "already_" + old["status"], "project": project_queue_view(old)})
        return
    display = title or repo.key
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO project_registry(repository_key,repository_url,display_name,first_seen_at) VALUES(?,?,?,?)",
            (repo.key, repo.url, display, stamp),
        )
        if old:
            conn.execute(
                "UPDATE project_queue SET title=?,request=?,status='queued',error=NULL,started_at=NULL,completed_at=NULL,updated_at=? WHERE id=?",
                (display, request, stamp, old["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO project_queue(repository_key,repository_url,title,request,status,created_at,updated_at) VALUES(?,?,?,?,'queued',?,?)",
                (repo.key, repo.url, display, request, stamp, stamp),
            )
    emit(
        {
            "result": "requeued" if old else "queued",
            "project": project_queue_view(project_queue_get(conn, repo.key)),
        }
    )


def project_queue_list(json_output: bool = typer.Option(False, "--json")):
    """List queued, active, and failed GitHub project analyses."""
    rows = [
        project_queue_view(row)
        for row in db().execute(
            "SELECT * FROM project_queue WHERE status IN ('queued','analyzing','failed') ORDER BY created_at"
        )
    ]
    if json_output:
        emit(rows, True)
    elif not rows:
        print("Project queue is empty")
    else:
        for row in rows:
            print(f"{row['status']}\t{row['repository_key']}\t{row['title']}")


def project_queue_begin(repository: str, user_approved: bool = typer.Option(False)):
    """Mark one explicitly requested project analysis as active."""
    if not user_approved:
        raise SystemExit(
            "requires a separate explicit user request and --user-approved"
        )
    conn = db()
    row = project_queue_get(conn, repository)
    if row["status"] != "queued":
        raise SystemExit(f"expected queued, got {row['status']}")
    stamp = now()
    with conn:
        conn.execute(
            "UPDATE project_queue SET status='analyzing',started_at=?,updated_at=?,error=NULL WHERE id=?",
            (stamp, stamp, row["id"]),
        )
    emit(
        {
            "result": "analyzing",
            "project": project_queue_view(project_queue_get(conn, repository)),
        }
    )


def project_queue_fail(repository: str, error: str = typer.Option(...)):
    """Record a failed project analysis while retaining it in the queue."""
    conn = db()
    row = project_queue_get(conn, repository)
    stamp = now()
    with conn:
        conn.execute(
            "UPDATE project_queue SET status='failed',error=?,updated_at=? WHERE id=?",
            (error, stamp, row["id"]),
        )
    emit(
        {
            "result": "failed",
            "project": project_queue_view(project_queue_get(conn, repository)),
        }
    )


def project_category_warning(conn, category):
    count = conn.execute(
        "SELECT count(*) FROM projects WHERE category=?", (category,)
    ).fetchone()[0]
    if count <= PROJECT_CATEGORY_LIMIT:
        return None
    return {
        "code": "project_category_reindex_required",
        "category": category,
        "project_count": count,
        "limit": PROJECT_CATEGORY_LIMIT,
        "instructions": "skills/education/discover-github-projects/references/category-reindexing.md",
    }


def project_register(
    repository: str,
    report_file: Path = typer.Option(...),
    title: str = typer.Option(...),
    revision: str = typer.Option(...),
    summary: str = typer.Option(""),
    stars: Optional[int] = typer.Option(None),
    preview_file: Optional[Path] = typer.Option(None),
    category: str = typer.Option("uncategorized"),
    replace: bool = typer.Option(False),
):
    """Register one completed GitHub project report in the shared catalog."""
    try:
        repo = normalize_github_repository(repository)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="repository") from error
    source = report_file.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".html":
        raise SystemExit("--report-file must be an existing HTML file")
    try:
        category = normalize_category(category)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--category") from error
    conn = db()
    existing = conn.execute(
        "SELECT * FROM projects WHERE repository_key=? COLLATE NOCASE", (repo.key,)
    ).fetchone()
    if existing and not replace:
        emit({"result": "already_registered", "project": project_view(existing)})
        return
    identity = project_report_hash(repo.key, revision)
    target_dir = PROJECT_REPORTS / category
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = target_dir / f"{identity}.html"
    target.write_bytes(with_project_navigation(source, project_library_href(target)))
    target.chmod(0o600)
    stamp = now()
    preview = f"https://opengraph.githubassets.com/{identity}/{repo.owner}/{repo.name}"
    if preview_file is not None:
        preview_source = preview_file.expanduser().resolve()
        if not preview_source.is_file():
            raise SystemExit("--preview-file must be an existing image")
        suffix = preview_source.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise SystemExit("--preview-file must be PNG, JPEG, or WebP")
        preview_target = target_dir / f"{identity}{suffix}"
        preview_target.write_bytes(preview_source.read_bytes())
        preview_target.chmod(0o600)
        preview = f"projects/{preview_target.relative_to(PROJECT_REPORTS).as_posix()}"
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO project_registry(repository_key,repository_url,display_name,first_seen_at) VALUES(?,?,?,?)",
            (repo.key, repo.url, title, stamp),
        )
        conn.execute(
            """INSERT INTO projects(repository_key,repository_url,owner,name,title,summary,stars,revision,report_hash,report_path,preview_url,category,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(repository_key) DO UPDATE SET repository_url=excluded.repository_url,owner=excluded.owner,name=excluded.name,title=excluded.title,summary=excluded.summary,stars=excluded.stars,revision=excluded.revision,report_hash=excluded.report_hash,report_path=excluded.report_path,preview_url=excluded.preview_url,category=excluded.category,updated_at=excluded.updated_at""",
            (
                repo.key,
                repo.url,
                repo.owner,
                repo.name,
                title,
                summary,
                stars,
                revision,
                identity,
                str(target),
                preview,
                category,
                stamp,
                stamp,
            ),
        )
        conn.execute(
            "UPDATE project_queue SET status='analyzed',error=NULL,completed_at=?,updated_at=? WHERE repository_key=? COLLATE NOCASE",
            (stamp, stamp, repo.key),
        )
    payload = {
        "result": "registered" if not existing else "replaced",
        "project": project_view(
            conn.execute(
                "SELECT * FROM projects WHERE repository_key=?", (repo.key,)
            ).fetchone()
        ),
    }
    warning = project_category_warning(conn, category)
    if warning:
        payload["warning"] = warning
    emit(payload, True)


def project_list(
    json_output: bool = typer.Option(False, "--json"),
    category: Optional[str] = typer.Option(None),
):
    """List registered GitHub project reports."""
    normalized = normalize_category(category) if category else None
    rows = [
        project_view(row)
        for row in db().execute(
            "SELECT * FROM projects WHERE (? IS NULL OR category=?) ORDER BY updated_at DESC",
            (normalized, normalized),
        )
    ]
    if json_output:
        emit(rows, True)
    elif not rows:
        print("No project reports")
    else:
        for row in rows:
            print(
                f"{row['report_hash']}\t{row['category']}\t{row['repository_key']}\t{row['title']}"
            )


def project_move(report: str, category: str):
    """Move a project report and its preview into a real category directory."""
    conn = db()
    try:
        category = normalize_category(category)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="category") from error
    row = conn.execute(
        "SELECT * FROM projects WHERE report_hash=?", (report,)
    ).fetchone()
    if row is None:
        raise SystemExit(f"project report not found: {report}")
    source = Path(row["report_path"])
    if not source.is_file():
        raise SystemExit(f"registered project report file is missing: {source}")
    directory = PROJECT_REPORTS / category
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / f"{report}.html"
    if source != target:
        source.replace(target)
    target.write_bytes(with_project_navigation(target, project_library_href(target)))
    target.chmod(0o600)
    preview_url = row["preview_url"]
    if preview_url.startswith("projects/"):
        preview_source = PROJECT_REPORTS / preview_url.removeprefix("projects/")
        if preview_source.is_file():
            preview_target = directory / preview_source.name
            if preview_source != preview_target:
                preview_source.replace(preview_target)
            preview_target.chmod(0o600)
            preview_url = (
                f"projects/{preview_target.relative_to(PROJECT_REPORTS).as_posix()}"
            )
    with conn:
        conn.execute(
            "UPDATE projects SET category=?,report_path=?,preview_url=?,updated_at=? WHERE report_hash=?",
            (category, str(target), preview_url, now(), report),
        )
    payload = {
        "result": "moved",
        "report_hash": report,
        "category": category,
        "report_url": f"projects/{target.relative_to(PROJECT_REPORTS).as_posix()}",
    }
    warning = project_category_warning(conn, category)
    if warning:
        payload["warning"] = warning
    emit(payload, True)


def project_category_tree(json_output: bool = typer.Option(False, "--json")):
    """List real project-report directories and their project counts."""
    rows = (
        db()
        .execute(
            "SELECT category,count(*) AS projects FROM projects GROUP BY category ORDER BY category"
        )
        .fetchall()
    )
    payload = [dict(row) for row in rows]
    if json_output:
        emit(payload, True)
    elif not payload:
        print("No project categories")
    else:
        for row in payload:
            print(f"{row['category']}\t{row['projects']}")


def project_seen(repository: str):
    """Check the shared Vidra registry before researching a repository."""
    try:
        repo = normalize_github_repository(repository)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="repository") from error
    row = (
        db()
        .execute(
            "SELECT * FROM project_registry WHERE repository_key=? COLLATE NOCASE",
            (repo.key,),
        )
        .fetchone()
    )
    emit({"seen": row is not None, "project": dict(row) if row else None}, True)
    if row is None:
        raise typer.Exit(1)


def project_remember(repository: str, name: Optional[str] = typer.Option(None)):
    """Record a researched or screened GitHub repository without publishing a report."""
    try:
        repo = normalize_github_repository(repository)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="repository") from error
    stamp = now()
    with db() as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO project_registry(repository_key,repository_url,display_name,first_seen_at) VALUES(?,?,?,?)",
            (repo.key, repo.url, name or repo.name, stamp),
        )
    emit(
        {
            "result": "remembered" if cursor.rowcount else "already_seen",
            "repository_key": repo.key,
        }
    )


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
        else ("1=1" if all_rows else "status IN ('queued','analyzing','failed')")
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
                f"{r['id']}\t{r['status']}\t{r['report_title'] or r['title']}\t{r['source_url']}"
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
        raise SystemExit(f"expected failed, got {row['status']}")
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
        raise SystemExit(f"expected queued, got {row['status']}")
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
        f"{row['id']}:{row['status']}" for row in rows if row["status"] != "analyzing"
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
    target.write_bytes(with_report_identity(source, identity, library_href(target)))
    target.chmod(0o600)
    with conn:
        for row in rows:
            conn.execute(
                "UPDATE videos SET status='analyzed',report_title=?,report_concept=?,report_path=?,report_hash=?,category=?,completed_at=?,updated_at=?,error=NULL WHERE id=?",
                (
                    title,
                    concept,
                    str(target),
                    identity,
                    category,
                    stamp,
                    stamp,
                    row["id"],
                ),
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
        stamp = now()
        with conn:
            conn.execute(
                "UPDATE runs SET status='analyzed',finished_at=?,error=NULL WHERE id=(SELECT id FROM runs WHERE video_id=? AND status='analyzing' ORDER BY id DESC LIMIT 1)",
                (stamp, video["id"]),
            )
        emit({"result": "already_attached", "video": view(video)})
        return
    if video and video["report_hash"]:
        raise SystemExit(f"video already belongs to report {video['report_hash']}")
    target = Path(members[0]["report_path"])
    if not target.is_file():
        raise SystemExit(f"registered report file is missing: {target}")
    artifact_dir = ARTIFACTS / slug
    transcript_dir = artifact_dir / "transcription"
    transcript_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored_transcript = transcript_dir / transcript.name
    if transcript != stored_transcript:
        stored_transcript.write_bytes(transcript.read_bytes())
        stored_transcript.chmod(0o600)
    rendered = with_report_identity(updated, report, library_href(target))
    covered_ids = tuple(dict.fromkeys([row["source_slug"] for row in members] + [slug]))
    errors = report_validation_errors(rendered.decode("utf-8"), covered_ids, report)
    if errors:
        raise SystemExit("invalid updated report: " + ", ".join(errors))
    stamp = now()
    backup = artifact_dir / f"report-before-addition-{stamp.replace(':', '-')}.html"
    backup.write_bytes(target.read_bytes())
    backup.chmod(0o600)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_bytes(rendered)
    temporary.chmod(0o600)
    os.replace(temporary, target)
    report_title = members[0]["report_title"]
    category = members[0]["category"]
    with conn:
        if video:
            conn.execute(
                "UPDATE videos SET source_url=?,source_slug=?,title=?,status='analyzed',artifact_dir=?,report_title=?,report_concept=?,report_path=?,report_hash=?,target_report_hash=?,category=?,error=NULL,completed_at=?,updated_at=? WHERE id=?",
                (
                    url,
                    slug,
                    title or video["title"],
                    str(artifact_dir),
                    report_title,
                    members[0]["report_concept"],
                    str(target),
                    report,
                    report,
                    category,
                    stamp,
                    stamp,
                    video["id"],
                ),
            )
            video_id = video["id"]
        else:
            cur = conn.execute(
                "INSERT INTO videos(source_key,source_url,source_slug,title,status,artifact_dir,report_title,report_concept,report_path,report_hash,target_report_hash,category,created_at,updated_at,completed_at) VALUES(?,?,?,?,'analyzed',?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    url,
                    slug,
                    title or url,
                    str(artifact_dir),
                    report_title,
                    members[0]["report_concept"],
                    str(target),
                    report,
                    report,
                    category,
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            video_id = cur.lastrowid
        conn.execute(
            "UPDATE runs SET status='analyzed',finished_at=?,error=NULL WHERE id=(SELECT id FROM runs WHERE video_id=? AND status='analyzing' ORDER BY id DESC LIMIT 1)",
            (stamp, video_id),
        )
    payload = {
        "result": "attached",
        "video_id": video_id,
        "report_hash": report,
        "report_url": f"reports/{target.relative_to(REPORTS).as_posix()}",
        "backup": str(backup),
    }
    warning = category_warning(conn, category)
    if warning:
        payload["warning"] = warning
    emit(payload)


def report_add_video(
    report: str,
    source: str,
    title: Optional[str] = typer.Option(None),
):
    """Prepare one explicit, resumable video addition to an existing report."""
    conn = db()
    members = conn.execute(
        "SELECT * FROM videos WHERE report_hash=? ORDER BY id", (report,)
    ).fetchall()
    if not members:
        raise SystemExit(f"report not found: {report}")
    key, url, slug = source_key(source)
    existing = conn.execute(
        "SELECT * FROM videos WHERE source_key=?", (key,)
    ).fetchone()
    if existing and existing["report_hash"] == report:
        emit({"result": "already_attached", "video": view(existing)})
        return
    if existing and existing["report_hash"]:
        raise SystemExit(f"video already belongs to report {existing['report_hash']}")
    if (
        existing
        and existing["status"] == "analyzing"
        and existing["target_report_hash"] == report
    ):
        emit({"result": "already_prepared", "video": view(existing)})
        return
    artifact_dir = ARTIFACTS / slug
    transcript_dir = artifact_dir / "transcription"
    transcript_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = now()
    with conn:
        if existing:
            conn.execute(
                "UPDATE videos SET source_url=?,source_slug=?,title=?,request=?,status='analyzing',artifact_dir=?,target_report_hash=?,report_title=NULL,report_concept=NULL,report_path=NULL,report_hash=NULL,category='uncategorized',error=NULL,started_at=?,completed_at=NULL,updated_at=? WHERE id=?",
                (
                    url,
                    slug,
                    title or existing["title"],
                    f"Add to report {report}",
                    str(artifact_dir),
                    report,
                    stamp,
                    stamp,
                    existing["id"],
                ),
            )
            video_id = existing["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO videos(source_key,source_url,source_slug,title,request,status,artifact_dir,target_report_hash,created_at,updated_at,started_at) VALUES(?,?,?,?,?,'analyzing',?,?,?,?,?)",
                (
                    key,
                    url,
                    slug,
                    title or url,
                    f"Add to report {report}",
                    str(artifact_dir),
                    report,
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            video_id = cursor.lastrowid
        run = conn.execute(
            "INSERT INTO runs(video_id,status,started_at) VALUES(?,'analyzing',?)",
            (video_id, stamp),
        )
    manifest = artifact_dir / "addition.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "report-video-addition",
                "report_hash": report,
                "report_path": members[0]["report_path"],
                "video_id": video_id,
                "source_url": url,
                "source_slug": slug,
                "transcript_dir": str(transcript_dir),
                "authoring_contract": "skills/education/video-analyzer/references/report-authoring.md#extending-an-existing-report",
                "created_at": stamp,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest.chmod(0o600)
    emit(
        {
            "result": "addition_prepared",
            "video_id": video_id,
            "run_id": run.lastrowid,
            "report_hash": report,
            "source_url": url,
            "artifact_dir": str(artifact_dir),
            "manifest": str(manifest),
            "next": "obtain a verified transcript, integrate the source into the report narrative, then run `vidra report add`",
        }
    )


def report_additions(
    report: str,
    json_output: bool = typer.Option(False, "--json"),
):
    """List videos prepared for or added to a report."""
    rows = [
        view(row)
        for row in db().execute(
            "SELECT * FROM videos WHERE target_report_hash=? ORDER BY created_at",
            (report,),
        )
    ]
    if json_output:
        emit(rows, True)
    elif not rows:
        print("No additions")
    else:
        for row in rows:
            print(f"{row['id']}\t{row['status']}\t{row['title']}\t{row['source_url']}")


def validate_report(report: str):
    """Validate report identity, sources, players, and timestamp pairs."""
    conn = db()
    rows = conn.execute(
        "SELECT * FROM videos WHERE report_hash=? ORDER BY id", (report,)
    ).fetchall()
    if not rows:
        raise SystemExit(f"report not found: {report}")
    paths = {row["report_path"] for row in rows}
    if len(paths) != 1:
        raise SystemExit("report records disagree on file path")
    path = Path(paths.pop())
    errors = report_validation_errors(
        path.read_text(encoding="utf-8"),
        tuple(row["source_slug"] for row in rows),
        report,
    )
    emit(
        {
            "result": "valid" if not errors else "invalid",
            "report_hash": report,
            "sources": len(rows),
            "errors": list(errors),
        },
        True,
    )
    if errors:
        raise typer.Exit(1)


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
        target.write_bytes(with_report_identity(source, identity, library_href(target)))
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
    target.write_bytes(with_report_identity(target, report, library_href(target)))
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
            print(f"{row['category']}\t{row['reports']}")


def invalidate_report(video: str, error: str = typer.Option(...)):
    conn = db()
    row = get(conn, video)
    if row["status"] != "analyzed":
        raise SystemExit(f"expected analyzed, got {row['status']}")
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
        raise SystemExit(f"expected analyzing, got {row['status']}")
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
        "project_queue": conn.execute(
            "SELECT count(*) FROM project_queue WHERE status!='analyzed'"
        ).fetchone()[0],
        "reports": conn.execute(
            "SELECT count(*) FROM videos WHERE status='analyzed'"
        ).fetchone()[0],
        "projects": conn.execute("SELECT count(*) FROM projects").fetchone()[0],
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

    def json_error(self, status, message):
        body = json.dumps({"error": message}, ensure_ascii=False).encode()
        self.send_response(status)
        self.hdr("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        if path != "/api/ratings":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 4096:
                raise ValueError("invalid request size")
            request = json.loads(self.rfile.read(length))
            source_type = request.get("source_type")
            identity = str(request.get("report_hash", "")).strip()
            rating = normalize_rating(request.get("rating"))
            if not re.fullmatch(r"[0-9a-f]{12}", identity):
                raise ValueError("invalid report hash")
            conn = db()
            if source_type == "video":
                cursor = conn.execute(
                    "UPDATE videos SET rating=?,updated_at=? WHERE report_hash=? AND status='analyzed'",
                    (rating, now(), identity),
                )
            elif source_type == "github_project":
                cursor = conn.execute(
                    "UPDATE projects SET rating=?,updated_at=? WHERE report_hash=?",
                    (rating, now(), identity),
                )
            else:
                raise ValueError("invalid source type")
            if cursor.rowcount == 0:
                conn.rollback()
                self.json_error(404, "report not found")
                return
            conn.commit()
            self.payload(
                {"result": "rated", "source_type": source_type, "report_hash": identity, "rating": rating}
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.json_error(400, str(exc))

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
        if path in {"/api/videos", "/api/catalog"}:
            conn = db()
            queue = [
                {**view(r), "source_type": "video"}
                for r in conn.execute(
                    "SELECT * FROM videos WHERE status IN ('queued','analyzing','failed') ORDER BY created_at"
                )
            ]
            queue.extend(
                project_queue_view(r)
                for r in conn.execute(
                    "SELECT * FROM project_queue WHERE status IN ('queued','analyzing','failed') ORDER BY created_at"
                )
            )
            queue.sort(key=lambda item: item["created_at"])
            grouped = {}
            for raw in conn.execute(
                "SELECT * FROM videos WHERE status='analyzed' ORDER BY completed_at DESC"
            ):
                item = view(raw)
                key = item["report_url"] or f"video:{item['id']}"
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
                    "projects": [
                        project_view(row)
                        for row in conn.execute(
                            "SELECT * FROM projects ORDER BY updated_at DESC"
                        )
                    ],
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
        if path.startswith("/projects/"):
            candidate = (PROJECT_REPORTS / path.removeprefix("/projects/")).resolve()
            if PROJECT_REPORTS.resolve() not in candidate.parents:
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
        print(f"{self.log_date_time_string()} {fmt % args}", file=sys.stderr)


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
project_app = typer.Typer(help="Manage GitHub project reports.", no_args_is_help=True)

app.add_typer(queue_app, name="queue")
app.add_typer(report_app, name="report")
app.add_typer(analyze_app, name="analyze")
app.add_typer(combine_app, name="combine")
app.add_typer(category_app, name="category")
app.add_typer(project_app, name="project")


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
report_app.command("add-video")(report_add_video)
report_app.command("additions")(report_additions)
report_app.command("validate")(validate_report)
report_app.command("normalize")(normalize_reports)
report_app.command("move")(move_report)
category_app.command("tree")(category_tree)
project_app.command("register")(project_register)
project_app.command("list")(project_list)
project_app.command("seen")(project_seen)
project_app.command("remember")(project_remember)
project_app.command("move")(project_move)
project_app.command("category-tree")(project_category_tree)
project_app.command("queue-add")(project_queue_add)
project_app.command("queue-list")(project_queue_list)
project_app.command("queue-begin")(project_queue_begin)
project_app.command("queue-fail")(project_queue_fail)
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
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[
        :16
    ]
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
