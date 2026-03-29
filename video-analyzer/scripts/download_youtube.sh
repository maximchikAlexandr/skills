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

ensure_vot_node_deps() {
  local deps_dir="${HOME}/.cache/video-analyzer/vot-node"

  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "Node.js/npm not found, skip Yandex API features." >&2
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

  printf '%s' "$deps_dir"
}

translate_audio_with_yandex() {
  local video_url="$1"
  local source_lang="$2"
  local target_lang="$3"
  local out_file="$4"
  local duration_seconds="$5"
  local max_attempts="${VIDEO_ANALYZER_TRANSLATE_MAX_ATTEMPTS:-12}"
  local poll_seconds="${VIDEO_ANALYZER_TRANSLATE_POLL_SECONDS:-10}"
  local deps_dir
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local translator_js="${script_dir}/yandex_translate_audio.mjs"

  if [[ ! -f "$translator_js" ]]; then
    echo "Translator script not found: $translator_js" >&2
    return 1
  fi
  if ! deps_dir="$(ensure_vot_node_deps)"; then
    return 1
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

fetch_transcription_with_yandex() {
  local video_url="$1"
  local source_lang="$2"
  local target_lang="$3"
  local out_dir="$4"
  local duration_seconds="$5"
  local max_attempts="${VIDEO_ANALYZER_SUBS_MAX_ATTEMPTS:-8}"
  local poll_seconds="${VIDEO_ANALYZER_SUBS_POLL_SECONDS:-5}"
  local deps_dir
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local transcript_js="${script_dir}/yandex_fetch_transcription.mjs"

  if [[ ! -f "$transcript_js" ]]; then
    echo "Transcription script not found: $transcript_js" >&2
    return 1
  fi
  if ! deps_dir="$(ensure_vot_node_deps)"; then
    return 1
  fi

  VA_DEPS_DIR="$deps_dir" \
    node "$transcript_js" \
      "$video_url" \
      "$source_lang" \
      "$target_lang" \
      "$out_dir" \
      "$duration_seconds" \
      "$max_attempts" \
      "$poll_seconds"
}

fetch_transcription_from_site_subtitles() {
  local video_url="$1"
  local target_lang="$2"
  local source_lang="$3"
  local out_dir="$4"
  local tmp_dir="${out_dir}/.tmp_site_subs"
  local with_timestamps_file="${out_dir}/transcript_with_timestamps.txt"
  local plain_file="${out_dir}/transcript_plain.txt"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local converter_py="${script_dir}/subtitles_to_txt.py"
  local subtitle_file=""
  local attempt_langs=()
  local lang_set=""
  local lang_expr=""
  local detected_sub_lang=""

  if [[ ! -f "$converter_py" ]]; then
    echo "Subtitle converter script not found: $converter_py" >&2
    return 1
  fi

  mkdir -p "$out_dir"

  attempt_langs+=("$target_lang")
  if [[ -n "$source_lang" && "$source_lang" != "auto" && "$source_lang" != "$target_lang" ]]; then
    attempt_langs+=("$source_lang")
  fi
  if [[ "$target_lang" != "en" ]]; then
    attempt_langs+=("en")
  fi

  for lang in "${attempt_langs[@]}"; do
    if [[ -z "$lang" ]]; then
      continue
    fi
    case ",$lang_set," in
      *",$lang,"*) continue ;;
      *) lang_set="${lang_set},${lang}" ;;
    esac
    rm -rf "$tmp_dir"
    mkdir -p "$tmp_dir"
    if [[ "$lang" == "en" ]]; then
      lang_expr="en,en-US,en-orig,en.*"
    else
      lang_expr="${lang},${lang}.*"
    fi
    yt-dlp \
      --skip-download \
      --write-subs \
      --write-auto-subs \
      --sub-lang "$lang_expr" \
      --sub-format "best" \
      -o "${tmp_dir}/subtitle.%(ext)s" \
      "$video_url" >/dev/null 2>&1 || true

    subtitle_file="$(find "$tmp_dir" -maxdepth 1 -type f \( -name '*.srt' -o -name '*.vtt' \) | head -n1)"
    if [[ -n "$subtitle_file" ]]; then
      break
    fi
  done

  if [[ -z "$subtitle_file" ]]; then
    rm -rf "$tmp_dir"
    return 1
  fi

  python3 "$converter_py" "$subtitle_file" "$with_timestamps_file" "$plain_file"

  detected_sub_lang="$(basename "$subtitle_file" | sed -E 's/^subtitle\.([^.]+)\..+$/\1/')"
  if [[ -z "$detected_sub_lang" ]]; then
    detected_sub_lang="unknown"
  fi

  rm -rf "$tmp_dir"
  echo "site_subtitles_lang=$detected_sub_lang"
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
transcription_status="failed"
transcription_source="none"
transcription_dir="${out_dir}/transcription"
transcription_with_timestamps_file="${transcription_dir}/transcript_with_timestamps.txt"
transcription_plain_file="${transcription_dir}/transcript_plain.txt"
transcription_info=""

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

if transcription_info="$(fetch_transcription_with_yandex "$url" "$selected_audio_lang_norm" "$requested_lang_norm" "$transcription_dir" "$duration_seconds" 2>&1)"; then
  transcription_status="ok"
  transcription_source="yandex"
else
  rm -f "$transcription_with_timestamps_file" "$transcription_plain_file" || true
  if transcription_info="$(fetch_transcription_from_site_subtitles "$url" "$requested_lang_norm" "$selected_audio_lang_norm" "$transcription_dir" 2>&1)"; then
    transcription_status="ok"
    transcription_source="site_subtitles"
  else
    transcription_status="failed"
    transcription_source="none"
  fi
fi
transcription_info="$(printf '%s' "${transcription_info:-}" | tr '\n' ' ' | tr -s ' ')"

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
  echo "transcription_status=$transcription_status"
  echo "transcription_source=$transcription_source"
  echo "transcription_dir=$transcription_dir"
  echo "transcription_with_timestamps_file=$transcription_with_timestamps_file"
  echo "transcription_plain_file=$transcription_plain_file"
  echo "transcription_info=${transcription_info:-}"
} > "${out_dir}/download_metadata.txt"

echo "Downloaded to: ${out_dir}"
