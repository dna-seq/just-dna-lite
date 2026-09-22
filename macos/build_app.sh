#!/bin/bash
# Build the JustDNALite.app bundle from the repo source.
# Usage: ./macos/build_app.sh <uv_binary_path> <app_version>
#
# This script is called by the GitHub Actions release workflow.

set -euo pipefail

UV_BINARY="${1:?Usage: build_app.sh <uv_binary_path> <app_version>}"
APP_VERSION="${2:?Usage: build_app.sh <uv_binary_path> <app_version>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$REPO_ROOT/dist/macos"
APP_BUNDLE="$BUILD_DIR/JustDNALite.app"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources/app"

# Info.plist with version substituted
sed "s/APP_VERSION/$APP_VERSION/g" "$SCRIPT_DIR/Info.plist" > "$APP_BUNDLE/Contents/Info.plist"

# Launcher executable
cp "$SCRIPT_DIR/entrypoint.sh" "$APP_BUNDLE/Contents/MacOS/just-dna-lite"
chmod +x "$APP_BUNDLE/Contents/MacOS/just-dna-lite"

# uv binary
cp "$UV_BINARY" "$APP_BUNDLE/Contents/Resources/uv"
chmod +x "$APP_BUNDLE/Contents/Resources/uv"

# Icon (if it exists)
if [ -f "$SCRIPT_DIR/icon.icns" ]; then
    cp "$SCRIPT_DIR/icon.icns" "$APP_BUNDLE/Contents/Resources/icon.icns"
fi

# Application source
APP_DEST="$APP_BUNDLE/Contents/Resources/app"

cp "$REPO_ROOT/pyproject.toml" "$APP_DEST/"
cp "$REPO_ROOT/README.md" "$APP_DEST/"  # the package readme; uv sync cannot build the root package without it
cp "$REPO_ROOT/uv.lock" "$APP_DEST/"
cp "$REPO_ROOT/modules.yaml" "$APP_DEST/"
cp "$REPO_ROOT/.python-version" "$APP_DEST/"
cp "$REPO_ROOT/.env.template" "$APP_DEST/"
cp "$REPO_ROOT/dagster.yaml.template" "$APP_DEST/"

rsync -a --exclude='__pycache__' --exclude='*.pyc' \
    "$REPO_ROOT/src/" "$APP_DEST/src/"

rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='.ruff_cache' \
    "$REPO_ROOT/just-dna-pipelines/" "$APP_DEST/just-dna-pipelines/"

rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='.web' --exclude='.ruff_cache' \
    "$REPO_ROOT/webui/" "$APP_DEST/webui/"

rsync -a "$REPO_ROOT/images/" "$APP_DEST/images/"

mkdir -p "$APP_DEST/docs"
cp "$REPO_ROOT/docs/FAQ.md" "$APP_DEST/docs/"  # the FAQ page renders this file

echo "Built $APP_BUNDLE (version $APP_VERSION)"
