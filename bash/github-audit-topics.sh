#!/bin/bash

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

GITHUB_OWNER=""

##
# Function to check required tools (gh and jq).
##
check_dependencies() {
    # Check gh cli
    if ! command -v gh >/dev/null 2>&1; then
        echo -e "${RED}Error: GitHub CLI (gh) is not installed. Please install it to run this script.${NC}"
        exit 1
    fi
    # Check jq
    if ! command -v jq >/dev/null 2>&1; then
        echo -e "${RED}Error: 'jq' is not installed. Please install it to run this script.${NC}"
        exit 1
    fi
    
    # Get the owner name for reference
    GITHUB_OWNER=$(gh api user --jq .login)
}

##
# Function to fetch and process topics for all repositories.
##
main_audit_loop() {
    echo -e "${BOLD}${BLUE}--- Starting Topics Audit for $GITHUB_OWNER ---${NC}"
    
    # 1. Fetch ALL repos and their data (pure JSON output).
    # This is the safest way to ensure all pages are fetched into a valid array.
    REPOS_JSON=$(gh api user/repos --paginate 2>/dev/null)

    # Check for empty or invalid output
    if [ -z "$REPOS_JSON" ] || ! echo "$REPOS_JSON" | jq -e '.[0].full_name' >/dev/null 2>&1; then
        echo -e "${RED}❌ Failed to fetch repositories or received invalid JSON.${NC}"
        echo -e "${YELLOW}Please verify your gh auth status and ensure your token has the 'repo' scope.${NC}"
        exit 1
    fi

    echo -e "${BOLD}Topics found across all repositories:${NC}"
    
    # 2. Process the ENTIRE array with a single jq call.
    echo "$REPOS_JSON" | jq -r --arg BLUE "${BLUE}" --arg BOLD "${BOLD}" --arg GREEN "${GREEN}" --arg YELLOW "${YELLOW}" --arg NC "${NC}" '
        .[] | 
        {
            # .topics is an array of strings directly from the API. Join it for output.
            name: .full_name, 
            topics_list: (.topics | join(", "))
        } |
        # Format the line. The shell loop handles colorizing "NO TOPICS" afterwards.
        "\(.name):\(.topics_list)"
    ' | 
    
    # 3. Sort the final output alphabetically by repository name.
    sort |
    
    # 4. Re-read the output in the shell to apply colors cleanly.
    while IFS=: read -r REPO_NAME TOPICS_LIST; do
        # Remove leading/trailing spaces from topics list
        TOPICS_LIST_CLEAN=$(echo "$TOPICS_LIST" | awk '{$1=$1};1') 

        if [ -z "$TOPICS_LIST_CLEAN" ]; then
            TOPICS_DISPLAY="${YELLOW}NO TOPICS ASSIGNED${NC}"
        else
            TOPICS_DISPLAY="${GREEN}$TOPICS_LIST${NC}"
        fi
        
        echo -e "${BLUE}${BOLD}${REPO_NAME}:${NC} $TOPICS_DISPLAY"
    done

    echo -e "\n${BOLD}${BLUE}--- Topics audit completed. ---${NC}"
}
# --- Script Execution Flow (Standardized) ---

check_dependencies
main_audit_loop
