#!/usr/bin/env bash
# ============================================================================
# Op^3 full reproduction script (Task 21).
#
# Clones a fresh copy of the Op^3 repository at the v0.3.0 tag into a
# temporary directory, bootstraps the OpenFAST v5.0.0 binary and r-test
# directory, and runs the complete release validation report. This is
# the "clean room" test: any independent reviewer should be able to
# execute this script on a fresh machine and obtain a matching
# report.md / report.json.
#
# Usage:
#     bash scripts/reproduce_all.sh
#     bash scripts/reproduce_all.sh --tag v0.3.0 --workdir /tmp/op3_reproduce
# ============================================================================

set -euo pipefail

TAG="${OP3_TAG:-v0.3.0}"
WORKDIR="${OP3_WORKDIR:-/tmp/op3_reproduce}"
REPO_URL="${OP3_REPO_URL:-https://github.com/ksk5429/numerical_model.git}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)      TAG="$2"; shift 2 ;;
        --workdir)  WORKDIR="$2"; shift 2 ;;
        --repo)     REPO_URL="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--tag v0.3.0] [--workdir DIR] [--repo URL]"
            exit 0 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

echo "============================================================"
echo " Op^3 reproduction run"
echo "============================================================"
echo "  tag     : $TAG"
echo "  workdir : $WORKDIR"
echo "  repo    : $REPO_URL"
echo ""

# 1. Clean workdir
if [[ -d "$WORKDIR" ]]; then
    echo "  workdir exists; reusing"
else
    mkdir -p "$WORKDIR"
fi
cd "$WORKDIR"

# 2. Clone (or update)
if [[ ! -d numerical_model ]]; then
    git clone "$REPO_URL" numerical_model
fi
cd numerical_model
git fetch --tags
git checkout "$TAG"
echo "  checkout: $(git describe)"

# 3. Python dependencies
python -m pip install --upgrade pip
pip install -e ".[test,docs]"

# 4. Bootstrap OpenFAST v5.0.0
mkdir -p tools/openfast
if [[ ! -f tools/openfast/OpenFAST.exe ]]; then
    echo "  downloading OpenFAST v5.0.0 binary ..."
    curl -sL -o tools/openfast/OpenFAST.exe \
        https://github.com/OpenFAST/openfast/releases/download/v5.0.0/OpenFAST.exe
fi

# 5. Bootstrap r-test
mkdir -p tools/r-test_v5
if [[ ! -d tools/r-test_v5/r-test ]]; then
    cd tools/r-test_v5
    git clone --depth=1 --branch v5.0.0 https://github.com/OpenFAST/r-test.git
    cd ../..
fi

# 6. Run the full validation report
PYTHONUTF8=1 python scripts/release_validation_report.py

# 7. Print the report path
LATEST=$(ls -td validation/release_report/v*/ | head -1)
echo ""
echo "============================================================"
echo " Reproduction complete."
echo " Report: $LATEST/report.md"
echo "============================================================"
