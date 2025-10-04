#!/bin/bash

# Colors for messaging
NC="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"

CSV_MODE=0
if [[ "$1" == "--csv" ]]; then
    CSV_MODE=1
fi

OWNER_NAME=$(gh api user --jq .login)
HEADERS=(Repo Issues Projects Wiki Pages Downloads Discussions Archived Disabled Private Visib Forking Template Releases Packages Deployments)


echo -e "${BLUE}${BOLD}Auditing repository features for $OWNER_NAME...${NC}"
REPOS_JSON=$(gh api "user/repos" --paginate)
REPOS_JSON=$(echo "$REPOS_JSON" | jq 'sort_by(.full_name)')
REPOS_COUNT=$(echo "$REPOS_JSON" | jq 'length')
if [ "$REPOS_COUNT" -eq 0 ]; then
    echo -e "${RED}No repositories found for $OWNER_NAME.${NC}"
    exit 1
fi

FEATURES=(
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

# Helper to safely get count from gh api, returns 0 on error or 404
safe_gh_count() {
    local endpoint="$1"
    local count=$(gh api $endpoint --jq 'length' 2>/dev/null)
    if [[ ! "$count" =~ ^[0-9]+$ ]]; then
        echo 0
    else
        echo $count
    fi
}

check_extra_features() {
    local repo="$1"

    local releases_count=$(safe_gh_count repos/$repo/releases)
    if [ "$releases_count" -gt 0 ]; then
        echo -n "enabled"
    else
        echo -n "disabled"
    fi
    echo -n ","

    local packages_count=$(safe_gh_count repos/$repo/packages)
    if [ "$packages_count" -gt 0 ]; then
        echo -n "enabled"
    else
        echo -n "disabled"
    fi
    echo -n ","

    local deployments_count=$(safe_gh_count repos/$repo/deployments)
    if [ "$deployments_count" -gt 0 ]; then
        echo -n "enabled"
    else
        echo -n "disabled"
    fi
}

if [ "$CSV_MODE" -eq 1 ]; then
    (IFS=','; echo "${HEADERS[*]}")
    # Print each repo's features as CSV
    for ((i=0; i<REPOS_COUNT; i++)); do
        REPO_NAME=$(echo "$REPOS_JSON" | jq -r ".[$i].full_name")
        LINE="$REPO_NAME"
        for FEATURE in "${FEATURES[@]}"; do
            VALUE=$(echo "$REPOS_JSON" | jq -r ".[$i].$FEATURE")
            if [ "$VALUE" == "true" ]; then
                LINE+=",enabled"
            elif [ "$VALUE" == "false" ]; then
                LINE+=",disabled"
            else
                LINE+=",$VALUE"
            fi
        done
        # Add extra features
        LINE+=","$(check_extra_features "$REPO_NAME")
        echo "$LINE"
    done
    exit 0
else
    MAX_REPO_LEN=$(echo "$REPOS_JSON" | jq -r '.[].full_name' | awk '{ print length }' | sort -nr | head -1)
    ((MAX_REPO_LEN=MAX_REPO_LEN<8?8:MAX_REPO_LEN))
    COL_WIDTHS=($MAX_REPO_LEN 8 10 6 6 10 12 9 9 8 7 8 10 9 9 12)

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


    for ((i=0; i<REPOS_COUNT; i++)); do
        IFS=',' read -r rel pkg dep <<< "$(check_extra_features "$REPO_NAME")"

        REPO_NAME=$(echo "$REPOS_JSON" | jq -r ".[$i].full_name")
        printf "│ %-${COL_WIDTHS[0]}s " "$REPO_NAME"
        for ((j=1; j<=${#FEATURES[@]}; j++)); do
            FEATURE=${FEATURES[$((j-1))]}
            VALUE=$(echo "$REPOS_JSON" | jq -r ".[$i].$FEATURE")
            if [ "$VALUE" == "true" ]; then
                printf "│ %*s${GREEN}✔${NC}%*s " $(( (COL_WIDTHS[$j]-1)/2 )) "" $(( COL_WIDTHS[$j]/2 )) ""
            elif [ "$VALUE" == "false" ]; then
                printf "│ %*s${RED}✘${NC}%*s " $(( (COL_WIDTHS[$j]-1)/2 )) "" $(( COL_WIDTHS[$j]/2 )) ""
            else
                printf "│ %-${COL_WIDTHS[$j]}s " "$VALUE"
            fi
        done

        for k in 0 1 2; do
            val=$(echo "$rel,$pkg,$dep" | cut -d, -f$((k+1)))
            idx=$(( ${#FEATURES[@]} + 1 + k ))
            if [ "$val" == "enabled" ]; then
                printf "│ %*s${GREEN}✔${NC}%*s " $(( (COL_WIDTHS[$idx]-1)/2 )) "" $(( COL_WIDTHS[$idx]/2 )) ""
            else
                printf "│ %*s${RED}✘${NC}%*s " $(( (COL_WIDTHS[$idx]-1)/2 )) "" $(( COL_WIDTHS[$idx]/2 )) ""
            fi
        done
        printf "│\n"
    done


    printf "${YELLOW}└"
    for ((j=0; j<${#HEADERS[@]}; j++)); do
        if [ $j -ne 0 ]; then printf "┴"; fi
        printf "%0.s─" $(seq 1 $((COL_WIDTHS[$j]+2)))
        done
    printf "┘${NC}\n"

    echo -e "\n${BOLD}Legend:${NC} ${GREEN}✔${NC}=Enabled, ${RED}✘${NC}=Disabled, public/private/visibility=repo type"

    echo -e "\n${BLUE}Audit complete.${NC}"
fi
