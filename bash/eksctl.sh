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

# Setup extra mounts for eksctl
EXTRA_DOCKER_ARGS=()

# Ensure ~/.aws and ~/.kube directories exist
[ -d "${HOME}/.aws" ] || mkdir -p "${HOME}/.aws"
[ -d "${HOME}/.kube" ] || mkdir -p "${HOME}/.kube"

EXTRA_DOCKER_ARGS+=(
  -v "${TARGET_HOME}/.aws:/home/ubuntu/.aws"
  -v "${TARGET_HOME}/.kube:/home/ubuntu/.kube"
)

# Mount ~/.ssh if present (for cluster keypair management)
if [ -d "${HOME}/.ssh" ]; then
    EXTRA_DOCKER_ARGS+=(-v "${TARGET_HOME}/.ssh:/home/ubuntu/.ssh")
fi

# Execute eksctl
docker run --rm $FLAGS \
  -v "${TARGET_PWD}:/eksctl" \
  "${EXTRA_DOCKER_ARGS[@]}" \
  -e HOME="/home/ubuntu" \
  -e AWS_PROFILE="${AWS_PROFILE:-default}" \
  -e AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-}}" \
  -e AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-}}" \
  -e AWS_SDK_LOAD_CONFIG="1" \
  -e AWS_SSO_SESSION="${AWS_SSO_SESSION:-}" \
  -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}" \
  -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}" \
  -e AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN:-}" \
  -w /eksctl \
  lpsouza/devops-tools \
  eksctl "$@"
