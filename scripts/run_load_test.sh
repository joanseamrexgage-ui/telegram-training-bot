#!/bin/bash
# ============================================================================
# Comprehensive Load Testing Script for telegram-training-bot
# ============================================================================
#
# This script orchestrates load testing with multiple scenarios and generates
# detailed performance reports.
#
# Usage:
#   chmod +x scripts/run_load_test.sh
#   ./scripts/run_load_test.sh [scenario] [users] [duration]
#
# Examples:
#   ./scripts/run_load_test.sh light 50 5m
#   ./scripts/run_load_test.sh medium 100 10m
#   ./scripts/run_load_test.sh stress 200 5m
#
# ============================================================================

set -e

# Default values
SCENARIO="${1:-medium}"
USERS="${2:-100}"
DURATION="${3:-5m}"
HOST="${BOT_HOST:-http://localhost:8000}"
REPORT_DIR="load_test_reports"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Create report directory
mkdir -p "$REPORT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/load_test_${SCENARIO}_${TIMESTAMP}.txt"

# Banner
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         LOAD TESTING - telegram-training-bot              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "Scenario:  $SCENARIO"
echo "Users:     $USERS"
echo "Duration:  $DURATION"
echo "Target:    $HOST"
echo "Started:   $(date)"
echo ""

# Check dependencies
if ! command -v locust &> /dev/null; then
    echo -e "${RED}❌ Locust not installed!${NC}"
    echo "Install with: pip install locust"
    exit 1
fi

if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}⚠️  pytest not available, skipping unit tests${NC}"
fi

# Check if bot is running
echo -e "${BLUE}🔍 Checking bot availability...${NC}"
if ! curl -f -s "$HOST/health" &> /dev/null && ! curl -f -s "http://localhost:8080/health" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Bot health endpoint not responding${NC}"
    echo "Make sure the bot is running before load testing"
fi

# ============================================================================
# SCENARIO DEFINITIONS
# ============================================================================

case "$SCENARIO" in
    light)
        echo -e "${GREEN}📊 Running LIGHT load test${NC}"
        echo "  → Simulates normal business day traffic"
        SPAWN_RATE=5
        USER_CLASS="TelegramBotUser"
        ;;

    medium)
        echo -e "${YELLOW}📊 Running MEDIUM load test${NC}"
        echo "  → Simulates busy period traffic"
        SPAWN_RATE=10
        USER_CLASS="TelegramBotUser"
        ;;

    stress)
        echo -e "${RED}📊 Running STRESS test${NC}"
        echo "  → Tests system limits and breaking points"
        SPAWN_RATE=20
        USER_CLASS="HeavyLoadUser"
        ;;

    realistic)
        echo -e "${BLUE}📊 Running REALISTIC mix test${NC}"
        echo "  → Mix of real user behaviors"
        SPAWN_RATE=10
        USER_CLASS="RealisticUserMix"
        ;;

    *)
        echo -e "${RED}❌ Unknown scenario: $SCENARIO${NC}"
        echo "Available scenarios: light, medium, stress, realistic"
        exit 1
        ;;
esac

# ============================================================================
# PRE-TEST VALIDATION
# ============================================================================

echo ""
echo -e "${BLUE}🔬 Running pre-test validation...${NC}"

# Check system resources
if command -v free &> /dev/null; then
    FREE_MEM=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    echo "  → Available memory: ${FREE_MEM}MB"

    if [ "$FREE_MEM" -lt 500 ]; then
        echo -e "${YELLOW}  ⚠️  Low memory warning${NC}"
    fi
fi

if command -v uptime &> /dev/null; then
    LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | cut -d',' -f1 | xargs)
    echo "  → System load: $LOAD_AVG"
fi

# ============================================================================
# RUN LOCUST LOAD TEST
# ============================================================================

echo ""
echo -e "${BLUE}🚀 Starting Locust load test...${NC}"
echo ""

# Run locust in headless mode
LOCUST_OUTPUT="$REPORT_DIR/locust_output_${TIMESTAMP}.log"

locust \
    -f tests/performance/locustfile.py \
    --host="$HOST" \
    --users="$USERS" \
    --spawn-rate="$SPAWN_RATE" \
    --run-time="$DURATION" \
    --headless \
    --only-summary \
    --html="$REPORT_DIR/locust_report_${TIMESTAMP}.html" \
    --csv="$REPORT_DIR/locust_stats_${TIMESTAMP}" \
    2>&1 | tee "$LOCUST_OUTPUT"

LOCUST_EXIT_CODE=$?

# ============================================================================
# ANALYZE RESULTS
# ============================================================================

echo ""
echo -e "${BLUE}📈 Analyzing results...${NC}"

# Extract key metrics from Locust output
if [ -f "$LOCUST_OUTPUT" ]; then
    TOTAL_REQUESTS=$(grep -o "Total requests.*" "$LOCUST_OUTPUT" | head -1 || echo "N/A")
    FAILURES=$(grep -o "Failures.*" "$LOCUST_OUTPUT" | head -1 || echo "N/A")
    RPS=$(grep -o "Requests/s.*" "$LOCUST_OUTPUT" | head -1 || echo "N/A")
    AVG_RESPONSE=$(grep -o "Average.*ms" "$LOCUST_OUTPUT" | head -1 || echo "N/A")

    echo "  → $TOTAL_REQUESTS"
    echo "  → $FAILURES"
    echo "  → $RPS"
    echo "  → $AVG_RESPONSE"
fi

# Parse CSV stats if available
if [ -f "$REPORT_DIR/locust_stats_${TIMESTAMP}_stats.csv" ]; then
    echo ""
    echo "Detailed statistics:"
    column -t -s, "$REPORT_DIR/locust_stats_${TIMESTAMP}_stats.csv" | head -10
