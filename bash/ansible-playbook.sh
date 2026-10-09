#!/bin/bash

# Prevent MSYS/Git Bash on Windows from auto-converting volume paths
export MSYS_NO_PATHCONV=1

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

FLAGS=""
[ -t 0 ] && FLAGS="-ti"

##
# Function to check required tools (docker).
##
check_dependencies() {
    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}Error: Docker is not installed or not in PATH. Please install it to run this script.${NC}"
        exit 1
    fi
}

##
# Function to load environment variables from .env file.
##
load_env() {
    local SCRIPT_PATH
    SCRIPT_PATH=$(readlink -f "$0")
    local SCRIPT_DIR
    SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
    local ENV_FILE="${SCRIPT_DIR}/../.env"

    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    fi
}

# Resolve paths safely for POSIX and Git Bash on Windows
TARGET_PWD="$PWD"
TARGET_HOME="$HOME"
if command -v cygpath >/dev/null 2>&1; then
    TARGET_PWD="$(cygpath -m "$PWD")"
    TARGET_HOME="$(cygpath -m "$HOME")"
fi

# Initialize script
check_dependencies
load_env

# Setup extra mounts for SSH agent
EXTRA_DOCKER_ARGS=()

# Detect 1Password or generic SSH agent socket
SSH_SOCK=""
if [ -S "${HOME}/.1password/agent.sock" ]; then
    SSH_SOCK="${HOME}/.1password/agent.sock"
elif [ -n "$SSH_AUTH_SOCK" ] && [ -S "$SSH_AUTH_SOCK" ]; then
    SSH_SOCK="$SSH_AUTH_SOCK"
fi

if [ -n "$SSH_SOCK" ]; then
    TARGET_SSH_SOCK="$SSH_SOCK"
    if command -v cygpath >/dev/null 2>&1; then
        TARGET_SSH_SOCK="$(cygpath -m "$SSH_SOCK")"
    fi
    EXTRA_DOCKER_ARGS+=(
        -v "${TARGET_SSH_SOCK}:/home/ubuntu/.1password/agent.sock"
        -e "SSH_AUTH_SOCK=/home/ubuntu/.1password/agent.sock"
    )
fi

# Resolve symlinked ~/.ssh/config to prevent broken symlinks inside container
if [ -L "${HOME}/.ssh/config" ] && [ -f "${HOME}/.ssh/config" ]; then
    RESOLVED_CONFIG="$(readlink -f "${HOME}/.ssh/config")"
    if command -v cygpath >/dev/null 2>&1; then
        RESOLVED_CONFIG="$(cygpath -m "$RESOLVED_CONFIG")"
    fi
    EXTRA_DOCKER_ARGS+=(-v "${RESOLVED_CONFIG}:/home/ubuntu/.ssh/config")
fi

# Execute Ansible Playbook
docker run --rm $FLAGS \
  -v "${TARGET_PWD}:/ansible" \
  -v "${TARGET_HOME}/.ssh:/home/ubuntu/.ssh" \
  "${EXTRA_DOCKER_ARGS[@]}" \
  -w /ansible \
  lpsouza/devops-tools \
  ansible-playbook "$@"


