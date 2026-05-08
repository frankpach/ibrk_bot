#!/bin/bash

# Material Requests Feature — Phase 5 Orchestrator (Claude CLI Skill)
# Invoke: /material-requests-executor [--summary|--dry-run|--group N|--issue N|--all]
# Invoked from: Claude CLI via skill system
# Generated: 2026-04-29

set -e

ISSUES_DIR=".windsurf/plans/issues"
README_FILE="$ISSUES_DIR/README.md"
MODULE_NAME="material_requests"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Default action: show summary
ACTION="summary"

# Parse arguments from Claude CLI
if [ -n "$1" ]; then
    case "$1" in
        --summary) ACTION="summary" ;;
        --dry-run) ACTION="dry-run" ;;
        --group) ACTION="group"; GROUP_NUM="$2" ;;
        --issue) ACTION="issue"; ISSUE_NUM="$2" ;;
        --all) ACTION="all" ;;
        *)
            echo -e "${RED}Unknown action: $1${NC}"
            echo ""
            echo "Usage from Claude CLI:"
            echo "  /material-requests-executor --summary  (default, show plan)"
            echo "  /material-requests-executor --dry-run  (show all commands)"
            echo "  /material-requests-executor --group 1  (execute group 1)"
            echo "  /material-requests-executor --issue 001 (execute single issue)"
            echo "  /material-requests-executor --all      (execute everything)"
            exit 1
            ;;
    esac
fi

# Define groups (respecting dependencies)
declare -A GROUPS=(
    [1]="001 008"
    [2]="002 003 004"
    [3]="005 006 009"
    [4]="007 010"
    [5]="011 012"
)

