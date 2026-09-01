"""Pure domain functions for Vidra.

I/O belongs in ``storage`` and ``cli``. Keeping normalization and transition
rules here makes the behavior deterministic and easy to test.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VIDEO_STATES = frozenset({"queued", "analyzing", "analyzed", "failed"})
CATEGORY_LIMIT = 10


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    slug: str


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
