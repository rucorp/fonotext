#!/usr/bin/env bash
# Реальные скриншоты главной + OG и социальные форматы.
# Установка: npm ci --prefix tools/og
#            npx --prefix tools/og playwright install chromium
# Запуск: bash tools/og/render-og.sh
# Системный браузер: CHROME_BIN=/path/to/chromium bash tools/og/render-og.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
node "$DIR/render-previews.mjs"
