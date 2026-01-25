#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

pushd "$ROOT_DIR/mobile" >/dev/null

if [[ ! -d node_modules ]]; then
  npm install
fi

npx expo export --platform android --platform ios --non-interactive

popd >/dev/null
