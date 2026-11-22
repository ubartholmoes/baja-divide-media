#!/usr/bin/env bash
# one-time setup of the Baja Divide post kit (run from the kit folder)
set -e
cd "$(dirname "$0")"
pip install --break-system-packages -q pillow-heif numpy scipy opencv-python-headless 2>&1 | grep -v WARNING || true
which ffmpeg >/dev/null || { echo "ffmpeg missing"; exit 1; }
if [ ! -d model/package ]; then
  npm pack sts-whisper-small >/dev/null && mkdir -p model && tar xzf sts-whisper-small-*.tgz -C model && rm sts-whisper-small-*.tgz
fi
[ -f package.json ] || npm init -y >/dev/null
[ -d node_modules/@huggingface/transformers ] || npm i --ignore-scripts @huggingface/transformers >/dev/null
mkdir -p fonts
for f in anton archivo-black inter; do
  npm pack @fontsource/$f >/dev/null && tar xzf fontsource-$f-*.tgz && rm fontsource-$f-*.tgz
  cp package/files/$f-latin-*-normal.woff fonts/ 2>/dev/null || true; rm -rf package
done
ls fonts | grep -E "anton-latin-400|archivo-black-latin-400|inter-latin-(700|800)" && echo "kit ready"
