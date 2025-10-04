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

read -p $'Enter the webhook URL: ' WEBHOOK_URL
if [ -z "$WEBHOOK_URL" ]; then
    echo -e "${RED}Webhook URL is required. Exiting.${NC}"
    exit 1
fi

read -p $'Enter a secret (optional, press Enter to skip): ' SECRET


# Show all possible event options
echo -e "${BOLD}Available webhook events:${NC}"
echo -e "  ${GREEN}branch_protection_rule${NC}"
echo -e "  ${GREEN}check_run${NC}"
echo -e "  ${GREEN}check_suite${NC}"
echo -e "  ${GREEN}code_scanning_alert${NC}"
echo -e "  ${GREEN}commit_comment${NC}"
echo -e "  ${GREEN}create${NC}"
echo -e "  ${GREEN}delete${NC}"
echo -e "  ${GREEN}dependabot_alert${NC}"
echo -e "  ${GREEN}deploy_key${NC}"
echo -e "  ${GREEN}deployment${NC}"
echo -e "  ${GREEN}deployment_status${NC}"
echo -e "  ${GREEN}discussion${NC}"
echo -e "  ${GREEN}discussion_comment${NC}"
echo -e "  ${GREEN}fork${NC}"
echo -e "  ${GREEN}gollum${NC}"
echo -e "  ${GREEN}issues${NC}"
echo -e "  ${GREEN}issue_comment${NC}"
echo -e "  ${GREEN}label${NC}"
echo -e "  ${GREEN}member${NC}"
echo -e "  ${GREEN}membership${NC}"
echo -e "  ${GREEN}merge_group${NC}"
echo -e "  ${GREEN}milestone${NC}"
echo -e "  ${GREEN}organization${NC}"
echo -e "  ${GREEN}org_block${NC}"
echo -e "  ${GREEN}package${NC}"
echo -e "  ${GREEN}page_build${NC}"
echo -e "  ${GREEN}project${NC}"
echo -e "  ${GREEN}project_card${NC}"
echo -e "  ${GREEN}project_column${NC}"
echo -e "  ${GREEN}public${NC}"
echo -e "  ${GREEN}pull_request${NC}"
echo -e "  ${GREEN}pull_request_review${NC}"
echo -e "  ${GREEN}pull_request_review_comment${NC}"
echo -e "  ${GREEN}pull_request_target${NC}"
echo -e "  ${GREEN}push${NC} (default)"
echo -e "  ${GREEN}registry_package${NC}"
echo -e "  ${GREEN}release${NC}"
echo -e "  ${GREEN}repository${NC}"
echo -e "  ${GREEN}repository_dispatch${NC}"
echo -e "  ${GREEN}repository_import${NC}"
echo -e "  ${GREEN}repository_vulnerability_alert${NC}"
echo -e "  ${GREEN}secret_scanning_alert${NC}"
echo -e "  ${GREEN}secret_scanning_alert_location${NC}"
echo -e "  ${GREEN}security_advisory${NC}"
echo -e "  ${GREEN}sponsorship${NC}"
echo -e "  ${GREEN}star${NC}"
echo -e "  ${GREEN}status${NC}"
echo -e "  ${GREEN}team${NC}"
echo -e "  ${GREEN}team_add${NC}"
echo -e "  ${GREEN}watch${NC}"
echo -e "  ${GREEN}workflow_dispatch${NC}"
echo -e "  ${GREEN}workflow_job${NC}"
echo -e "  ${GREEN}workflow_run${NC}"
echo -e "  ${YELLOW}See GitHub docs for more details: https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads${NC}"
default_events="push"
read -p $'Enter events (comma separated, default: push): ' EVENTS
if [ -z "$EVENTS" ]; then
    EVENTS=$default_events
fi
IFS=',' read -ra EVENTS_ARRAY <<< "$EVENTS"

echo -e "${BOLD}\nSummary:${NC}"
echo -e "  Repository: ${GREEN}$FULL_REPO${NC}"
echo -e "  Webhook URL: ${GREEN}$WEBHOOK_URL${NC}"
echo -e "  Secret: ${GREEN}${SECRET:-<none>}${NC}"
echo -e "  Events: ${GREEN}${EVENTS}${NC}"
read -p $'\nProceed to create the webhook? (y/N): ' CONFIRM
if [[ ! "$CONFIRM" =~ ^[yY]$ ]]; then
    echo -e "${YELLOW}Aborted by user.${NC}"
    exit 0
fi

if [ -n "$SECRET" ]; then
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
                content_type: "json",
                secret: $secret
            }
        }'
    )
else
    CONFIG=$(jq -n \
        --arg url "$WEBHOOK_URL" \
        --argjson events "$(printf '%s\n' "${EVENTS_ARRAY[@]}" | jq -R . | jq -s .)" \
        '{
            name: "web",
            active: true,
            events: $events,
            config: {
                url: $url,
                content_type: "json"
            }
        }'
    )
fi

echo -e "${BLUE}Creating webhook...${NC}"
RESPONSE=$(echo "$CONFIG" | gh api -X POST repos/$FULL_REPO/hooks --input - 2>&1)

if echo "$RESPONSE" | grep -q 'id'; then
    #debug
    # echo "Response: $RESPONSE"
    echo -e "${GREEN}✅ Webhook added successfully!${NC}"
else
    echo -e "${RED}❌ Failed to add webhook.${NC}"
    echo -e "${YELLOW}Response:${NC} $RESPONSE"
    exit 1
fi
