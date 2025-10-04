#!/bin/bash

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

OWNER_NAME=$(gh api user --jq .login)

echo -e "${BLUE}Fetching repositories for $OWNER_NAME...${NC}"
REPOS=($(gh repo list $OWNER_NAME --limit 100 --json name --jq '.[].name'))
if [ ${#REPOS[@]} -eq 0 ]; then
    echo -e "${RED}No repositories found for $OWNER_NAME.${NC}"
    exit 1
fi

PS3="Select a repository to manage webhooks: "
select REPO in "${REPOS[@]}"; do
    if [ -n "$REPO" ]; then
        FULL_REPO="$OWNER_NAME/$REPO"
        break
    else
        echo -e "${RED}Invalid selection. Try again.${NC}"
    fi
done

echo -e "${BLUE}Repository selected:${NC} $FULL_REPO"

HOOKS_JSON=$(gh api repos/$FULL_REPO/hooks 2>/dev/null)
HOOKS_COUNT=$(echo "$HOOKS_JSON" | jq 'length')
if [ "$HOOKS_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No webhooks found in this repository.${NC}"
    exit 0
fi


# Prepare arrays for ID, URL, and EVENTS
HOOK_IDS=($(echo "$HOOKS_JSON" | jq -r '.[].id'))
HOOK_URLS=($(echo "$HOOKS_JSON" | jq -r '.[].config.url'))
HOOK_EVENTS=($(echo "$HOOKS_JSON" | jq -c '.[].events'))


PS3="${YELLOW}Select a webhook to delete (or 0 to cancel): ${NC}"
echo -e "${BOLD}Webhooks:${NC}"
for i in "${!HOOK_IDS[@]}"; do
    EVENTS_DISPLAY=$(echo ${HOOK_EVENTS[$i]} | jq -r '. | join(", ")')
    echo "$((i+1)). ID: ${HOOK_IDS[$i]} | URL: ${HOOK_URLS[$i]} | EVENTS: $EVENTS_DISPLAY"
done
echo "0. Cancel"

while true; do
    read -p "Enter your choice: " CHOICE
    if [[ "$CHOICE" == "0" ]]; then
        echo -e "${YELLOW}Operation cancelled by user.${NC}"
        exit 0
    elif [[ "$CHOICE" =~ ^[0-9]+$ ]] && [ "$CHOICE" -ge 1 ] && [ "$CHOICE" -le ${#HOOK_IDS[@]} ]; then
        IDX=$((CHOICE-1))
        HOOK_ID=${HOOK_IDS[$IDX]}
        HOOK_URL=${HOOK_URLS[$IDX]}
    HOOK_EVENTS_SELECTED=$(echo ${HOOK_EVENTS[$IDX]} | jq -r '. | join(", ")')
    break
    else
        echo -e "${RED}Invalid selection. Try again.${NC}"
    fi
done

echo -e "${BOLD}\nSummary:${NC}"
echo -e "  Repository: ${GREEN}$FULL_REPO${NC}"
echo -e "  Webhook ID: ${GREEN}$HOOK_ID${NC}"
echo -e "  Webhook URL: ${GREEN}$HOOK_URL${NC}"
echo -e "  Events: ${GREEN}${HOOK_EVENTS_SELECTED}${NC}"
read -p $'\nProceed to delete this webhook? (y/N): ' CONFIRM
if [[ ! "$CONFIRM" =~ ^[yY]$ ]]; then
    echo -e "${YELLOW}Aborted by user.${NC}"
    exit 0
fi

echo -e "${BLUE}Deleting webhook ID $HOOK_ID...${NC}"
DELETE_OUTPUT=$(gh api --method DELETE repos/$FULL_REPO/hooks/$HOOK_ID 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Webhook deleted successfully!${NC}"
else
    echo -e "${RED}❌ Failed to delete webhook.${NC}"
    echo -e "${YELLOW}Response:${NC} $DELETE_OUTPUT"
    exit 1
fi
