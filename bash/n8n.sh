#!/bin/bash
FLAGS=""
[ -t 0 ] && FLAGS="-ti"

[ -f "$(dirname "$0")/../.env" ] && export $(grep -v '^#' "$(dirname "$0")/../.env" | xargs)

docker run $FLAGS \
  -e N8N_API_KEY="$N8N_API_KEY" \
  -e N8N_INSTANCE_URL="$N8N_INSTANCE_URL" \
  n8n-cli "$@"
