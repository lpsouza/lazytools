#!/bin/bash

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
BOLD="\033[1m"

BIN_DIR="${HOME}/.local/bin"
PROJECT_ROOT="$(dirname "$(readlink -f "$0")")"
BASH_DIR="${PROJECT_ROOT}/bash"
PYTHON_DIR="${PROJECT_ROOT}/python"

##
# Function to list available scripts in bash/ and python/ directories.
##
list_scripts() {
    local count=0

    echo -e "${BLUE}${BOLD}Available scripts in lazytools:${NC}"
    echo -e "----------------------------------------"

    if [ -d "$BASH_DIR" ]; then
        echo -e "${CYAN}${BOLD}Bash Scripts (${BASH_DIR}):${NC}"
        for script in "${BASH_DIR}"/*.sh; do
            if [ -f "$script" ]; then
                local filename=$(basename "$script")
                local script_name="${filename%.sh}"
                echo -e "  - ${YELLOW}${script_name}${NC}"
                ((count++))
            fi
        done
    fi

    if [ -d "$PYTHON_DIR" ]; then
        echo -e "\n${CYAN}${BOLD}Python Scripts (${PYTHON_DIR}):${NC}"
        for script in "${PYTHON_DIR}"/*.py; do
            if [ -f "$script" ]; then
                local filename=$(basename "$script")
                local script_name="${filename%.py}"
                echo -e "  - ${YELLOW}${script_name}${NC}"
                ((count++))
            fi
        done
    fi

    if [ "$count" -eq 0 ]; then
        echo -e "${RED}No scripts found in ${BASH_DIR} or ${PYTHON_DIR}.${NC}"
    else
        echo -e "----------------------------------------"
        echo -e "Usage: ${BOLD}./install-script.sh <script_name>${NC}"
    fi
}

##
# Function to install a specific script.
##
install_script() {
    local script_name="$1"
    local source_script=""

    # Check bash directory
    if [ -f "${BASH_DIR}/${script_name}.sh" ]; then
        source_script="${BASH_DIR}/${script_name}.sh"
    elif [ -f "${PYTHON_DIR}/${script_name}.py" ]; then
        source_script="${PYTHON_DIR}/${script_name}.py"
    elif [ -f "${BASH_DIR}/${script_name}" ]; then
        source_script="${BASH_DIR}/${script_name}"
    elif [ -f "${PYTHON_DIR}/${script_name}" ]; then
        source_script="${PYTHON_DIR}/${script_name}"
    fi

    # Check if source exists
    if [ -z "$source_script" ] || [ ! -f "$source_script" ]; then
        echo -e "${RED}Error: Script '${script_name}' not found in ${BASH_DIR} or ${PYTHON_DIR}.${NC}"
        echo -e "Run without arguments to see available scripts."
        exit 1
    fi

    local target_link="${BIN_DIR}/${script_name}"

    # Ensure BIN_DIR exists
    if [ ! -d "$BIN_DIR" ]; then
        echo -e "${YELLOW}Creating ${BIN_DIR} directory...${NC}"
        mkdir -p "$BIN_DIR"
    fi

    echo -e "${BLUE}Installing ${YELLOW}${script_name}${BLUE}...${NC}"

    # Ensure source is executable
    chmod +x "$source_script"

    # Handle existing target
    if [ -L "$target_link" ]; then
        rm "$target_link"
    elif [ -f "$target_link" ]; then
        echo -e "${RED}Error: A file already exists at ${target_link} and is NOT a symbolic link.${NC}"
        echo -e "Please remove it manually if you wish to proceed."
        exit 1
    fi

    # Create symlink
    ln -s "$source_script" "$target_link"

    echo -e "${GREEN}Success! Link created:${NC}"
    echo -e "  ${YELLOW}${target_link}${NC} -> ${source_script}"
    
    # Path warning
    if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
        echo -e "\n${YELLOW}Warning: ${BIN_DIR} is not in your PATH.${NC}"
        echo -e "Add 'export PATH=\"\$HOME/.local/bin:\$PATH\"' to your shell config."
    fi
}

# Main logic
if [ -z "$1" ]; then
    list_scripts
else
    install_script "$1"
fi
