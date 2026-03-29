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

normalize_lang() {
  local raw="${1:-}"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  raw="${raw%%-*}"
  raw="${raw%%_*}"
  if [[ -z "$raw" || "$raw" == "na" || "$raw" == "none" || "$raw" == "unknown" ]]; then
    printf 'auto'
    return
  fi
  printf '%s' "$raw"
}

translate_audio_with_yandex() {
  local video_url="$1"
  local source_lang="$2"
  local target_lang="$3"
  local out_file="$4"
  local duration_seconds="$5"
  local max_attempts="${VIDEO_ANALYZER_TRANSLATE_MAX_ATTEMPTS:-12}"
  local poll_seconds="${VIDEO_ANALYZER_TRANSLATE_POLL_SECONDS:-10}"
  local deps_dir="${HOME}/.cache/video-analyzer/vot-node"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local translator_js="${script_dir}/yandex_translate_audio.mjs"

  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "Node.js/npm not found, skip Yandex translation." >&2
    return 1
  fi
  if [[ ! -f "$translator_js" ]]; then
    echo "Translator script not found: $translator_js" >&2
    return 1
  fi

  mkdir -p "$deps_dir"
  if [[ ! -f "$deps_dir/package.json" ]]; then
    cat > "${deps_dir}/package.json" <<'JSON'
{
  "name": "video-analyzer-vot-node",
  "private": true,
  "type": "module",
  "dependencies": {
    "@vot.js/core": "2.4.12",
    "@vot.js/ext": "2.4.12",
    "@vot.js/shared": "2.4.12"
  }
}
JSON
  fi

  if [[ ! -d "$deps_dir/node_modules/@vot.js/ext" ]]; then
    (cd "$deps_dir" && npm install --silent --no-progress)
  fi

  VA_DEPS_DIR="$deps_dir" \
    node "$translator_js" \
      "$video_url" \
      "$source_lang" \
      "$target_lang" \
      "$out_file" \
      "$duration_seconds" \
      "$max_attempts" \
      "$poll_seconds"
}

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
duration_seconds="$(yt-dlp --no-playlist --print "%(duration)s" "$url" 2>/dev/null | head -n1)"
if [[ -z "$duration_seconds" ]]; then
  duration_seconds="343"
fi

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

requested_lang_norm="$(normalize_lang "$audio_lang")"
selected_audio_lang="$(printf '%s' "$audio_selected" | cut -d '|' -f2)"
selected_audio_lang_norm="$(normalize_lang "$selected_audio_lang")"
translation_status="skipped_track_exists"
translated_audio_file=""
translation_info=""

if [[ "$selected_audio_lang_norm" != "$requested_lang_norm" ]]; then
  translation_status="failed"
  translated_audio_file="${out_dir}/audio_track_translated_${requested_lang_norm}.mp3"
  if translation_info="$(translate_audio_with_yandex "$url" "$selected_audio_lang_norm" "$requested_lang_norm" "$translated_audio_file" "$duration_seconds" 2>&1)"; then
    translation_status="ok"
  else
    rm -f "$translated_audio_file"
    translated_audio_file=""
  fi
fi

translation_info="$(printf '%s' "${translation_info:-}" | tr '\n' ' ' | tr -s ' ')"

{
  echo "url=$url"
  echo "requested_audio_lang=$audio_lang"
  echo "requested_audio_lang_normalized=$requested_lang_norm"
  echo "video_duration_seconds=$duration_seconds"
  echo "video_format_selector=$video_format"
  echo "audio_format_selector=$audio_format"
  echo "video_selected=${video_selected:-unknown}"
  echo "audio_selected=${audio_selected:-unknown}"
  echo "selected_audio_lang_normalized=$selected_audio_lang_norm"
  echo "translation_status=$translation_status"
  echo "translated_audio_file=${translated_audio_file:-}"
  echo "translation_info=${translation_info:-}"
} > "${out_dir}/download_metadata.txt"

echo "Downloaded to: ${out_dir}"
