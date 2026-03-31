#!/usr/bin/env bash
# =============================================================================
# LENS Workbench — Generic PR creation helper
#
# PURPOSE:
#   Creates a PR between any two branches using GitHub API + PAT or manual URL.
#   Supports both GitHub and Azure DevOps.
#   Never relies on 'gh' CLI — always uses API via PAT or provides manual instructions.
#
# USAGE:
#   ./_bmad/lens-work/scripts/create-pr.sh -s my-feature -t main -T "My PR" -b "PR description"
#   ./_bmad/lens-work/scripts/create-pr.sh --source preplan-phase --target small-audience --title "[PHASE] PrePlan complete"
#
# OPTIONS:
#   -s, --source              Source branch name (required)
#   -t, --target              Target branch name (required)
#   -T, --title               PR title (required)
#   -b, --body                PR body/description (optional)
#   -r, --remote              Remote name (default: origin)
#   --url-only                Only print the PR creation URL, don't create PR
#   --timeout                 API call timeout in seconds (default: 30)
#   -h, --help                Show this help message
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PROFILE_FILE="${PROJECT_ROOT}/_bmad-output/lens-work/personal/profile.yaml"

# -- Colors -----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# -- Defaults ---------------------------------------------------------------
SOURCE_BRANCH=""
TARGET_BRANCH=""
TITLE=""
BODY=""
REMOTE="origin"
URL_ONLY=false
TIMEOUT=30

# -- Helper Functions -------------------------------------------------------

show_help() {
    sed -n '2,/^# =/p' "$0" | sed 's/^# //'
}

invoke_git() {
    local allow_failure=false
    local args=()

    for arg in "$@"; do
        if [[ "$arg" == "-allow-failure" ]]; then
            allow_failure=true
        else
            args+=("$arg")
        fi
    done

    if [[ "$allow_failure" == true ]]; then
        local rc=0
        git "${args[@]}" 2>&1 || rc=$?
        return $rc
    else
        git "${args[@]}"
    fi
}

get_remote_url() {
    local remote_name="$1"
    invoke_git remote get-url "$remote_name" | tr -d '[:space:]'
}

