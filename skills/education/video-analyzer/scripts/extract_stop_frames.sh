#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <video_path> [fps]" >&2
  echo "Example: $0 /path/video.mp4 0.5   # 1 frame every 2 seconds" >&2
  exit 1
fi

VIDEO_PATH="$1"
FPS="${2:-0.1}"
if [[ ! -f "$VIDEO_PATH" ]]; then
  echo "Video file not found: $VIDEO_PATH" >&2
  exit 1
fi

for tool_name in ffmpeg ffprobe python3; do
  if ! command -v "$tool_name" >/dev/null 2>&1; then
    echo "Required tool is missing: $tool_name" >&2
    exit 1
  fi
done

if ! python3 - "$FPS" <<'PY'
import sys
try:
    value = float(sys.argv[1])
except Exception:
    raise SystemExit(1)
raise SystemExit(0 if value > 0 else 1)
PY
then
  echo "Invalid fps value: $FPS (must be a positive number)" >&2
  exit 1
fi

VIDEO_ABS_PATH="$(python3 -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$VIDEO_PATH")"
VIDEO_DIR="$(dirname "$VIDEO_ABS_PATH")"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Frames are saved next to the original video in a dedicated subfolder.
FRAMES_DIR="${VIDEO_DIR}/frames_${TIMESTAMP}"
mkdir -p "$FRAMES_DIR"

DURATION_SECONDS="$(
  ffprobe \
    -v error \
    -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 \
    "$VIDEO_ABS_PATH"
)"

if [[ -z "$DURATION_SECONDS" ]]; then
  echo "Could not determine video duration." >&2
  exit 1
fi

read -r FRAME_LIMIT FRAME_INTERVAL <<<"$(
  python3 - "$DURATION_SECONDS" "$FPS" <<'PY'
import math
import sys

duration = max(float(sys.argv[1]), 1.0)
fps = float(sys.argv[2])
frame_limit = min(120, max(1, int(duration * fps)))
interval = 1.0 / fps
print(frame_limit, f"{interval:.4f}")
PY
)"

METADATA_FILE="$FRAMES_DIR/metadata.txt"
{
  echo "video_path=$VIDEO_ABS_PATH"
  echo "frames_dir=$FRAMES_DIR"
  echo "duration_seconds=$DURATION_SECONDS"
  echo "fps=$FPS"
  echo "frame_limit=$FRAME_LIMIT"
  echo "frame_interval_seconds=$FRAME_INTERVAL"
} >"$METADATA_FILE"

ffmpeg \
  -hide_banner \
  -loglevel error \
  -y \
  -i "$VIDEO_ABS_PATH" \
  -vf "fps=${FPS},scale='min(960,iw)':-2" \
  -frames:v "$FRAME_LIMIT" \
  -q:v 8 \
  "$FRAMES_DIR/frame_%03d.jpg"

EXTRACTED_FRAME_COUNT="$(find "$FRAMES_DIR" -maxdepth 1 -name 'frame_*.jpg' | wc -l | tr -d ' ')"
echo "extracted_frame_count=$EXTRACTED_FRAME_COUNT" >>"$METADATA_FILE"

echo "$FRAMES_DIR"
