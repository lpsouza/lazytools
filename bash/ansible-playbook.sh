#!/bin/bash
FLAGS=""
[ -t 0 ] && FLAGS="-ti"

docker run --rm $FLAGS \
  -v .:/ansible \
  -v ~/.ssh:/root/.ssh \
  -w /ansible \
  lpsouza/devops-tools \
  ansible-playbook "$@"
