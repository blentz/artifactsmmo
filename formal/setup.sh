#!/usr/bin/env bash
# Clone a pinned PlusPy into formal/vendor/ (gitignored). Re-runnable.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
PLUSPY_DIR="$VENDOR/PlusPy"
PLUSPY_REPO="https://github.com/tlaplus/PlusPy.git"
PLUSPY_COMMIT="26254e16d23cbc076b870036fecbf586c0d51e46"

mkdir -p "$VENDOR"
if [ ! -d "$PLUSPY_DIR/.git" ]; then
  git clone "$PLUSPY_REPO" "$PLUSPY_DIR"
fi
if ! git -C "$PLUSPY_DIR" cat-file -e "$PLUSPY_COMMIT^{commit}" 2>/dev/null; then
  git -C "$PLUSPY_DIR" fetch --all --tags
fi
git -C "$PLUSPY_DIR" checkout "$PLUSPY_COMMIT"
echo "PlusPy ready at $PLUSPY_DIR (commit $PLUSPY_COMMIT)"
