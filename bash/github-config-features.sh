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
REPO_DATA_JSON=""
ARCHIVED_STATE=""

# Variáveis de estado das features (serão preenchidas em fetch_repo_settings)
ISSUES_STATE=""
WIKI_STATE=""
PROJECTS_STATE=""
DISCUSSIONS_STATE=""


##
# Function to check required tools (gh cli and jq).
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
# Function to fetch all user's repositories (public and private).
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

##
# Function to select a repository interactively.
##
select_repository() {
    PS3="Select a repository to manage its settings: "
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
# Function to format boolean state for display
##
format_state() {
    local state="$1"
    if [ "$state" == "true" ]; then
        echo -e "${GREEN}Enabled (true)${NC}"
    else
        echo -e "${RED}Disabled (false)${NC}"
    fi
}

##
# Function to fetch current repository settings (Now includes archived status)
##
fetch_repo_settings() {
    # Necessário tornar as variáveis globais acessíveis
    declare -g ISSUES_STATE WIKI_STATE PROJECTS_STATE DISCUSSIONS_STATE ARCHIVED_STATE

    echo -e "${BLUE}Fetching current settings for $FULL_REPO...${NC}"
    REPO_DATA_JSON=$(gh api repos/$FULL_REPO)
    
    # Extract current feature states
    ISSUES_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_issues')
    WIKI_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_wiki')
    PROJECTS_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_projects')
    DISCUSSIONS_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_discussions')
    
    # Extract archived status
    ARCHIVED_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.archived')

    # Alert if archived
    # if [ "$ARCHIVED_STATE" == "true" ]; then
    #     echo -e "${YELLOW}⚠️ WARNING: This repository is ARCHIVED (Read-Only). Changes require temporary unarchiving.${NC}"
    # fi
}

##
# Function to display current settings (Add archived warning if necessary)
##
display_settings() {
    echo -e "\n${BOLD}Current Settings for $FULL_REPO:${NC}"
    echo -e "1. ${BOLD}Issues:${NC}      $(format_state $ISSUES_STATE)"
    echo -e "2. ${BOLD}Wiki:${NC}        $(format_state $WIKI_STATE)"
    echo -e "3. ${BOLD}Projects:${NC}    $(format_state $PROJECTS_STATE)"
    echo -e "4. ${BOLD}Discussions:${NC} $(format_state $DISCUSSIONS_STATE)"
    
    # Show archived status in the menu if it was fetched
    if [ "$ARCHIVED_STATE" == "true" ]; then
        echo -e "${RED}--- REPOSITORY IS CURRENTLY ARCHIVED (READ-ONLY) ---${NC}"
    fi
    
    echo -e "---"
    echo -e "5. ${BOLD}Back to Repository Selection${NC}"
    echo -e "0. ${BOLD}Exit Script${NC}"
}

##
# Function to toggle a setting (Now handles archiving/unarchiving).
##
toggle_setting() {
    local setting_name="$1"
    local current_state="$2"
    local setting_field="$3"
    
    # Use the ARCHIVED_STATE fetched previously
    local IS_ARCHIVED="$ARCHIVED_STATE"
    local NEEDS_REARCHIVE="false"

    NEW_STATE=""
    if [ "$current_state" == "true" ]; then
        NEW_STATE="false"
    else
        NEW_STATE="true"
    fi

    local action="Disabling"
    if [ "$NEW_STATE" == "true" ]; then
        action="Enabling"
    fi

    echo -e "${BLUE}$action $setting_name ($current_state -> $NEW_STATE)...${NC}"
    
    # 1. TEMPORARILY UNARCHIVE if necessary
    if [ "$IS_ARCHIVED" == "true" ]; then
        echo -e "${YELLOW}-> Temporarily unarchiving $FULL_REPO to apply changes...${NC}"
        UNARCHIVE_PAYLOAD=$(jq -n '{ "archived": false }')
        # Use <() to pass a file descriptor to gh api, making it safer
        gh api --method PATCH "repos/$FULL_REPO" --input <(echo "$UNARCHIVE_PAYLOAD") >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ Failed to unarchive. Aborting.${NC}"
            # Refetch to show the current (still archived) state
            fetch_repo_settings
            return 1
        fi
        NEEDS_REARCHIVE="true"
    fi

    # 2. APPLY THE FEATURE CHANGE
    PAYLOAD=$(jq -n --arg value "$NEW_STATE" "{ \"$setting_field\": (\$value | test(\"true\")) }")
    RESPONSE=$(echo "$PAYLOAD" | gh api --method PATCH "repos/$FULL_REPO" --input - 2>&1)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $setting_name updated successfully to $NEW_STATE!${NC}"
    else
        echo -e "${RED}❌ Failed to update $setting_name.${NC}"
        echo -e "${YELLOW}Response:${NC} $RESPONSE"
        # If application failed, we still try to re-archive
    fi

    # 3. RE-ARCHIVE if necessary
    if [ "$NEEDS_REARCHIVE" == "true" ]; then
        echo -e "${YELLOW}<- Re-archiving $FULL_REPO...${NC}"
        REARCHIVE_PAYLOAD=$(jq -n '{ "archived": true }')
        gh api --method PATCH "repos/$FULL_REPO" --input <(echo "$REARCHIVE_PAYLOAD") >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo -e "${RED}❌ WARNING: Failed to re-archive the repository! Check manually.${NC}"
        else
            echo -e "${GREEN}✅ Re-archived successfully.${NC}"
        fi
    fi

    # REMOVIDO: A chamada redundante 'fetch_repo_settings' foi removida daqui.
    # O loop principal (main_menu) fará a próxima busca de dados.
}

##
# Main Menu logic
##
main_menu() {
    while true; do
        fetch_repo_settings
        display_settings
        
        read -p $'\nEnter your choice (1-4 to toggle, 5 to change repo, 0 to exit): ' CHOICE
        
        case "$CHOICE" in
            1) # Issues
                toggle_setting "Issues" "$ISSUES_STATE" "has_issues"
                ;;
            2) # Wiki
                toggle_setting "Wiki" "$WIKI_STATE" "has_wiki"
                ;;
            3) # Projects
                toggle_setting "Projects" "$PROJECTS_STATE" "has_projects"
                ;;
            4) # Discussions
                toggle_setting "Discussions" "$DISCUSSIONS_STATE" "has_discussions"
                ;;
            5) # Back to Repo Select
                select_repository
                ;;
            0) # Exit
                echo -e "${BLUE}Exiting. Goodbye!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid choice: $CHOICE. Please choose a valid option.${NC}"
                ;;
        esac
    done
}

# --- Script Execution Flow (Standardized) ---

check_dependencies
fetch_repositories
select_repository
main_menu
