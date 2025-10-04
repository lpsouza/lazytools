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
    
    GITHUB_OWNER=$(gh api user --jq .login)
}

##
# Function to perform the audit and cleanup on a single webhook.
##
audit_and_cleanup_hook() {
    local FULL_REPO="$1"
    local HOOK_ID="$2"
    local HOOK_URL="$3"
    local HOOK_ACTIVE="$4"

    # Check if the hook is active, skip delivery check if inactive
    if [ "$HOOK_ACTIVE" == "false" ]; then
        echo -e "  ${YELLOW}⚠️ INACTIVE HOOK:${NC} Hook ID $HOOK_ID"
        echo -e "     ${YELLOW}- URL:${NC} $HOOK_URL"
        echo -e "     ${YELLOW}- Status:${NC} Inactive (Skipping delivery check)"
        return
    fi

    # Fetch last delivery attempt
    LAST_DELIVERY_JSON=$(gh api "repos/$FULL_REPO/hooks/$HOOK_ID/deliveries" --paginate --jq '.[0] | {status_code, delivered_at}' 2>/dev/null)
    
    STATUS_CODE=$(echo "$LAST_DELIVERY_JSON" | jq -r '.status_code // "N/A"')
    DELIVERED_AT=$(echo "$LAST_DELIVERY_JSON" | jq -r '.delivered_at // "N/A"')

    if [[ "$STATUS_CODE" != 2* ]] || [[ "$STATUS_CODE" == "N/A" ]]; then
        # If status is not 2xx (Success) or if no delivery was ever recorded
        echo -e "  ${RED}❌ FAILURE/UNKNOWN DETECTED:${NC} Hook ID $HOOK_ID"
        echo -e "     ${YELLOW}- URL:${NC} $HOOK_URL"
        echo -e "     ${YELLOW}- Last Status:${NC} $STATUS_CODE (at $DELIVERED_AT)"

        # Use /dev/tty to ensure input comes from the user terminal, not the pipe
        read -r -p $'     - Do you want to remove this failed/unknown webhook? (y/N): ' CONFIRM_DELETE </dev/tty

        if [[ "$CONFIRM_DELETE" =~ ^[yY]$ ]]; then
            echo -e "     ${BLUE}-> Trying to remove Webhook ID $HOOK_ID...${NC}"

            DELETE_OUTPUT=$(gh api --method DELETE "repos/$FULL_REPO/hooks/$HOOK_ID" 2>&1)

            if [[ $? -eq 0 ]]; then
                echo -e "     ${GREEN}✅ Webhook ID $HOOK_ID successfully removed.${NC}"
            else
                echo -e "     ${RED}❌ ERROR removing Webhook ID $HOOK_ID.${NC}"
                echo -e "        ${YELLOW}Error details:${NC} $DELETE_OUTPUT"
            fi
        else
            echo -e "     ${YELLOW}ℹ️ Removal cancelled. Webhook kept.${NC}"
        fi
    else
        echo -e "  ${GREEN}✅ Hook ID $HOOK_ID is OK${NC}"
        echo -e "     ${YELLOW}- URL:${NC} $HOOK_URL"
        echo -e "     ${YELLOW}- Last Status:${NC} $STATUS_CODE (at $DELIVERED_AT)"
    fi
}

##
# Main function to loop through all repositories.
##
main_audit_loop() {
    # Use gh repo list to get all repos
    REPOS_LIST=$(gh repo list "$GITHUB_OWNER" --limit 1000 --json nameWithOwner --jq '.[].nameWithOwner' | sort)

    if [ -z "$REPOS_LIST" ]; then
        echo -e "${RED}No repositories found for $GITHUB_OWNER.${NC}"
        exit 1
    fi

    echo -e "${BOLD}${BLUE}--- Starting Webhook Audit for $GITHUB_OWNER ---${NC}"

    # Loop through repos using the list
    echo "$REPOS_LIST" | while read -r FULL_REPO; do
        
        echo -e "\n${BLUE}${BOLD}>> Checking Webhooks in: $FULL_REPO${NC}"
        
        # Fetch hook details: id, url, and active status
        HOOKS=$(gh api "repos/$FULL_REPO/hooks" --jq '.[] | {id, url: .config.url, active}')
        
        if [ -z "$HOOKS" ]; then
            echo -e "  ${YELLOW}-> No webhooks found in this repository.${NC}"
            continue
        fi
        
        # Process each hook found and call the audit function
        echo "$HOOKS" | jq -r '. | "\(.id) \(.url) \(.active)"' | while read -r HOOK_ID HOOK_URL HOOK_ACTIVE; do
            audit_and_cleanup_hook "$FULL_REPO" "$HOOK_ID" "$HOOK_URL" "$HOOK_ACTIVE"
        done
    done

    echo -e "\n${BOLD}${BLUE}--- Webhook audit completed. ---${NC}"
}

# --- Script Execution Flow (Standardized) ---

check_dependencies
main_audit_loop