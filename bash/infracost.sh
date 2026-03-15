#!/bin/bash
FLAGS=""
[ -t 0 ] && FLAGS="-ti"

[ -f "$(dirname "$0")/../.env" ] && export $(grep -v '^#' "$(dirname "$0")/../.env" | xargs)

docker run --rm $FLAGS \
  -v .:/infracost \
  -w /infracost \
  -e INFRACOST_API_KEY="$INFRACOST_API_KEY" \
  infracost/infracost "$@"
