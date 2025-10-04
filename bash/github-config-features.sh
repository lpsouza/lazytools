#!/bin/bash

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

# Ensure GitHub CLI is installed
if ! command -v gh >/dev/null 2>&1; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed. Please install it to run this script.${NC}"
    exit 1
fi

OWNER_NAME=$(gh api user --jq .login)
FULL_REPO=""
REPO_DATA_JSON=""

##
# Function to fetch all user's repositories
##
fetch_repositories() {
    echo -e "${BLUE}Fetching repositories for $OWNER_NAME...${NC}"
    # Use user/repos endpoint to get all repos (private and public)
    REPOS_JSON=$(gh api user/repos --paginate --jq '[.[] | {name, full_name}]')
    REPOS=($(echo "$REPOS_JSON" | jq -r '.[].name'))
    
    if [ ${#REPOS[@]} -eq 0 ]; then
        echo -e "${RED}No repositories found for $OWNER_NAME.${NC}"
        exit 1
    fi
}

##
# Function to select a repository
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
# Function to fetch current repository settings
##
fetch_repo_settings() {
    echo -e "${BLUE}Fetching current settings for $FULL_REPO...${NC}"
    # Fetch repository details
    REPO_DATA_JSON=$(gh api repos/$FULL_REPO)
    
    # Extract current feature states
    ISSUES_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_issues')
    WIKI_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_wiki')
    PROJECTS_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_projects')
    DISCUSSIONS_STATE=$(echo "$REPO_DATA_JSON" | jq -r '.has_discussions')
}

##
# Function to display current settings
##
display_settings() {
    echo -e "\n${BOLD}Current Settings for $FULL_REPO:${NC}"
    echo -e "1. ${BOLD}Issues:${NC}      $(format_state $ISSUES_STATE)"
    echo -e "2. ${BOLD}Wiki:${NC}        $(format_state $WIKI_STATE)"
    echo -e "3. ${BOLD}Projects:${NC}    $(format_state $PROJECTS_STATE)"
    echo -e "4. ${BOLD}Discussions:${NC} $(format_state $DISCUSSIONS_STATE)"
    echo -e "---"
    echo -e "5. ${BOLD}Back to Repository Selection${NC}"
    echo -e "0. ${BOLD}Exit Script${NC}"
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
# Function to toggle a setting
##
toggle_setting() {
    local setting_name="$1"
    local current_state="$2"
    local setting_field="$3"

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
    
    # Construct the payload
    PAYLOAD=$(jq -n --arg value "$NEW_STATE" "{ \"$setting_field\": (\$value | test(\"true\")) }")
    
    # Call the API to update the setting
    RESPONSE=$(echo "$PAYLOAD" | gh api --method PATCH "repos/$FULL_REPO" --input - 2>&1)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $setting_name updated successfully to $NEW_STATE!${NC}"
        # Refetch settings to update the display
        fetch_repo_settings
    else
        echo -e "${RED}❌ Failed to update $setting_name.${NC}"
        echo -e "${YELLOW}Response:${NC} $RESPONSE"
    fi
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

# --- Script Execution Flow ---

fetch_repositories
select_repository
main_menu
