#!/usr/bin/env bash
# Build docs/media/agenttaint-demo.mp4: title card, real MCP proxy probe output,
# then a Playwright walkthrough of the dashboard on a freshly seeded session.
#
# Needs: ffmpeg, a running API (:8080) and dashboard (:3000), Playwright chromium,
# AGENTTAINT_APPROVER_TOKEN in the environment, and probe output in $PROBES
# (text file, one line per probe result).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/docs/media}"
WORK="$(mktemp -d)"
FONT_DIR="${FONT_DIR:-/usr/share/fonts/truetype/dejavu}"
PROBES="${PROBES:?set PROBES to a file with probe output}"
mkdir -p "$OUT"

(cd "$ROOT/apps/dashboard" && node scripts/screenshots.mjs "$WORK/shots" --video)

printf 'AgentTaint\nProvenance-aware enforcement at the agent tool boundary\n\nDemo: real MCP proxy probes, then the dashboard on a seeded session\n(synthetic scenarios run through the real SecurityGateway)\n' > "$WORK/title.txt"
{ printf 'MCP proxy security probes (real run)\n\n'; cut -c1-110 "$PROBES"; } > "$WORK/probes.txt"

ffmpeg -y -loglevel error -f lavfi -i color=c=0x050b18:s=1600x1000:d=4 \
  -vf "drawtext=fontfile=$FONT_DIR/DejaVuSans-Bold.ttf:textfile=$WORK/title.txt:fontcolor=0xc9f6ff:fontsize=40:line_spacing=18:x=120:y=330" \
  -r 25 -pix_fmt yuv420p "$WORK/title.mp4"
ffmpeg -y -loglevel error -f lavfi -i color=c=0x05070c:s=1600x1000:d=9 \
  -vf "drawtext=fontfile=$FONT_DIR/DejaVuSansMono.ttf:textfile=$WORK/probes.txt:fontcolor=0xd5deee:fontsize=22:line_spacing=12:x=70:y=90" \
  -r 25 -pix_fmt yuv420p "$WORK/probes.mp4"
ffmpeg -y -loglevel error -i "$WORK/shots/walkthrough.webm" -vf "scale=1600:1000,fps=25" \
  -pix_fmt yuv420p -c:v libx264 -crf 26 "$WORK/walk.mp4"
printf "file '%s'\nfile '%s'\nfile '%s'\n" "$WORK/title.mp4" "$WORK/probes.mp4" "$WORK/walk.mp4" > "$WORK/list.txt"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$WORK/list.txt" -c:v libx264 -crf 26 \
  -pix_fmt yuv420p "$OUT/agenttaint-demo.mp4"
echo "wrote $OUT/agenttaint-demo.mp4"
