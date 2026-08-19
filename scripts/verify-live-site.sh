#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <live-base-url>"
  echo "Example: $0 https://trackflow-preview.example.com"
  exit 1
fi

base_url="${1%/}"
paths=(
  "/index.html"
  "/application.html"
  "/es/index.html"
  "/es/application.html"
)

echo "Verifying live site: $base_url"

for path in "${paths[@]}"; do
  url="$base_url$path"
  code=$(curl -sS -o /dev/null -L -w "%{http_code}" "$url")
  if [[ "$code" -lt 200 || "$code" -ge 400 ]]; then
    echo "FAIL $url -> HTTP $code"
    exit 1
  fi
  echo "PASS $url -> HTTP $code"
done

echo "All live route checks passed."
