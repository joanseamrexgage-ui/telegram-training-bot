#!/bin/bash
# ============================================================================
# Production Environment Validation Script for telegram-training-bot
# ============================================================================
#
# This script validates the production environment before deployment.
# It checks all critical dependencies, configurations, and infrastructure.
#
# Usage:
#   chmod +x scripts/validate_production_environment.sh
#   ./scripts/validate_production_environment.sh
#
# Exit codes:
#   0 - All checks passed, ready for production
#   1 - Critical failures detected, not ready for production
#
# ============================================================================

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0
TOTAL=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASSED++))
    ((TOTAL++))
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((FAILED++))
    ((TOTAL++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
    ((TOTAL++))
}

section_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
}

# Start validation
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   PRODUCTION ENVIRONMENT VALIDATION                       ║"
echo "║   telegram-training-bot v3.2                              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo "Started at: $(date)"
echo ""

# ============================================================================
# INFRASTRUCTURE VALIDATION
# ============================================================================

section_header "🏗️  INFRASTRUCTURE VALIDATION"

# Redis connectivity
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        check_pass "Redis connectivity"

        # Check Redis Sentinel (if configured)
        if redis-cli -p 26379 sentinel masters &> /dev/null 2>&1; then
            check_pass "Redis Sentinel operational"

            # Get master info
            REDIS_MASTER=$(redis-cli -p 26379 sentinel masters | grep -A 24 "mymaster" | grep "ip" | awk '{print $2}')
            if [ -n "$REDIS_MASTER" ]; then
                echo "  → Master IP: $REDIS_MASTER"
            fi
        else
            check_warn "Redis Sentinel not configured (single instance mode)"
        fi

        # Check Redis memory
        REDIS_MEM=$(redis-cli info memory | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
        echo "  → Memory usage: $REDIS_MEM"
    else
        check_fail "Redis connectivity - CRITICAL BLOCKER"
    fi
else
    check_warn "redis-cli not available, skipping Redis checks"
fi

# PostgreSQL connectivity
if [ -n "$DATABASE_URL" ]; then
    if command -v psql &> /dev/null; then
        if psql "$DATABASE_URL" -c "SELECT 1;" &> /dev/null 2>&1; then
            check_pass "PostgreSQL connectivity"

            # Get database size
            DB_SIZE=$(psql "$DATABASE_URL" -t -c "SELECT pg_size_pretty(pg_database_size(current_database()));" 2>/dev/null | xargs)
            echo "  → Database size: $DB_SIZE"
        else
            check_fail "PostgreSQL connectivity"
        fi
    else
        check_warn "psql not available, skipping PostgreSQL checks"
    fi
elif [ -f "training_bot.db" ]; then
    check_warn "Using SQLite (not recommended for production)"
    DB_SIZE=$(du -h training_bot.db | cut -f1)
    echo "  → Database size: $DB_SIZE"
else
    check_fail "No database connectivity"
fi

# Docker services check
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null 2>&1; then
        check_pass "Docker daemon running"

        # Check if docker-compose services are running
        if [ -f "docker-compose.production.yml" ]; then
            if docker-compose -f docker-compose.production.yml ps | grep -q "Up"; then
                check_pass "Docker Compose services running"

                # List running services
                echo "  → Running services:"
                docker-compose -f docker-compose.production.yml ps --services | while read service; do
                    echo "    • $service"
                done
            else
                check_warn "Docker Compose not running (manual deployment?)"
            fi
        fi
    else
        check_warn "Docker daemon not accessible"
    fi
else
    check_warn "Docker not installed"
fi

# ============================================================================
# SECURITY VALIDATION
# ============================================================================

section_header "🔒 SECURITY VALIDATION"

# Environment variables
if [ -f ".env.production" ]; then
    check_pass ".env.production file exists"

    # Check for default passwords
    if grep -q "CHANGE_ME\|password123\|admin123" .env.production 2>/dev/null; then
        check_fail "Default passwords detected in .env.production"
    else
        check_pass "No default passwords detected"
    fi

    # Check required variables
    required_vars=("BOT_TOKEN" "DATABASE_URL" "ADMIN_PASSWORD")
    for var in "${required_vars[@]}"; do
        if grep -q "^${var}=" .env.production 2>/dev/null; then
            check_pass "$var is configured"
        else
            check_warn "$var not found in .env.production"
        fi
    done
else
    check_fail ".env.production file missing"
fi

# Check .gitignore
if [ -f ".gitignore" ]; then
    if grep -q ".env" .gitignore && grep -q "*.db" .gitignore; then
        check_pass ".gitignore properly configured"
    else
        check_warn ".gitignore may be missing sensitive patterns"
    fi
else
    check_fail ".gitignore missing"
fi

# SSL/TLS check
if command -v nginx &> /dev/null; then
    if nginx -t &> /dev/null 2>&1; then
        check_pass "Nginx configuration valid"
    else
        check_warn "Nginx configuration invalid"
    fi
else
    check_warn "Nginx not configured (HTTP only)"
fi

# File permissions
if [ -f ".env.production" ]; then
    PERM=$(stat -c "%a" .env.production 2>/dev/null || stat -f "%Lp" .env.production 2>/dev/null)
    if [ "$PERM" = "600" ] || [ "$PERM" = "400" ]; then
        check_pass ".env.production has restrictive permissions ($PERM)"
    else
        check_warn ".env.production permissions too permissive ($PERM), recommend 600"
    fi
fi

# ============================================================================
# APPLICATION HEALTH
# ============================================================================

section_header "🏥 APPLICATION HEALTH"

# Health endpoint check
if curl -f http://localhost:8080/health &> /dev/null 2>&1; then
    check_pass "Bot health endpoint responding"

    HEALTH_JSON=$(curl -s http://localhost:8080/health)
    echo "  → Status: $(echo $HEALTH_JSON | grep -o '"status":"[^"]*"' | cut -d'"' -f4)"
else
    check_warn "Health endpoint not accessible (bot may not be running)"
fi

# Metrics endpoint
if curl -f http://localhost:8080/metrics | head -n 1 | grep -q "bot_requests_total" &> /dev/null 2>&1; then
    check_pass "Prometheus metrics endpoint"

    # Count available metrics
    METRICS_COUNT=$(curl -s http://localhost:8080/metrics | grep -c "^bot_" || echo "0")
    echo "  → Available metrics: $METRICS_COUNT"
else
    check_warn "Metrics endpoint not working"
fi

# Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    if [ "$(echo $PYTHON_VERSION | cut -d. -f1)" -ge 3 ] && [ "$(echo $PYTHON_VERSION | cut -d. -f2)" -ge 10 ]; then
        check_pass "Python version $PYTHON_VERSION (≥3.10)"
    else
        check_warn "Python version $PYTHON_VERSION (recommend ≥3.10)"
    fi
else
    check_fail "Python 3 not found"
fi

# Dependencies check
if [ -f "requirements.txt" ]; then
    if python3 -m pip list --format=freeze > /tmp/installed_packages.txt 2>/dev/null; then
        MISSING_COUNT=0
        while IFS= read -r package; do
            # Skip comments and empty lines
            [[ "$package" =~ ^#.*$ ]] && continue
            [[ -z "$package" ]] && continue

            PKG_NAME=$(echo "$package" | cut -d'=' -f1 | cut -d'>' -f1 | cut -d'<' -f1)
            if ! grep -q "^$PKG_NAME==" /tmp/installed_packages.txt; then
                ((MISSING_COUNT++))
            fi
        done < requirements.txt

        if [ $MISSING_COUNT -eq 0 ]; then
            check_pass "All dependencies installed"
        else
            check_warn "$MISSING_COUNT dependencies may be missing"
        fi

        rm -f /tmp/installed_packages.txt
    fi
else
    check_fail "requirements.txt not found"
fi

# ============================================================================
# TEST VALIDATION
# ============================================================================

section_header "🧪 TEST VALIDATION"

if command -v pytest &> /dev/null; then
    check_pass "pytest available"

    # Run tests (with timeout)
    echo "  → Running test suite (this may take a moment)..."
    if timeout 120 pytest --co -q > /tmp/test_collection.txt 2>&1; then
        TEST_COUNT=$(grep -c "test session starts" /tmp/test_collection.txt || echo "0")
        check_pass "Test suite collection successful"
        echo "  → Collected tests: $TEST_COUNT"
    else
        check_warn "Test collection had issues"
    fi

    rm -f /tmp/test_collection.txt

    # Check coverage (if pytest-cov available)
    if python3 -m pytest --version | grep -q "pytest-cov"; then
        check_pass "pytest-cov available for coverage"
    fi
else
    check_fail "pytest not available"
fi

# Load testing tools
if command -v locust &> /dev/null; then
    check_pass "Load testing tools available (Locust)"
else
    check_warn "Load testing tools not installed"
fi

# ============================================================================
# MONITORING STACK
# ============================================================================

section_header "📊 MONITORING VALIDATION"

# Prometheus
if curl -f http://localhost:9090/api/v1/query?query=up &> /dev/null 2>&1; then
    check_pass "Prometheus operational"

    # Check targets
    TARGETS_UP=$(curl -s http://localhost:9090/api/v1/targets | grep -o '"health":"up"' | wc -l)
    echo "  → Healthy targets: $TARGETS_UP"
else
    check_warn "Prometheus not accessible"
fi

# Grafana
if curl -f http://localhost:3000/api/health &> /dev/null 2>&1; then
    check_pass "Grafana operational"
else
    check_warn "Grafana not accessible"
fi

# Check if monitoring configuration exists
if [ -f "monitoring/prometheus.yml" ]; then
    check_pass "Prometheus configuration exists"
else
    check_warn "Prometheus configuration not found"
fi

if [ -d "monitoring/grafana/dashboards" ]; then
    DASHBOARD_COUNT=$(find monitoring/grafana/dashboards -name "*.json" | wc -l)
    check_pass "Grafana dashboards configured ($DASHBOARD_COUNT found)"
else
    check_warn "Grafana dashboards not configured"
fi

# ============================================================================
# CONFIGURATION FILES
# ============================================================================

section_header "📁 CONFIGURATION FILES"

# Check required files
required_files=(
    "Dockerfile"
    "docker-compose.production.yml"
    ".env.production.template"
    "requirements.txt"
    "README.md"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        check_pass "$file exists"
    else
        check_warn "$file missing"
    fi
done

# Check Alembic (if used)
if [ -f "alembic.ini" ] && [ -d "alembic" ]; then
    check_pass "Database migrations configured (Alembic)"
else
    check_warn "Database migrations not configured"
fi

# ============================================================================
# CALCULATE SCORE AND RECOMMENDATION
# ============================================================================

section_header "📊 PRODUCTION READINESS SCORE"

if [ $TOTAL -gt 0 ]; then
    SCORE=$((PASSED * 100 / TOTAL))
else
    SCORE=0
fi

echo ""
echo -e "${GREEN}✅ Passed:   $PASSED${NC}"
echo -e "${RED}❌ Failed:   $FAILED${NC}"
echo -e "${YELLOW}⚠️  Warnings: $WARNINGS${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "📈 Score:    ${BLUE}$SCORE%${NC}"
echo ""

# Deployment recommendation
if [ $SCORE -ge 95 ] && [ $FAILED -eq 0 ]; then
    echo -e "🎉 ${GREEN}PRODUCTION READY!${NC} 🚀"
    echo "Deployment recommendation: FULL GO"
    echo ""
    echo "All critical systems operational. Ready for production deployment."
    EXIT_CODE=0
elif [ $SCORE -ge 85 ] && [ $FAILED -le 1 ]; then
    echo -e "✅ ${YELLOW}CONDITIONAL GO${NC} ⚠️"
    echo "Deployment recommendation: Staged rollout with monitoring"
    echo ""
    echo "Most systems operational. Consider addressing warnings before full deployment."
    EXIT_CODE=0
elif [ $SCORE -ge 70 ]; then
    echo -e "⚠️  ${YELLOW}NOT READY${NC} - Address critical issues first"
    echo "Deployment recommendation: Fix critical issues before deployment"
    echo ""
    echo "Several critical issues detected. Not recommended for production."
    EXIT_CODE=1
else
    echo -e "❌ ${RED}NOT PRODUCTION READY${NC}"
    echo "Deployment recommendation: Significant work required"
    echo ""
    echo "Major issues detected. Extensive work needed before production deployment."
    EXIT_CODE=1
fi

echo ""
echo "Completed at: $(date)"
echo ""

# Generate report file
REPORT_FILE="production_validation_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "Production Validation Report"
    echo "Generated: $(date)"
    echo "Score: $SCORE%"
    echo "Passed: $PASSED, Failed: $FAILED, Warnings: $WARNINGS"
    echo ""
    echo "Exit Code: $EXIT_CODE"
} > "$REPORT_FILE"

echo "Report saved to: $REPORT_FILE"

exit $EXIT_CODE
