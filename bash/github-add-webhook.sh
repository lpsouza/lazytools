#!/bin/bash

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

OWNER_NAME=""
FULL_REPO=""
REPOS=()
WEBHOOK_URL=""
SECRET=""
EVENTS_ARRAY=()

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
    
    OWNER_NAME=$(gh api user --jq .login)
}

##
# Function to fetch all user's repositories.
##
fetch_repositories() {
    echo -e "${BLUE}Fetching repositories for $OWNER_NAME...${NC}"
    REPOS=($(gh repo list $OWNER_NAME --limit 100 --json name --jq '.[].name'))
    IFS=$'\n' REPOS=($(sort <<<"${REPOS[*]}"))
    unset IFS
    
    if [ ${#REPOS[@]} -eq 0 ]; then
        echo -e "${RED}No repositories found for $OWNER_NAME.${NC}"
        exit 1
    fi
}

# ... (Restante das funções select_repository, collect_webhook_data e create_webhook são mantidas)

##
# Function to select a repository interactively.
##
select_repository() {
    PS3="Select a repository to add a webhook: "
    select REPO in "${REPOS[@]}"; do
        if [ -n "$REPO" ]; then
            FULL_REPO="$OWNER_NAME/$REPO"
            break
        else
            echo -e "${RED}Invalid selection. Try again.${NC}"
        fi
    done
    echo -e "${BLUE}Repository selected:${NC} $FULL_REPO"
}

##
# Function to collect webhook data from the user.
##
collect_webhook_data() {
    # Get Webhook URL with basic validation
    while true; do
        read -p $'Enter the webhook URL: ' WEBHOOK_URL
        if [ -z "$WEBHOOK_URL" ]; then
            echo -e "${RED}Webhook URL is required.${NC}"
        elif [[ ! "$WEBHOOK_URL" =~ ^https?:// ]]; then
            echo -e "${RED}Invalid URL format. Must start with http:// or https://.${NC}"
        else
            break
        fi
    done

    read -p $'Enter a secret (optional, press Enter to skip): ' SECRET

    # Show all possible event options
    echo -e "\n${BOLD}Webhook Events (default: push):${NC}"
    echo -e "  Common: ${GREEN}push${NC}, ${GREEN}pull_request${NC}, ${GREEN}issues${NC}, ${GREEN}release${NC}"
    default_events="push"
    read -p "Enter events (comma separated, default: $default_events): " EVENTS
    if [ -z "$EVENTS" ]; then
        EVENTS=$default_events
    fi
    IFS=',' read -ra EVENTS_ARRAY <<< "$EVENTS"
}

##
# Function to confirm and create the webhook via API.
##
create_webhook() {
    echo -e "${BOLD}\nSummary:${NC}"
    echo -e "  Repository: ${GREEN}$FULL_REPO${NC}"
    echo -e "  Webhook URL: ${GREEN}$WEBHOOK_URL${NC}"
    echo -e "  Secret: ${GREEN}${SECRET:-<none>}${NC}"
    echo -e "  Events: ${GREEN}${EVENTS_ARRAY[*]}${NC}"
    read -p $'\nProceed to create the webhook? (y/N): ' CONFIRM
    if [[ ! "$CONFIRM" =~ ^[yY]$ ]]; then
        echo -e "${YELLOW}Aborted by user.${NC}"
        exit 0
    fi

    # Build CONFIG payload using jq
    CONFIG=$(jq -n \
        --arg url "$WEBHOOK_URL" \
        --arg secret "$SECRET" \
        --argjson events "$(printf '%s\n' "${EVENTS_ARRAY[@]}" | jq -R . | jq -s .)" \
        '{
            name: "web",
            active: true,
            events: $events,
            config: {
                url: $url,
                content_type: "json"
            }
        } | if $secret != "" then .config.secret = $secret else . end'
    )

    echo -e "${BLUE}Creating webhook...${NC}"
    RESPONSE=$(echo "$CONFIG" | gh api -X POST "repos/$FULL_REPO/hooks" --input - 2>&1)

    if echo "$RESPONSE" | grep -q 'id'; then
        # Print the created webhook ID for reference
        HOOK_ID=$(echo "$RESPONSE" | jq -r '.id')
        echo -e "${GREEN}✅ Webhook added successfully! ID: $HOOK_ID${NC}"
    else
        echo -e "${RED}❌ Failed to add webhook.${NC}"
        echo -e "${YELLOW}Response:${NC} $RESPONSE"
        exit 1
    fi
}


# --- Script Execution Flow (Standardized) ---

check_dependencies
fetch_repositories
select_repository
collect_webhook_data
create_webhook