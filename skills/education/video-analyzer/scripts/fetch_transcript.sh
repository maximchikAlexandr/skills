#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 4 ]]; then
  echo "Usage: $0 <youtube-url> [source-lang] [result-lang] [output-dir]" >&2
  exit 2
fi

url="$1"
source_lang="${2:-auto}"
result_lang="${3:-ru}"
video_id="$(printf '%s' "$url" | sed -E 's#.*(v=|youtu\.be/|shorts/)([^&?/]+).*#\2#')"

if [[ -z "$video_id" || "$video_id" == "$url" ]]; then
  echo "Could not extract a YouTube video ID: $url" >&2
  exit 2
fi

output_dir="${4:-${VIDRA_HOME:-${HOME}/.vidra}/artifacts/${video_id}/transcription}"
mkdir -p "$output_dir"

if command -v vot-cli >/dev/null 2>&1; then
  command=(vot-cli)
elif command -v npx >/dev/null 2>&1; then
  command=(npx --yes vot-cli@2.0.1)
else
  echo "vot-cli is required (install it globally or provide npx)." >&2
  exit 1
fi

result="$("${command[@]}" \
  --json \
  --subs \
  --subs-format=vtt \
  --lang="$source_lang" \
  --reslang="$result_lang" \
  --no-title \
  --outdir="$output_dir" \
  "$url")"

transcript="$(python3 -c 'import json,sys; data=json.load(sys.stdin); print(data["results"][0].get("outputPath") or "")' <<<"$result")"
if [[ ! -s "$transcript" ]]; then
  printf '%s\n' "$result" >&2
  echo "vot-cli did not produce a transcript." >&2
  exit 1
fi

printf '%s\n' "$transcript"
