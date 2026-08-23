#!/bin/bash
# Swap in the real album art:  ./set-art.sh ~/Downloads/gunsaway.jpg
# Handles HEIC/PNG/JPG, downscales for mobile, and bumps the service-worker
# cache so phones actually pick up the new image.
set -e
[ -z "$1" ] && { echo "usage: ./set-art.sh <image file>"; exit 1; }
[ -f "$1" ] || { echo "no such file: $1"; exit 1; }
cd "$(dirname "$0")"
sips -s format jpeg -s formatOptions 78 -Z 1600 "$1" --out band.jpg >/dev/null
echo "band.jpg  $(sips -g pixelWidth -g pixelHeight band.jpg | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w"x"h}')  $(du -h band.jpg | cut -f1)"
v=$(grep -o "droptuner-v[0-9]*" sw.js | head -1 | grep -o '[0-9]*$')
sed -i '' "s/droptuner-v$v/droptuner-v$((v+1))/" sw.js
echo "service worker cache -> droptuner-v$((v+1))"
echo "now:  git add -A && git commit -m 'Use real album art' && git push"
