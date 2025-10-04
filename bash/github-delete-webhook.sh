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
HOOK_DATA=()
HOOK_ID=""
HOOK_URL=""
HOOK_EVENTS_SELECTED=""

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
    
    if [ ${#REPOS[@]} -eq 0 ]; then
        echo -e "${RED}No repositories found for $OWNER_NAME.${NC}"
        exit 1
    fi
}

# ... (Restante das funções select_repository, fetch_and_prepare_hooks, select_hook_to_delete e delete_webhook são mantidas)

##
# Function to select a repository interactively.
##
select_repository() {
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
}

##
# Function to fetch and prepare webhook data for display.
##
fetch_and_prepare_hooks() {
    HOOKS_JSON=$(gh api "repos/$FULL_REPO/hooks" 2>/dev/null)
    HOOKS_COUNT=$(echo "$HOOKS_JSON" | jq 'length')
    
    if [ "$HOOKS_COUNT" -eq 0 ]; then
        echo -e "${YELLOW}No webhooks found in this repository.${NC}"
        exit 0
    fi

    HOOK_DATA=()
    # AQUI ESTÁ A CORREÇÃO: Usar (.events | join(",")) para converter o array em string
    while IFS=$'\t' read -r id url events active; do
        # Format events nicely for display (already done in the jq output)
        EVENTS_DISPLAY=$events
        # Store as a single string, separated by ';'
        HOOK_DATA+=("$id;$url;$EVENTS_DISPLAY;$active")
    done < <(echo "$HOOKS_JSON" | jq -r '.[] | [.id, .config.url, (.events | join(","))] | @tsv')

    # A linha que usa @tsv não precisa do .active, pois ele não está no objeto de .events, vamos refazer o pipe para ser mais limpo:
    # Versão mais robusta, focando em extrair os campos:
    HOOK_DATA=()
    while IFS=$'\t' read -r id url events active; do
        HOOK_DATA+=("$id;$url;$events;$active")
    done < <(echo "$HOOKS_JSON" | jq -r '.[] | [.id, .config.url, (.events | join(", ")), .active] | @tsv')

    # Se a chamada acima falhar novamente, tentamos a versão sem o `join` no script, pois ela já está sendo feita no display loop! 
    # Mas, teoricamente, o problema é o array. Vamos manter a última tentativa corrigida.
    
    # Tentativa final de correção que deve funcionar:
    HOOKS_OUTPUT=$(echo "$HOOKS_JSON" | jq -r '.[] | [.id, .config.url, (.events | join(", ")), .active] | @tsv')
    
    if [ -z "$HOOKS_OUTPUT" ]; then
        echo -e "${YELLOW}No webhooks found or jq parsing failed.${NC}"
        exit 0
    fi
    
    HOOK_DATA=()
    while IFS=$'\t' read -r id url events active; do
        HOOK_DATA+=("$id;$url;$events;$active")
    done <<< "$HOOKS_OUTPUT"

    if [ ${#HOOK_DATA[@]} -eq 0 ]; then
        echo -e "${YELLOW}No webhooks found after parsing.${NC}"
        exit 0
    fi
}

##
# Function to display hooks and get user selection for deletion. (DEVE VIR ANTES DE delete_webhook)
##
select_hook_to_delete() {
    PS3="${YELLOW}Select a webhook to delete (or 0 to cancel): ${NC}"
    echo -e "${BOLD}Webhooks:${NC}"
    
    for i in "${!HOOK_DATA[@]}"; do
        IFS=';' read -r TEMP_ID TEMP_URL TEMP_EVENTS TEMP_ACTIVE <<< "${HOOK_DATA[$i]}"
        ACTIVE_COLOR=$(if [ "$TEMP_ACTIVE" == "true" ]; then echo -e "${GREEN}ACTIVE${NC}"; else echo -e "${RED}INACTIVE${NC}"; fi)
        echo "$((i+1)). ID: ${TEMP_ID} | STATUS: $ACTIVE_COLOR | URL: ${TEMP_URL} | EVENTS: $TEMP_EVENTS"
    done
    echo "0. Cancel"

    while true; do
        read -p "Enter your choice: " CHOICE
        if [[ "$CHOICE" == "0" ]]; then
            echo -e "${YELLOW}Operation cancelled by user.${NC}"
            exit 0
        elif [[ "$CHOICE" =~ ^[0-9]+$ ]] && [ "$CHOICE" -ge 1 ] && [ "$CHOICE" -le ${#HOOK_DATA[@]} ]; then
            IDX=$((CHOICE-1))
            # Extract data from the selected string into global variables
            IFS=';' read -r HOOK_ID HOOK_URL HOOK_EVENTS_SELECTED HOOK_ACTIVE <<< "${HOOK_DATA[$IDX]}"
            break
        else
            echo -e "${RED}Invalid selection. Try again.${NC}"
        fi
    done
}

##
# Function to confirm and execute the deletion via API.
##
delete_webhook() {
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
    DELETE_OUTPUT=$(gh api --method DELETE "repos/$FULL_REPO/hooks/$HOOK_ID" 2>&1)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Webhook deleted successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to delete webhook.${NC}"
        echo -e "${YELLOW}Response:${NC} $DELETE_OUTPUT"
        exit 1
    fi
}

# --- Script Execution Flow (Standardized) ---

check_dependencies
fetch_repositories
select_repository
fetch_and_prepare_hooks
select_hook_to_delete
delete_webhook
