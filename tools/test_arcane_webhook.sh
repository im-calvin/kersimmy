#!/usr/bin/env bash
set +x
set -euo pipefail

# A successful request queues a real Arcane redeploy.
unsafe='[[:space:]"\\]'
for setting in ARCANE_WEBHOOK_URL CF_ACCESS_CLIENT_ID CF_ACCESS_CLIENT_SECRET; do
  if [[ -z ${!setting:-} ]]; then
    if [[ ! -t 0 ]]; then
      printf 'Set %s before running non-interactively.\n' "$setting" >&2
      exit 1
    fi
    printf '%s (hidden): ' "$setting" >&2
    if ! IFS= read -rs "$setting"; then
      printf '\nInput canceled.\n' >&2
      exit 1
    fi
    printf '\n' >&2
  fi

  if [[ -z ${!setting} || ${!setting} =~ $unsafe ]]; then
    printf 'Invalid value for %s.\n' "$setting" >&2
    exit 1
  fi
done

if [[ $ARCANE_WEBHOOK_URL != https://* ]]; then
  printf 'ARCANE_WEBHOOK_URL must use HTTPS.\n' >&2
  exit 1
fi

response_headers=$(mktemp "${TMPDIR:-/tmp}/arcane-webhook-headers.XXXXXX")
trap 'rm -f -- "$response_headers"' EXIT

# Read credentials on stdin and ignore user curl configuration.
if status=$(curl -q --proto '=https' --globoff --silent \
  --dump-header "$response_headers" --output /dev/null --write-out '%{http_code}' \
  --max-time 60 --request POST --config - <<EOF
url = "$ARCANE_WEBHOOK_URL"
header = "CF-Access-Client-Id: $CF_ACCESS_CLIENT_ID"
header = "CF-Access-Client-Secret: $CF_ACCESS_CLIENT_SECRET"
EOF
); then
  printf 'HTTP %s\n' "$status"
else
  printf 'Could not contact the Arcane webhook (curl exit %s).\n' "$?" >&2
  exit 1
fi

if [[ $status != 202 ]]; then
  # Allowlist diagnostic headers. Raw headers can contain cookies or the webhook URL.
  LC_ALL=C awk '
    /^HTTP\// { ray = ""; challenge = 0 }
    tolower($1) == "cf-ray:" {
      sub(/\r$/, "", $2)
      if ($2 ~ /^[[:xdigit:]]+-[A-Z][A-Z][A-Z]$/) ray = $2
    }
    tolower($1) == "cf-mitigated:" && $2 ~ /^challenge\r?$/ { challenge = 1 }
    END {
      if (ray != "") print "Cloudflare Ray ID " ray
      if (challenge) print "Cloudflare returned a challenge page."
    }
  ' "$response_headers"
fi

case "$status" in
  202) printf 'Arcane accepted the redeploy request. Check its Event Log for the result.\n' ;;
  302) printf 'The request redirected. Check the Cloudflare Access path and Service Auth policy.\n' >&2; exit 1 ;;
  401|403) printf 'The request was denied. Check Cloudflare Access logs, Security Events, and the Arcane webhook.\n' >&2; exit 1 ;;
  *) printf 'Expected HTTP 202 from the Arcane webhook.\n' >&2; exit 1 ;;
esac
