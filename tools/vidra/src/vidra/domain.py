"""Pure domain functions for Vidra.

I/O belongs in ``storage`` and ``cli``. Keeping normalization and transition
rules here makes the behavior deterministic and easy to test.
"""

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

VIDEO_STATES = frozenset({"queued", "analyzing", "analyzed", "failed"})
CATEGORY_LIMIT = 10
PROJECT_CATEGORY_LIMIT = 15
RATING_VALUES = frozenset(range(1, 6))


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    slug: str


@dataclass(frozen=True)
class GitHubRepository:
    key: str
    url: str
    owner: str
    name: str


def normalize_github_repository(value: str) -> GitHubRepository:
    """Return the canonical identity of a GitHub repository URL or owner/name."""
    raw = value.strip()
    parsed = urlparse(raw if "://" in raw else f"https://github.com/{raw}")
    if parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("only github.com repositories are supported")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("repository must be a GitHub owner/name URL")
    parts = [parts[0], parts[1].removesuffix(".git")]
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise ValueError("repository must be a GitHub owner/name URL")
    owner, name = parts
    key = f"{owner.lower()}/{name.lower()}"
    return GitHubRepository(
        key=key,
        url=f"https://github.com/{owner}/{name}",
        owner=owner,
        name=name,
    )


def project_report_hash(repository_key: str, revision: str) -> str:
    """Return a stable short filename identity for one repository revision."""
    return sha256(f"{repository_key}\0{revision}".encode()).hexdigest()[:12]


def normalize_source(value: str) -> Source:
    """Return a stable identity for YouTube URLs and local/other sources."""
    parsed = urlparse(value)
    host = parsed.netloc.lower().removeprefix("www.")
    video_id = ""
    if host in {"youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/embed/", "/shorts/")):
            video_id = parsed.path.rstrip("/").split("/")[-1]
    elif host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    if video_id:
        return Source(
            key=f"youtube:{video_id}",
            url=f"https://www.youtube.com/watch?v={video_id}",
            slug=video_id,
        )
    resolved = value if parsed.scheme else str(Path(value).expanduser().resolve())
    digest = sha256(resolved.encode()).hexdigest()
    return Source(key=f"source:{digest}", url=resolved, slug=digest[:16])


def require_transition(current: str, target: str) -> None:
    allowed = {
        "queued": frozenset({"analyzing"}),
        "analyzing": frozenset({"queued", "analyzed", "failed"}),
        "failed": frozenset({"queued"}),
        "analyzed": frozenset({"failed"}),
    }
    if current not in VIDEO_STATES or target not in allowed.get(current, frozenset()):
        raise ValueError(f"invalid video transition: {current} -> {target}")


def report_hash(seed: bytes, source_keys: tuple[str, ...], created_at: str) -> str:
    """Return a short identifier that stays stable when a report is edited."""
    payload = b"\0".join(
        (seed, "\n".join(sorted(source_keys)).encode(), created_at.encode())
    )
    return sha256(payload).hexdigest()[:12]


def normalize_category(value: str) -> str:
    """Normalize a slash-separated category into a safe relative path."""
    parts = []
    for raw in value.strip(" /").split("/"):
        part = "".join(
            char.lower() if char.isascii() and char.isalnum() else "-" for char in raw
        ).strip("-")
        while "--" in part:
            part = part.replace("--", "-")
        if not part or part in {".", ".."}:
            raise ValueError(f"invalid category segment: {raw!r}")
        parts.append(part)
    if not parts:
        raise ValueError("category is required")
    return "/".join(parts)


def normalize_rating(value: object) -> int:
    """Return a valid user rating from one to five stars."""
    if isinstance(value, bool):
        raise ValueError("rating must be an integer from 1 to 5")
    try:
        rating = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("rating must be an integer from 1 to 5") from exc
    if rating not in RATING_VALUES or str(value).strip() != str(rating):
        raise ValueError("rating must be an integer from 1 to 5")
    return rating


def report_validation_errors(
    html: str, video_ids: tuple[str, ...], identity: Optional[str] = None
) -> tuple[str, ...]:
    """Return deterministic structural errors for a candidate combined report."""
    errors = []
    if re.search(r"\{\{[A-Z][A-Z0-9_]*\}\}", html):
        errors.append("unresolved_template_placeholder")
    if not re.search(r"<a\b[^>]*>[^<]*(?:Все видео|All videos)[^<]*</a>", html, re.I):
        errors.append("missing_library_link")
    for video_id in dict.fromkeys(video_ids):
        if f"/embed/{video_id}" not in html:
            errors.append(f"missing_player:{video_id}")
    timestamp_links = len(re.findall(r'class=["\'][^"\']*\bts\b', html))
    youtube_links = len(re.findall(r'class=["\'][^"\']*\byt\b', html))
    if timestamp_links != youtube_links:
        errors.append(f"timestamp_pair_mismatch:{timestamp_links}:{youtube_links}")
    if identity is not None:
        marker = 'data-vidra-report-id="true"'
        if html.count(marker) != 1 or identity not in html:
            errors.append("invalid_report_identity")
    return tuple(errors)
