#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="analyze-this-2026"
OUT_FILE=""
OVERWRITE=false

usage() {
  cat <<'EOF'
Usage:
  ./backend/scripts/export-app-env-from-gcloud-secrets.sh [options]

Exports runtime secret values from Google Secret Manager in KEY=VALUE format.
This output is intended for the sops-managed app_env secret content.

Options:
  --project <id>      GCP project id (default: analyze-this-2026)
  --out <path>        Write to file instead of stdout
  --overwrite         Allow overwriting --out file
  --help              Show this help

Examples:
  ./backend/scripts/export-app-env-from-gcloud-secrets.sh --project analyze-this-2026
  ./backend/scripts/export-app-env-from-gcloud-secrets.sh --out /tmp/app_env
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_ID="${2:-}"
      shift 2
      ;;
    --out)
      OUT_FILE="${2:-}"
      shift 2
      ;;
    --overwrite)
      OVERWRITE=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -n "$OUT_FILE" && -e "$OUT_FILE" && "$OVERWRITE" != true ]]; then
  echo "Refusing to overwrite existing file: $OUT_FILE" >&2
  echo "Use --overwrite to replace it." >&2
  exit 1
fi

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd gcloud

check_secret() {
  local secret_name="$1"
  if ! gcloud secrets describe "$secret_name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    echo "Missing secret in project '$PROJECT_ID': $secret_name" >&2
    return 1
  fi
}

read_secret() {
  local secret_name="$1"
  gcloud secrets versions access latest \
    --secret "$secret_name" \
    --project "$PROJECT_ID"
}

emit_line() {
  local key="$1"
  local value="$2"
  printf '%s=%s\n' "$key" "$value"
}

# env var name -> secret manager secret name
ENV_KEYS=(
  SECRET_KEY
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  GOOGLE_EXTENSION_CLIENT_ID
  GOOGLE_IOS_CLIENT_ID
  GOOGLE_ANDROID_CLIENT_ID
  GOOGLE_ANDROID_DEBUG_CLIENT_ID
  FIREBASE_STORAGE_BUCKET
  IRCCAT_BEARER_TOKEN
  HONEYCOMB_API_KEY
  OPENROUTER_API_KEY
  OPENROUTER_MODEL
)

secret_name_for_env() {
  case "$1" in
    IRCCAT_BEARER_TOKEN) echo "irc-server-password" ;;
    HONEYCOMB_API_KEY) echo "honey-comb-api-key" ;;
    *) echo "$1" ;;
  esac
}

tmp_file="$(mktemp)"
trap 'rm -f "$tmp_file"' EXIT

{
  echo "# Generated from Google Secret Manager project: $PROJECT_ID"
  echo "# Generated at: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "# Paste these lines into your sops app_env secret payload."
  for env_key in "${ENV_KEYS[@]}"; do
    secret_name="$(secret_name_for_env "$env_key")"
    check_secret "$secret_name"
    secret_value="$(read_secret "$secret_name")"
    emit_line "$env_key" "$secret_value"
  done
} >"$tmp_file"

if [[ -n "$OUT_FILE" ]]; then
  install -m 600 "$tmp_file" "$OUT_FILE"
  echo "Wrote app_env content to: $OUT_FILE" >&2
else
  cat "$tmp_file"
fi
