#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
version=${1:-local}
if [[ $# -gt 1 || ! "$version" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]]; then
    echo "Usage: bash ./build.sh [version]" >&2
    exit 1
fi
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo "This build requires Linux x86-64." >&2
    exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
fi
python=.venv/bin/python
"$python" -c 'import tkinter; import sys; assert sys.version_info >= (3, 13), "Python 3.13 or newer required"'
"$python" -m pip install -r requirements.txt pyinstaller

mkdir -p dist
staging=$(mktemp -d dist/.linux-build.XXXXXX)
trap 'rm -rf -- "$staging"' EXIT
"$python" -m PyInstaller --onedir --name GitHubFolderSync --specpath build \
    --distpath "$staging" --collect-data customtkinter \
    --add-data "$PWD/assets/sync-icon.png:assets" \
    --add-data "$PWD/assets/icons:assets/icons" github_folder_sync.py

archive="GitHubFolderSync-${version}-linux-x86_64.tar.gz"
tar -czf "$staging/$archive" -C "$staging" GitHubFolderSync
mv -f -- "$staging/$archive" "dist/$archive"
printf 'Archive: dist/%s\n' "$archive"
