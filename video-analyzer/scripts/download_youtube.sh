#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <youtube_url> [audio_lang]"
  echo "Example: $0 https://www.youtube.com/watch?v=... ru"
  exit 1
fi

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "Error: yt-dlp is not installed."
  echo "Install: pipx install yt-dlp  (or pip install --user yt-dlp)"
  exit 1
fi

url="$1"
audio_lang="${2:-ru}"
cache_root="${HOME}/.cache/video-analyzer"
mkdir -p "$cache_root"

title_raw="$(yt-dlp --no-playlist --print "%(title)s" "$url" | head -n1)"
if [[ -z "${title_raw}" ]]; then
  title_raw="video"
fi

# Keep directory name filesystem-friendly and replace spaces with underscores.
title_safe="$(printf '%s' "$title_raw" | tr '/:' '__' | tr -cd '[:alnum:] _.-' | tr -s '[:space:]' '_' | sed 's/^_*//;s/_*$//')"
if [[ -z "${title_safe}" ]]; then
  title_safe="video"
fi

ts="$(date +%Y%m%d_%H%M%S)"
out_dir="${cache_root}/${title_safe}_${ts}"
mkdir -p "$out_dir"

# Prefer requested language for combined video stream; fallback to original and then generic best.
video_format="b[language=${audio_lang}]/b[format_note*=original]/b"
# Prefer requested language for audio-only; fallback to requested language in combined stream,
# then original audio-only/combined, then generic best.
audio_format="ba[language=${audio_lang}]/b[language=${audio_lang}]/ba[format_note*=original]/b[format_note*=original]/ba/b"

video_selected="$(
  yt-dlp --no-playlist --simulate --print "%(format_id)s|%(language)s|%(format_note)s" -f "$video_format" "$url" 2>/dev/null | head -n1
)"
audio_selected="$(
  yt-dlp --no-playlist --simulate --print "%(format_id)s|%(language)s|%(format_note)s" -f "$audio_format" "$url" 2>/dev/null | head -n1
)"

# Download video file (with selected/fallback audio language embedded).
yt-dlp \
  --no-playlist \
  -f "$video_format" \
  -o "${out_dir}/original_video.%(ext)s" \
  "$url"

# Download separate audio track file.
yt-dlp \
  --no-playlist \
  -f "$audio_format" \
  -x \
  --audio-format m4a \
  -o "${out_dir}/audio_track.%(ext)s" \
  "$url"

{
  echo "url=$url"
  echo "requested_audio_lang=$audio_lang"
  echo "video_format_selector=$video_format"
  echo "audio_format_selector=$audio_format"
  echo "video_selected=${video_selected:-unknown}"
  echo "audio_selected=${audio_selected:-unknown}"
} > "${out_dir}/download_metadata.txt"

echo "Downloaded to: ${out_dir}"
