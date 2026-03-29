#!/usr/bin/env python3
import pathlib
import re
import sys


def convert(subtitle_path: pathlib.Path, out_timed: pathlib.Path, out_plain: pathlib.Path) -> int:
    timing_re = re.compile(
        r"^\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2}[,\.][0-9]{3})\s*-->\s*([0-9]{1,2}:[0-9]{2}:[0-9]{2}[,\.][0-9]{3})"
    )
    index_re = re.compile(r"^\s*\d+\s*$")

    lines = subtitle_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    blocks: list[tuple[str, str, str]] = []
    cur_start: str | None = None
    cur_end: str | None = None
    cur_text: list[str] = []

    def flush() -> None:
        nonlocal cur_start, cur_end, cur_text
        if cur_start and cur_end and cur_text:
            text = " ".join(part.strip() for part in cur_text if part.strip()).strip()
            if text:
                blocks.append((cur_start, cur_end, text))
        cur_start = None
        cur_end = None
        cur_text = []

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if index_re.match(line):
            continue
        m = timing_re.match(line)
        if m:
            flush()
            cur_start = m.group(1).replace(".", ",")
            cur_end = m.group(2).replace(".", ",")
            continue
        if cur_start:
            cleaned = re.sub(r"<[^>]+>", "", line).strip()
            if cleaned:
                cur_text.append(cleaned)

    flush()
    if not blocks:
        return 1

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
