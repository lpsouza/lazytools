#!/bin/bash

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

# Initialize script
check_dependencies
load_env

# Execute Terraform
docker run --rm $FLAGS \
  -v "${PWD}:/terraform" \
  -v "${HOME}:/home/ubuntu" \
  -w /terraform \
  -u ubuntu \
  lpsouza/devops-tools \
  terraform "$@"
