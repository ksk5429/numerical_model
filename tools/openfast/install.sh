#!/usr/bin/env bash
# Reproducible OpenFAST v4.0.2 binary installer.
#
# Downloads the official Windows x64 build of openfast_x64.exe from the
# OpenFAST GitHub release into this directory. The binary itself is
# .gitignored so the repo stays small.
#
# Usage:
#   bash tools/openfast/install.sh
#
# Verification:
#   tools/openfast/openfast_x64.exe -v
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
URL="https://github.com/OpenFAST/openfast/releases/download/v4.0.2/openfast_x64.exe"
DEST="$HERE/openfast_x64.exe"

if [[ -f "$DEST" ]]; then
    echo "Binary already present: $DEST"
    "$DEST" -v 2>&1 | head -3
    exit 0
fi

echo "Downloading OpenFAST v4.0.2 (~52 MB) ..."
curl -L -o "$DEST" "$URL"
echo "Installed: $DEST"
"$DEST" -v 2>&1 | head -3