parse_remote_url() {
    local remote_url="$1"

    # Initialize variables
    local host="" org="" repo="" project="" platform="unknown"

    # GitHub HTTPS: https://github.com/org/repo(.git)
    if [[ "$remote_url" =~ ^https?://([^/]+)/([^/]+)/([^/]+?)(\.git)?$ ]]; then
        host="${BASH_REMATCH[1]}"
        org="${BASH_REMATCH[2]}"
        repo="${BASH_REMATCH[3]}"
        repo="${repo%.git}"
        if [[ "$host" =~ github\.com|github ]]; then
            platform="github"
        fi
        echo "$host|$org|$repo|$project|$platform"
        return
    fi

    # GitHub SSH: git@github.com:org/repo(.git)
    if [[ "$remote_url" =~ ^git@([^:]+):([^/]+)/([^/]+?)(\.git)?$ ]]; then
        host="${BASH_REMATCH[1]}"
        org="${BASH_REMATCH[2]}"
        repo="${BASH_REMATCH[3]}"
        repo="${repo%.git}"
        if [[ "$host" =~ github\.com|github ]]; then
            platform="github"
        fi
        echo "$host|$org|$repo|$project|$platform"
        return
    fi

    # Azure DevOps HTTPS: https://dev.azure.com/org/project/_git/repo
    if [[ "$remote_url" =~ ^https?://dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/]+?)(\.git)?$ ]]; then
        host="dev.azure.com"
        org="${BASH_REMATCH[1]}"
        project="${BASH_REMATCH[2]}"
        repo="${BASH_REMATCH[3]}"
        repo="${repo%.git}"
        platform="azdo"
        echo "$host|$org|$repo|$project|$platform"
        return
    fi

    # Azure DevOps SSH: git@ssh.dev.azure.com:v3/org/project/repo
    if [[ "$remote_url" =~ ^git@ssh\.dev\.azure\.com:v3/([^/]+)/([^/]+)/([^/]+?)(\.git)?$ ]]; then
        host="dev.azure.com"
        org="${BASH_REMATCH[1]}"
        project="${BASH_REMATCH[2]}"
        repo="${BASH_REMATCH[3]}"
        repo="${repo%.git}"
        platform="azdo"
        echo "$host|$org|$repo|$project|$platform"
        return
    fi

    # Unrecognized
    echo "$host|$org|$repo|$project|$platform"
}

get_pr_url() {
    local host="$1" org="$2" repo="$3" project="$4" platform="$5"
    local source="$6" target="$7"

    if [[ "$platform" == "github" && -n "$host" && -n "$org" && -n "$repo" ]]; then
        echo "https://$host/$org/$repo/compare/$target...$source"
    elif [[ "$platform" == "azdo" && -n "$org" && -n "$project" && -n "$repo" ]]; then
        echo "https://dev.azure.com/$org/$project/_git/$repo/pullrequestcreate?sourceRef=$source&targetRef=$target"
    else
        echo "MANUAL: Create PR from $source -> $target"
    fi
}

get_profile_pat() {
    local query_host="$1"

    if [[ ! -f "$PROFILE_FILE" ]]; then
        return
    fi

    local in_credentials=false
    local current_host=""
    local current_pat=""

    while IFS= read -r line; do
        line="${line#"${line%%[![:space:]]*}"}"  # ltrim
        line="${line%"${line##*[![:space:]]}"}"  # rtrim

        if [[ "$line" == "git_credentials:" ]]; then
            in_credentials=true
            continue
        fi

        if [[ "$in_credentials" == true ]]; then
            if [[ "$line" =~ ^-[[:space:]]*host:[[:space:]]*(.+)$ ]]; then
                current_host="${BASH_REMATCH[1]}"
                current_pat=""
            elif [[ "$line" =~ ^pat:[[:space:]]*(.+)$ ]]; then
                current_pat="${BASH_REMATCH[1]}"
                if [[ "$current_host" == "$query_host" ]]; then
                    echo "$current_pat"
                    return
                fi
            fi
        fi
    done < "$PROFILE_FILE"
}

invoke_github_pr_create() {
    local host="$1" org="$2" repo="$3" source="$4" target="$5" title="$6" body="$7" pat="${8:-}"
    local timeout="${9:-30}"

    # Attempt API creation if PAT is available
    if [[ -n "$pat" ]]; then
        local api_base
        if [[ "$host" == "github.com" ]]; then
            api_base="https://api.github.com"
        else
            api_base="https://$host/api/v3"
        fi

        local repo_name="$org/$repo"
        local payload
        payload=$(cat <<EOF
{
  "head": "$source",
  "base": "$target",
  "title": "$title",
  "body": "$body"
}
EOF
)

        local response
        local http_code
        response=$(curl -s -w "\n%{http_code}" \
            -X POST \
            "$api_base/repos/$repo_name/pulls" \
            -H "Authorization: token $pat" \
            -H "Content-Type: application/json" \
            -H "Accept: application/vnd.github+json" \
            -d "$payload" \
            --max-time "$timeout" 2>&1 || echo "error")

        http_code=$(echo "$response" | tail -n1)
        local json=$(echo "$response" | head -n-1)

        if [[ "$http_code" == "201" ]]; then
            local url=$(echo "$json" | grep -o '"html_url":"[^"]*' | cut -d'"' -f4)
            local number=$(echo "$json" | grep -o '"number":[0-9]*' | cut -d':' -f2)
            echo "SUCCESS|$url|$number"
            return 0
        elif [[ "$http_code" == "422" ]]; then
            echo "WARN|PR may already exist|"
            return 0
        else
            echo "ERROR|PR creation failed (HTTP $http_code)|"
            return 1
        fi
    fi

    # Fall back to manual URL
    echo "MANUAL|$(get_pr_url "$host" "$org" "$repo" "" "github" "$source" "$target")|"
}

# ============================================================================
# PARSE ARGUMENTS
# ============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--source) SOURCE_BRANCH="$2"; shift 2 ;;
        -t|--target) TARGET_BRANCH="$2"; shift 2 ;;
        -T|--title) TITLE="$2"; shift 2 ;;
        -b|--body) BODY="$2"; shift 2 ;;
        -r|--remote) REMOTE="$2"; shift 2 ;;
        --url-only) URL_ONLY=true; shift ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# Validate required arguments