# ============================================================================
# ACTION: SUMMARY (Default)
# ============================================================================
if [ "$ACTION" = "summary" ]; then
    echo ""
    echo "=========================================="
    echo "Material Requests — Phase 5 Orchestrator"
    echo "=========================================="
    echo ""

    if [ -f "$README_FILE" ]; then
        echo -e "${GREEN}📋 Issue Summary:${NC}"
        echo ""
        cat "$README_FILE"
    else
        echo -e "${YELLOW}⚠️  README not found. Listing issues:${NC}"
        echo ""
        ls -1 "$ISSUES_DIR"/*.md | grep -v README | sort
    fi

    echo ""
    echo "=========================================="
    echo "Next Steps"
    echo "=========================================="
    echo ""
    echo "Step 1: Understand the groups and dependencies"
    echo ""
    echo "  Group 1 (no deps): 001 (Schema), 008 (Notifications)"
    echo "  Group 2 (need 001): 002 (CRUD), 003 (Approval), 004 (Tasks)"
    echo "  Group 3 (need 002,004,008): 005 (Single Resolve), 006 (Bulk), 009 (Rules)"
    echo "  Group 4 (need 005,006): 007 (Fulfillment), 010 (Events)"
    echo "  Group 5 (need 008,009,010): 011 (HITL), 012 (Dashboard)"
    echo ""
    echo "Step 2: Run preflight ONCE"
    echo ""
    echo -e "  ${BLUE}/05-phase-execution $MODULE_NAME 001 --preflight${NC}"
    echo "  (validates module scaffold, registers, setup infrastructure)"
    echo ""
    echo "Step 3: Execute issues in order"
    echo ""
    echo -e "  ${BLUE}/05-phase-execution $MODULE_NAME 001${NC}"
    echo -e "  ${BLUE}/clear${NC}"
    echo -e "  ${BLUE}/05-phase-execution $MODULE_NAME 008${NC}"
    echo -e "  ${BLUE}/clear${NC}"
    echo ""
    echo "  ... continue with Groups 2-5 ..."
    echo ""
    echo "Step 4: View dry-run plan"
    echo ""
    echo -e "  ${BLUE}/material-requests-executor --dry-run${NC}"
    echo ""
    echo "Step 5: Execute all automatically"
    echo ""
    echo -e "  ${BLUE}/material-requests-executor --all${NC}"
    echo "  (or use --group N for specific groups)"
    echo ""

# ============================================================================
# ACTION: DRY-RUN
# ============================================================================
elif [ "$ACTION" = "dry-run" ]; then
    echo ""
    echo "=========================================="
    echo "Dry-Run: Phase 5 Execution Plan"
    echo "=========================================="
    echo ""

    echo "Step 1: Module Preflight"
    echo -e "  ${BLUE}/05-phase-execution $MODULE_NAME 001 --preflight${NC}"
    echo "  Duration: ~30 min | Validates scaffold, registers module"
    echo ""

    for group in {1..5}; do
        echo "Step $((group+1)): Group $group"
        echo "  Issues: ${GROUPS[$group]}"
        echo ""

        for issue in ${GROUPS[$group]}; do
            echo "  Issue $issue:"
            echo -e "    ${BLUE}/05-phase-execution $MODULE_NAME $issue${NC}"
            echo "    ${BLUE}/clear${NC}  (clear context after each)"
            echo ""
        done
    done

    echo "Final Steps: Quality & Review"
    echo -e "  ${BLUE}/06-phase-quality $MODULE_NAME${NC}"
    echo "  ${BLUE}/clear${NC}"
    echo -e "  ${BLUE}/07-phase-review $MODULE_NAME${NC}"
    echo "  ${BLUE}/clear${NC}"
    echo ""
    echo "Documentation & Retrospective:"
    echo -e "  ${BLUE}/09-phase-documentation $MODULE_NAME${NC}"
    echo -e "  ${BLUE}/10-phase-retro${NC}"
    echo ""
    echo "=========================================="
    echo "Total Time Estimate"
    echo "=========================================="
    echo ""
    echo "  Preflight: 30 min"
    echo "  12 Issues: 2-4 hours each × 12 = 24-48 hours"
    echo "  Quality + Review: 2 hours"
    echo "  Documentation: 1-2 hours"
    echo "  ────────────────────────"
    echo "  Total: 30-54 hours"
    echo ""
    echo "  With 2 devs (parallel): ~7 days"
    echo "  With 1 dev (sequential): ~13 days"
    echo ""

# ============================================================================
# ACTION: EXECUTE SINGLE GROUP
# ============================================================================
elif [ "$ACTION" = "group" ]; then
    if [ -z "$GROUP_NUM" ]; then
        echo -e "${RED}Error: --group requires a number (1-5)${NC}"
        exit 1
    fi

    if [ -z "${GROUPS[$GROUP_NUM]}" ]; then
        echo -e "${RED}Error: Invalid group $GROUP_NUM (valid: 1-5)${NC}"
        exit 1
    fi

    echo ""
    echo "=========================================="
    echo "Executing Group $GROUP_NUM"
    echo "=========================================="
    echo ""
    echo "Issues: ${GROUPS[$GROUP_NUM]}"
    echo ""

    if [ "$GROUP_NUM" = "1" ]; then
        echo -e "${YELLOW}⚠️  Group 1 requires preflight (one-time setup)${NC}"
        echo ""
        echo -e "Step 1: ${BLUE}/05-phase-execution $MODULE_NAME 001 --preflight${NC}"
        echo "        (validates module, setup infrastructure)"
        echo ""
    fi

    echo "Step $((GROUP_NUM+1)): Execute issues"
    echo ""
    for issue in ${GROUPS[$GROUP_NUM]}; do
        echo "Issue $issue:"
        echo -e "  ${BLUE}/05-phase-execution $MODULE_NAME $issue${NC}"
        echo -e "  ${BLUE}/clear${NC}"
        echo ""
    done

    echo -e "${YELLOW}After this group, you can:${NC}"
    if [ "$GROUP_NUM" -lt 5 ]; then
        NEXT_GROUP=$((GROUP_NUM + 1))
        echo -e "  • ${BLUE}/material-requests-executor --group $NEXT_GROUP${NC}  (next group)"
    else
        echo -e "  • ${BLUE}/06-phase-quality $MODULE_NAME${NC}  (quality gates)"
    fi
    echo -e "  • ${BLUE}/material-requests-executor --dry-run${NC}  (view full plan)"
    echo ""

# ============================================================================
# ACTION: EXECUTE SINGLE ISSUE
# ============================================================================
elif [ "$ACTION" = "issue" ]; then
    if [ -z "$ISSUE_NUM" ]; then
        echo -e "${RED}Error: --issue requires an issue number${NC}"
        exit 1
    fi

    # Normalize issue number (pad to 3 digits)
    ISSUE_NUM=$(printf "%03d" "${ISSUE_NUM}")

    echo ""
    echo "=========================================="
    echo "Executing Issue $ISSUE_NUM"
    echo "=========================================="
    echo ""

    if [ ! -f "$ISSUES_DIR/$ISSUE_NUM-*.md" ]; then
        ISSUE_FILE=$(ls "$ISSUES_DIR/$ISSUE_NUM"-*.md 2>/dev/null | head -1)
        if [ -z "$ISSUE_FILE" ]; then
            echo -e "${RED}Error: Issue file not found: $ISSUES_DIR/$ISSUE_NUM-*.md${NC}"
            exit 1
        fi
    else
        ISSUE_FILE=$(ls "$ISSUES_DIR/$ISSUE_NUM"-*.md 2>/dev/null | head -1)
    fi

    echo "Issue File: $ISSUE_FILE"
    echo ""
    echo -e "${BLUE}/05-phase-execution $MODULE_NAME $ISSUE_NUM${NC}"
    echo ""
    echo "After issue completes:"
    echo -e "  ${BLUE}/clear${NC}  (clear context)"
    echo ""

# ============================================================================
# ACTION: EXECUTE ALL
# ============================================================================
elif [ "$ACTION" = "all" ]; then
    echo ""
    echo "=========================================="
    echo "Full Material Requests Execution"
    echo "=========================================="
    echo ""
    echo -e "${YELLOW}This will execute ALL phases:${NC}"
    echo ""
    echo "  ✓ Preflight (validate module)"
    echo "  ✓ Groups 1-5 (12 issues × 2-4h each)"
    echo "  ✓ Quality gates (comprehensive validation)"
    echo "  ✓ Code review (architecture + security)"
    echo ""
    echo -e "${YELLOW}Total time: ~30-54 hours${NC}"
    echo ""
    echo "Start with PREFLIGHT:"
    echo -e "  ${BLUE}/05-phase-execution $MODULE_NAME 001 --preflight${NC}"
    echo ""
    echo "Then execute issues in order:"
    echo ""

    for group in {1..5}; do
        for issue in ${GROUPS[$group]}; do
            echo -e "  ${BLUE}/05-phase-execution $MODULE_NAME $issue${NC}"
            echo -e "  ${BLUE}/clear${NC}"
        done
    done

    echo ""
    echo "After all issues, run quality gates:"
    echo -e "  ${BLUE}/06-phase-quality $MODULE_NAME${NC}"
    echo -e "  ${BLUE}/clear${NC}"
    echo ""
    echo "Then code review:"
    echo -e "  ${BLUE}/07-phase-review $MODULE_NAME${NC}"
    echo -e "  ${BLUE}/clear${NC}"
    echo ""
    echo "Finally, documentation and retrospective:"
    echo -e "  ${BLUE}/09-phase-documentation $MODULE_NAME${NC}"
    echo -e "  ${BLUE}/10-phase-retro${NC}"
    echo ""
    echo "Use /material-requests-executor --dry-run to review full plan"
    echo ""
fi

echo ""
