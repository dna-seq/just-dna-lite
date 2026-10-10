#!/usr/bin/env bash
# Download each Generation I module in modules.tsv at its pinned commit into DEST/<kind>s/<name>/,
# the layout of an OakVar modules directory, and print the sha256 of every archive.
#
#   fetch_modules.sh DEST
set -euo pipefail

dest="$1"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tail -n +2 "$here/modules.tsv" | while IFS=$'\t' read -r name kind repo commit _date _version; do
    target="$dest/${kind}s/$name"
    archive="$dest/archives/${name}-${commit}.tar.gz"
    mkdir -p "$target" "$dest/archives"
    curl -sS -L --fail -o "$archive" "https://codeload.github.com/$repo/tar.gz/$commit"
    tar -xzf "$archive" -C "$target" --strip-components=1
    printf '%s  %s\n' "$(sha256sum "$archive" | cut -d' ' -f1)" "$(basename "$archive")"
done
