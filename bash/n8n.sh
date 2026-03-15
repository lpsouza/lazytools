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

# Execute n8n-cli
docker run $FLAGS \
  -e N8N_API_KEY="$N8N_API_KEY" \
  -e N8N_INSTANCE_URL="$N8N_INSTANCE_URL" \
  n8n-cli "$@"