if [[ -z "$SOURCE_BRANCH" || -z "$TARGET_BRANCH" || -z "$TITLE" ]]; then
    echo -e "${RED}Error: source, target, and title are required${RESET}"
    show_help
    exit 1
fi

# ============================================================================
# MAIN
# ============================================================================

echo -e "${CYAN}📋 LENS PR Creation${RESET}"
echo "  Source:  $SOURCE_BRANCH"
echo "  Target:  $TARGET_BRANCH"
echo "  Title:   $TITLE"

# Get remote URL and parse
REMOTE_URL=$(get_remote_url "$REMOTE")
IFS='|' read -r HOST ORG REPO PROJECT PLATFORM <<< "$(parse_remote_url "$REMOTE_URL")"

if [[ -z "$HOST" || "$PLATFORM" == "unknown" ]]; then
    echo -e "${RED}❌ Error: Unable to parse remote URL: $REMOTE_URL${RESET}"
    exit 1
fi

echo "  Platform: $PLATFORM"
echo ""

# If UrlOnly, just show the comparison URL
if [[ "$URL_ONLY" == true ]]; then
    URL=$(get_pr_url "$HOST" "$ORG" "$REPO" "$PROJECT" "$PLATFORM" "$SOURCE_BRANCH" "$TARGET_BRANCH")
    echo -e "${GREEN}🔗 PR URL:${RESET}"
    echo -e "   ${CYAN}$URL${RESET}"
    echo "$URL"
    exit 0
fi

# Try to get PAT from profile or environment
PAT=""
if [[ -n "$HOST" ]]; then
    PAT=$(get_profile_pat "$HOST")
    if [[ -z "$PAT" ]]; then
        PAT="${GITHUB_TOKEN:-}"
        if [[ -z "$PAT" ]]; then
            PAT="${GH_TOKEN:-}"
        fi
        if [[ -n "$PAT" ]]; then
            echo -e "  ${CYAN}[INFO]  PAT loaded from environment${RESET}"
        fi
    fi
fi

# Create PR
if [[ "$PLATFORM" == "github" ]]; then
    RESULT=$(invoke_github_pr_create "$HOST" "$ORG" "$REPO" "$SOURCE_BRANCH" "$TARGET_BRANCH" "$TITLE" "$BODY" "$PAT" "$TIMEOUT")
    IFS='|' read -r STATUS URL NUMBER <<< "$RESULT"

    case "$STATUS" in
        SUCCESS)
            echo -e "${GREEN}✅ PR created successfully${RESET}"
            echo -e "   URL: ${CYAN}$URL${RESET}"
            echo -e "   Number: #$NUMBER"
            echo ""
            echo "$URL"
            exit 0
            ;;
        WARN)
            echo -e "${YELLOW}⚠️  $URL${RESET}"
            MANUAL_URL=$(get_pr_url "$HOST" "$ORG" "$REPO" "$PROJECT" "$PLATFORM" "$SOURCE_BRANCH" "$TARGET_BRANCH")
            echo -e "   Try: ${CYAN}$MANUAL_URL${RESET}"
            echo ""
            exit 0
            ;;
        MANUAL)
            echo -e "${YELLOW}📝 Manual PR creation required:${RESET}"
            echo -e "   ${CYAN}$URL${RESET}"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Error: $URL${RESET}"
            exit 1
            ;;
    esac
else
    echo -e "${YELLOW}ℹ️  PR creation via API not yet implemented for $PLATFORM${RESET}"
    URL=$(get_pr_url "$HOST" "$ORG" "$REPO" "$PROJECT" "$PLATFORM" "$SOURCE_BRANCH" "$TARGET_BRANCH")
    echo -e "   Visit: ${CYAN}$URL${RESET}"
    exit 0
fi
