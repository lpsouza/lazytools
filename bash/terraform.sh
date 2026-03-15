#!/bin/bash
FLAGS=""
[ -t 0 ] && FLAGS="-ti"

docker run --rm $FLAGS \
  -v .:/terraform \
  -v ~/:/home/ubuntu \
  -w /terraform \
  -u ubuntu \
  lpsouza/devops-tools \
  terraform "$@"
