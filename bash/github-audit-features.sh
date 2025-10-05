#!/bin/bash

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

# Global Constants (Read-only array structure)
declare -r HEADERS=(Repo Issues Projects Wiki Pages Downloads Discussions Archived Disabled Private Visib Forking Template Releases Packages Deployments)
declare -r FEATURES=(
    has_issues
    has_projects
    has_wiki
    has_pages
    has_downloads
    has_discussions
    archived
    disabled
    private
    visibility
    allow_forking
    is_template
)

##
# Function to check required tools (gh, jq, awk).
##
check_dependencies() {
    for tool in gh jq awk; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            echo -e "${RED}Error: '$tool' is not installed. Please install it to run this script.${NC}"
            exit 1
        fi
    done
}

##
# Helper to safely get count from gh api, returns 0 on error or 404.
# Args: $1 = endpoint (e.g., "repos/user/repo/releases")
##
safe_gh_count() {
    local endpoint="$1"
    # Use gh api with silent error suppression
    local count=$(gh api "$endpoint" --jq 'length' 2>/dev/null)
    # Check if count is a number, if not, assume 0
    if [[ ! "$count" =~ ^[0-9]+$ ]]; then
        echo 0
    else
        echo "$count"
    fi
}

##
# Function to check non-boolean features (Releases, Packages, Deployments).
# Args: $1 = repository full name
# Returns: comma-separated string (e.g., "enabled,disabled,enabled")
##
check_extra_features() {
    local repo="$1"
    local results=()
    
    # 1. Releases: Check if any releases exist
    if [ $(safe_gh_count "repos/$repo/releases") -gt 0 ]; then
        results+=("enabled")
    else
        results+=("disabled")
    fi

    # 2. Packages: Check if any packages exist (simplified check)
    if [ $(safe_gh_count "repos/$repo/packages") -gt 0 ]; then
        results+=("enabled")
    else
        results+=("disabled")
    fi

    # 3. Deployments: Check if any deployments exist
    if [ $(safe_gh_count "repos/$repo/deployments") -gt 0 ]; then
        results+=("enabled")
    else
        results+=("disabled")
    fi
    
    # Return comma-separated string
    echo "${results[@]}" | tr ' ' ','
}

##
# Function to format and print the audit data in CSV format.
# Args: $1 = REPOS_JSON
##
export_csv_report() {
    local REPOS_JSON="$1"
    local REPOS_COUNT=$(echo "$REPOS_JSON" | jq 'length')
    
    (IFS=','; echo "${HEADERS[*]}")
    
    for ((i=0; i<REPOS_COUNT; i++)); do
        local REPO_NAME=$(echo "$REPOS_JSON" | jq -r ".[$i].full_name")
        local LINE="$REPO_NAME"
        
        for FEATURE in "${FEATURES[@]}"; do
            local VALUE=$(echo "$REPOS_JSON" | jq -r ".[$i].$FEATURE")
            if [ "$VALUE" == "true" ]; then
                LINE+=",enabled"
            elif [ "$VALUE" == "false" ]; then
                LINE+=",disabled"
            else
                LINE+=",$VALUE"
            fi
        done
        
        local EXTRA_FEATURES=$(check_extra_features "$REPO_NAME")
        LINE+=",${EXTRA_FEATURES}"
        echo "$LINE"
    done
}

