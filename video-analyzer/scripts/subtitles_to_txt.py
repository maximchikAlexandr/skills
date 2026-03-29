#!/usr/bin/env python3
import pathlib
import re
import sys

TIMING_RE = re.compile(
    r"^\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2}[,\.][0-9]{3})\s*-->\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2}[,\.][0-9]{3})"
)
INDEX_RE = re.compile(r"^\s*\d+\s*$")
TAG_RE = re.compile(r"<[^>]+>")


def _parse_timestamp_ms(ts: str) -> int:
    """Parse an SRT/VTT timestamp string into milliseconds.

    Args:
        ts: Timestamp in format ``HH:MM:SS,mmm`` or ``HH:MM:SS.mmm``.

    Returns:
        Total milliseconds represented by the timestamp.
    """
    h, m, rest = ts.replace(".", ",").split(":")
    s, ms = rest.split(",")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def _deduplicate_rolling_cues(
    blocks: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Remove progressive duplication from YouTube-style rolling auto-captions.

    YouTube auto-generated VTT subtitles use a rolling display pattern where
    short flash cues (~10 ms) alternate with longer cues that repeat the tail
    of the previous cue and append new words.  This function filters the flash
    cues and strips word-level overlap between consecutive entries.

    Args:
        blocks: List of ``(start_ts, end_ts, text)`` tuples.

    Returns:
        Deduplicated list of ``(start_ts, end_ts, text)`` tuples.  Returned
        unchanged when the rolling pattern is not detected.
    """
    if len(blocks) <= 1:
        return blocks

    filtered = [
        (s, e, t)
        for s, e, t in blocks
        if _parse_timestamp_ms(e) - _parse_timestamp_ms(s) >= 100
    ]
    if not filtered:
        return blocks

    flash_ratio = 1.0 - len(filtered) / len(blocks)
    if flash_ratio < 0.2:
        return blocks

    result = [filtered[0]]
    for i in range(1, len(filtered)):
        prev_words = filtered[i - 1][2].split()
        start, end, text = filtered[i]
        curr_words = text.split()
        new_words = curr_words
        for overlap_len in range(min(len(prev_words), len(curr_words)), 0, -1):
            if prev_words[-overlap_len:] == curr_words[:overlap_len]:
                new_words = curr_words[overlap_len:]
                break
        joined = " ".join(new_words).strip()
        if joined:
            result.append((start, end, joined))

    return result


def _parse_cues(text: str) -> list[tuple[str, str, str]]:
    """Parse SRT/VTT subtitle text into a list of cue blocks.

    Args:
        text: Raw subtitle file content.

    Returns:
        List of ``(start_ts, end_ts, text)`` tuples with normalised timestamps.
    """
    blocks: list[tuple[str, str, str]] = []
    cur_start: str | None = None
    cur_end: str | None = None
    cur_text: list[str] = []

    def flush() -> None:
        nonlocal cur_start, cur_end, cur_text
        if cur_start and cur_end and cur_text:
            joined = " ".join(part.strip() for part in cur_text if part.strip()).strip()
            if joined:
                blocks.append((cur_start, cur_end, joined))
        cur_start = None
        cur_end = None
        cur_text = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if INDEX_RE.match(line):
            continue
        m = TIMING_RE.match(line)
        if m:
            flush()
            cur_start = m.group(1).replace(".", ",")
            cur_end = m.group(2).replace(".", ",")
            continue
        if cur_start:
            cleaned = TAG_RE.sub("", line).strip()
            if cleaned:
                cur_text.append(cleaned)

    flush()
    return blocks


def convert(subtitle_path: pathlib.Path, out_timed: pathlib.Path, out_plain: pathlib.Path) -> int:
    """Convert an SRT/VTT subtitle file into two plain-text transcripts.

    Args:
        subtitle_path: Path to the source ``.srt`` or ``.vtt`` file.
        out_timed: Destination for the timestamped transcript.
        out_plain: Destination for the plain (no timestamps) transcript.

    Returns:
        ``0`` on success, ``1`` when no subtitle cues were found.
    """
    raw = subtitle_path.read_text(encoding="utf-8", errors="ignore")
    blocks = _parse_cues(raw)
    if not blocks:
        return 1

    blocks = _deduplicate_rolling_cues(blocks)

    out_timed.parent.mkdir(parents=True, exist_ok=True)
    out_plain.parent.mkdir(parents=True, exist_ok=True)
    out_timed.write_text(
        "\n".join(f"[{start} --> {end}] {text}" for start, end, text in blocks) + "\n",
        encoding="utf-8",
    )
    out_plain.write_text(
        "\n".join(text for _, _, text in blocks) + "\n",
        encoding="utf-8",
    )
    return 0


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: subtitles_to_txt.py <subtitle_file.(srt|vtt)> <transcript_with_timestamps.txt> <transcript_plain.txt>",
            file=sys.stderr,
        )
        return 2

    subtitle_path = pathlib.Path(sys.argv[1])
    out_timed = pathlib.Path(sys.argv[2])
    out_plain = pathlib.Path(sys.argv[3])
    return convert(subtitle_path, out_timed, out_plain)


if __name__ == "__main__":
    raise SystemExit(main())