fi

# ============================================================================
# RUN PERFORMANCE TESTS (pytest)
# ============================================================================

if command -v pytest &> /dev/null; then
    echo ""
    echo -e "${BLUE}🧪 Running performance unit tests...${NC}"

    pytest tests/performance/test_concurrent_load.py \
        -v \
        --tb=short \
        --durations=10 \
        2>&1 | tee "$REPORT_DIR/pytest_performance_${TIMESTAMP}.log"

    PYTEST_EXIT_CODE=$?
else
    PYTEST_EXIT_CODE=0
fi

# ============================================================================
# PERFORMANCE ASSERTIONS
# ============================================================================

echo ""
echo -e "${BLUE}🎯 Checking performance requirements...${NC}"

ASSERTIONS_PASSED=0
ASSERTIONS_FAILED=0

# Extract failure rate from CSV
if [ -f "$REPORT_DIR/locust_stats_${TIMESTAMP}_stats.csv" ]; then
    # Get failure percentage from aggregated stats
    FAILURE_RATE=$(tail -1 "$REPORT_DIR/locust_stats_${TIMESTAMP}_stats.csv" | cut -d',' -f4 || echo "0")

    # Remove % sign and compare
    FAILURE_NUM=$(echo "$FAILURE_RATE" | tr -d '%' | tr -d ' ')

    if [ -n "$FAILURE_NUM" ] && [ "$(echo "$FAILURE_NUM < 5" | bc 2>/dev/null || echo 1)" -eq 1 ]; then
        echo -e "${GREEN}✓ Failure rate < 5% ($FAILURE_RATE)${NC}"
        ((ASSERTIONS_PASSED++))
    else
        echo -e "${RED}✗ Failure rate >= 5% ($FAILURE_RATE)${NC}"
        ((ASSERTIONS_FAILED++))
    fi

    # Check average response time
    AVG_RT=$(tail -1 "$REPORT_DIR/locust_stats_${TIMESTAMP}_stats.csv" | cut -d',' -f6 || echo "0")
    if [ -n "$AVG_RT" ] && [ "$(echo "$AVG_RT < 2000" | bc 2>/dev/null || echo 1)" -eq 1 ]; then
        echo -e "${GREEN}✓ Average response time < 2s (${AVG_RT}ms)${NC}"
        ((ASSERTIONS_PASSED++))
    else
        echo -e "${RED}✗ Average response time >= 2s (${AVG_RT}ms)${NC}"
        ((ASSERTIONS_FAILED++))
    fi
fi

# ============================================================================
# GENERATE REPORT
# ============================================================================

echo ""
echo -e "${BLUE}📝 Generating comprehensive report...${NC}"

{
    echo "═══════════════════════════════════════════════════════════"
    echo "LOAD TEST REPORT - telegram-training-bot"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "Test Details:"
    echo "  Scenario:       $SCENARIO"
    echo "  Users:          $USERS"
    echo "  Spawn Rate:     $SPAWN_RATE"
    echo "  Duration:       $DURATION"
    echo "  Target Host:    $HOST"
    echo "  Start Time:     $(date)"
    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo "RESULTS SUMMARY"
    echo "───────────────────────────────────────────────────────────"
    echo ""

    if [ -f "$LOCUST_OUTPUT" ]; then
        grep -E "Total requests|Failures|Requests/s|Average|Median|95%|99%" "$LOCUST_OUTPUT" || echo "No summary available"
    fi

    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo "PERFORMANCE ASSERTIONS"
    echo "───────────────────────────────────────────────────────────"
    echo "  Passed: $ASSERTIONS_PASSED"
    echo "  Failed: $ASSERTIONS_FAILED"
    echo ""

    if [ $ASSERTIONS_FAILED -eq 0 ]; then
        echo "STATUS: ✅ ALL PERFORMANCE REQUIREMENTS MET"
    else
        echo "STATUS: ❌ PERFORMANCE REQUIREMENTS NOT MET"
    fi

    echo ""
    echo "───────────────────────────────────────────────────────────"
    echo "FILES GENERATED"
    echo "───────────────────────────────────────────────────────────"
    echo "  • HTML Report:   locust_report_${TIMESTAMP}.html"
    echo "  • CSV Stats:     locust_stats_${TIMESTAMP}_stats.csv"
    echo "  • Test Log:      locust_output_${TIMESTAMP}.log"
    if [ $PYTEST_EXIT_CODE -eq 0 ]; then
        echo "  • Pytest Log:    pytest_performance_${TIMESTAMP}.log"
    fi
    echo ""
    echo "═══════════════════════════════════════════════════════════"

} | tee "$REPORT_FILE"

# ============================================================================
# FINAL SUMMARY
# ============================================================================

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}LOAD TEST COMPLETED${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo "Completed: $(date)"
echo "Report:    $REPORT_FILE"
echo "HTML:      $REPORT_DIR/locust_report_${TIMESTAMP}.html"
echo ""

# Open HTML report if possible
if command -v xdg-open &> /dev/null; then
    echo "Opening HTML report..."
    xdg-open "$REPORT_DIR/locust_report_${TIMESTAMP}.html" &> /dev/null &
elif command -v open &> /dev/null; then
    echo "Opening HTML report..."
    open "$REPORT_DIR/locust_report_${TIMESTAMP}.html" &> /dev/null &
fi

# Exit code
if [ $LOCUST_EXIT_CODE -eq 0 ] && [ $ASSERTIONS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ Load test PASSED${NC}"
    exit 0
else
    echo -e "${RED}❌ Load test FAILED${NC}"
    exit 1
fi
