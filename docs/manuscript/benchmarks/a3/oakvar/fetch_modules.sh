#!/usr/bin/env bash
# Download each Generation I module in a module list at its pinned commit into DEST/<kind>s/<name>/,
# the layout of an OakVar modules directory, and print the sha256 of every archive.
# modules-current.tsv: each repo's latest commit on 2026-10-11 (used first, with OakVar 2.13.1);
# modules.tsv: the last commit on or before 2023-05-07 (the May 2023 fallback, with OakVar 2.9.15).
#
#   fetch_modules.sh DEST [LIST.tsv]   (default modules.tsv)
set -euo pipefail

dest="$1"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
list="${2:-$here/modules.tsv}"
tail -n +2 "$list" | while IFS=$'\t' read -r name kind repo commit _date _version; do
    target="$dest/${kind}s/$name"
    archive="$dest/archives/${name}-${commit}.tar.gz"
    mkdir -p "$target" "$dest/archives"
    curl -sS -L --fail -o "$archive" "https://codeload.github.com/$repo/tar.gz/$commit"
    tar -xzf "$archive" -C "$target" --strip-components=1
    printf '%s  %s\n' "$(sha256sum "$archive" | cut -d' ' -f1)" "$(basename "$archive")"
done
