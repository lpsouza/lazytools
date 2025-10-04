#!/bin/bash

NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

if ! command -v gh >/dev/null 2>&1; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed, but it's required to run this script.${NC}"
    exit 1
fi

GITHUB_OWNER=$(gh api user --jq .login)

REPOS_LIST=$(gh repo list "$GITHUB_OWNER" --limit 1000 --json nameWithOwner --jq '.[].nameWithOwner' | sort | tr '\n' ' ')

for FULL_REPO in $REPOS_LIST; do
    
    echo -e "${BLUE}${BOLD}>> Checking Webhooks in: $FULL_REPO${NC}"
    
    HOOKS=$(gh api "repos/$FULL_REPO/hooks" --jq '.[] | {id, url: .config.url}')
    
    if [ -z "$HOOKS" ]; then
        echo -e "  ${YELLOW}-> No webhook found in this repository.${NC}"
        continue
    fi
    
    echo "$HOOKS" | jq -r '. | "\(.id) \(.url)"' | while read -r HOOK_ID HOOK_URL; do
        
        LAST_DELIVERY=$(gh api "repos/$FULL_REPO/hooks/$HOOK_ID/deliveries" --paginate --jq '.[0] | {status_code, delivered_at}' 2>/dev/null)
        
        STATUS_CODE="null"
        DELIVERED_AT="null"
        
        if [ -z "$LAST_DELIVERY" ] || [[ "$(echo "$LAST_DELIVERY" | jq -r '.delivered_at')" == "null" ]]; then
            :
        else
            STATUS_CODE=$(echo "$LAST_DELIVERY" | jq -r '.status_code')
            DELIVERED_AT=$(echo "$LAST_DELIVERY" | jq -r '.delivered_at')
        fi
        
        if [[ "$STATUS_CODE" != 2* ]] || [[ "$STATUS_CODE" == "null" ]]; then
            echo -e "  ${RED}❌ FAILURE DETECTED:${NC} Hook ID $HOOK_ID"
            echo -e "     ${YELLOW}- URL:${NC} $HOOK_URL"
            echo -e "     ${YELLOW}- Last Status:${NC} $STATUS_CODE (at $DELIVERED_AT)"

            read -r -p $'     - Do you want to remove this failed webhook? (y/N): ' CONFIRM_DELETE </dev/tty

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
            echo -e "  ${GREEN}✅ Hook ID $HOOK_ID is OK${NC} (Status: $STATUS_CODE, Last: $DELIVERED_AT)"
        fi
        echo -e "${BOLD}${BLUE}--- Webhook audit completed. ---${NC}"
    done
done