##
# Function to format and print the audit data in a formatted table.
# Args: $1 = REPOS_JSON
##
print_formatted_table() {
    local REPOS_JSON="$1"
    local REPOS_COUNT=$(echo "$REPOS_JSON" | jq 'length')
    local OWNER_NAME=$(echo "$REPOS_JSON" | jq -r '.[0].owner.login')
    
    echo -e "${BLUE}${BOLD}Auditing repository features for $OWNER_NAME...${NC}"
    
    # Calculate Max Widths
    local MAX_REPO_LEN=$(echo "$REPOS_JSON" | jq -r '.[].full_name' | awk '{ print length }' | sort -nr | head -1)
    local COL_WIDTHS=()
    ((MAX_REPO_LEN=MAX_REPO_LEN<8?8:MAX_REPO_LEN))
    COL_WIDTHS=($MAX_REPO_LEN 8 10 6 6 10 12 9 9 8 7 8 10 9 9 12)

    # --- Print Header ---
    printf "${YELLOW}┌"
    for ((j=0; j<${#HEADERS[@]}; j++)); do
        if [ $j -ne 0 ]; then printf "┬"; fi
        printf "%0.s─" $(seq 1 $((COL_WIDTHS[$j]+2)))
    done
    printf "┐${NC}\n"

    printf "${BOLD}│ %-${COL_WIDTHS[0]}s " "${HEADERS[0]}"
    for ((j=1; j<${#HEADERS[@]}; j++)); do
        printf "│ %-${COL_WIDTHS[$j]}s " "${HEADERS[$j]}"
    done
    printf "│${NC}\n"

    printf "${YELLOW}├"
    for ((j=0; j<${#HEADERS[@]}; j++)); do
        if [ $j -ne 0 ]; then printf "┼"; fi
        printf "%0.s─" $(seq 1 $((COL_WIDTHS[$j]+2)))
    done
    printf "┤${NC}\n"

    # --- Print Data Rows ---
    for ((i=0; i<REPOS_COUNT; i++)); do
        local REPO_NAME=$(echo "$REPOS_JSON" | jq -r ".[$i].full_name")
        local EXTRA_FEATURES=$(check_extra_features "$REPO_NAME")
        
        IFS=',' read -r -a EXTRA_VALUES <<< "$EXTRA_FEATURES"
        
        printf "│ %-${COL_WIDTHS[0]}s " "$REPO_NAME"
        
        # Print main boolean features
        for ((j=1; j<=${#FEATURES[@]}; j++)); do
            local FEATURE=${FEATURES[$((j-1))]}
            local VALUE=$(echo "$REPOS_JSON" | jq -r ".[$i].$FEATURE")
            local COL_WIDTH=${COL_WIDTHS[$j]}
            
            if [ "$VALUE" == "true" ]; then
                printf "│ %*s${GREEN}✔${NC}%*s " $(( (COL_WIDTH-1)/2 )) "" $(( COL_WIDTH/2 )) ""
            elif [ "$VALUE" == "false" ]; then
                printf "│ %*s${RED}✘${NC}%*s " $(( (COL_WIDTH-1)/2 )) "" $(( COL_WIDTH/2 )) ""
            else
                printf "│ %-${COL_WIDTH}s " "$VALUE"
            fi
        done

        # Print extra features (Releases, Packages, Deployments)
        for k in 0 1 2; do
            local val="${EXTRA_VALUES[$k]}"
            local idx=$(( ${#FEATURES[@]} + 1 + k ))
            local COL_WIDTH=${COL_WIDTHS[$idx]}
            
            if [ "$val" == "enabled" ]; then
                printf "│ %*s${GREEN}✔${NC}%*s " $(( (COL_WIDTH-1)/2 )) "" $(( COL_WIDTH/2 )) ""
            else
                printf "│ %*s${RED}✘${NC}%*s " $(( (COL_WIDTH-1)/2 )) "" $(( COL_WIDTH/2 )) ""
            fi
        done
        printf "│\n"
    done

    # --- Print Footer ---
    printf "${YELLOW}└"
    for ((j=0; j<${#HEADERS[@]}; j++)); do
        if [ $j -ne 0 ]; then printf "┴"; fi
        printf "%0.s─" $(seq 1 $((COL_WIDTHS[$j]+2)))
    done
    printf "┘${NC}\n"

    echo -e "\n${BOLD}Legend:${NC} ${GREEN}✔${NC}=Enabled/Found, ${RED}✘${NC}=Disabled/Not Found, public/private/visibility=repo type"
    echo -e "\n${BLUE}Audit complete.${NC}"
}

##
# Main execution function.
##
main_execution() {
    local REPOS_JSON=""
    local REPOS_COUNT=0
    local OWNER_NAME=$(gh api user --jq .login)
    
    # Fetch all user repos and sort them by name for clean display
    REPOS_JSON=$(gh api "user/repos" --paginate | jq 'sort_by(.full_name)')
    REPOS_JSON=$(echo "$REPOS_JSON" | jq --arg OWNER "$OWNER_NAME" '[.[] | select(.owner.login == $OWNER)]')
    REPOS_COUNT=$(echo "$REPOS_JSON" | jq 'length')

    if [ "$REPOS_COUNT" -eq 0 ]; then
        echo -e "${RED}No repositories found for $OWNER_NAME.${NC}"
        exit 1
    fi

    # Check for CSV argument and call the appropriate function
    if [[ "$1" == "--csv" ]]; then
        export_csv_report "$REPOS_JSON"
    else
        print_formatted_table "$REPOS_JSON"
    fi
}

# --- Script Execution Flow (Standardized) ---

check_dependencies
main_execution "$1"