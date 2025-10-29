#!/bin/bash
# Environment Validation Script
# PHASE 0 TASK 0.3.2: Environment Validation
#
# Validates the environment before Redis Sentinel cluster deployment
# Checks Docker, ports, resources, and configuration requirements

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 ENVIRONMENT VALIDATION FOR REDIS DEPLOYMENT${NC}"
echo -e "${BLUE}=============================================${NC}"
echo ""
echo -e "${PURPLE}🎯 Validating environment for production Redis Sentinel cluster${NC}"
echo ""

# Validation counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

log_section() {
    echo -e "\n${BLUE}📈 $1${NC}"
    echo -e "${BLUE}$(printf '=%.0s' {1..40})${NC}"
}

# Function to check if port is available
check_port() {
    local port=$1
    local description=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        local process=$(lsof -Pi :$port -sTCP:LISTEN | tail -n +2 | awk '{print $1, $2}')
        check_fail "Port $port ($description) is occupied by: $process"
        return 1
    else
        check_pass "Port $port ($description) is available"
        return 0
    fi
}

# Docker and Docker Compose validation
log_section "DOCKER ENVIRONMENT"

echo -e "\n🐳 Checking Docker installation..."

# Check Docker installation
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
    check_pass "Docker installed (version $DOCKER_VERSION)"
    
    # Check Docker version (minimum 20.10.0)
    DOCKER_MAJOR=$(echo $DOCKER_VERSION | cut -d. -f1)
    DOCKER_MINOR=$(echo $DOCKER_VERSION | cut -d. -f2)
    
    if [ "$DOCKER_MAJOR" -gt 20 ] || ([ "$DOCKER_MAJOR" -eq 20 ] && [ "$DOCKER_MINOR" -ge 10 ]); then
        check_pass "Docker version meets requirements (>= 20.10.0)"
    else
        check_warn "Docker version $DOCKER_VERSION may be outdated (recommend >= 20.10.0)"
    fi
else
    check_fail "Docker not found - please install Docker"
fi

# Check Docker daemon
if docker info &> /dev/null 2>&1; then
    check_pass "Docker daemon is running"
    
    # Check Docker daemon configuration
    local docker_root=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo "/var/lib/docker")
    local available_space=$(df "$docker_root" | tail -1 | awk '{print $4}')
    local available_gb=$((available_space / 1024 / 1024))
    
    if [ "$available_gb" -ge 10 ]; then
        check_pass "Docker storage has sufficient space (${available_gb}GB available)"
    else
        check_warn "Docker storage space low (${available_gb}GB available, recommend >= 10GB)"
    fi
else
    check_fail "Docker daemon not running - please start Docker"
fi

# Check Docker Compose
echo -e "\n📦 Checking Docker Compose..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    check_pass "Docker Compose installed (version $COMPOSE_VERSION)"
    
    # Check Docker Compose version (minimum 1.29.0)
    COMPOSE_MAJOR=$(echo $COMPOSE_VERSION | cut -d. -f1)
    COMPOSE_MINOR=$(echo $COMPOSE_VERSION | cut -d. -f2)
    
    if [ "$COMPOSE_MAJOR" -gt 1 ] || ([ "$COMPOSE_MAJOR" -eq 1 ] && [ "$COMPOSE_MINOR" -ge 29 ]); then
        check_pass "Docker Compose version meets requirements (>= 1.29.0)"
    else
        check_warn "Docker Compose version $COMPOSE_VERSION may be outdated (recommend >= 1.29.0)"
    fi
else
    # Check for docker compose plugin
    if docker compose version &> /dev/null 2>&1; then
        COMPOSE_VERSION=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
        check_pass "Docker Compose (plugin) installed (version $COMPOSE_VERSION)"
    else
        check_fail "Docker Compose not found - please install Docker Compose"
    fi
fi

# Port availability validation
log_section "PORT AVAILABILITY"

echo -e "\n🔌 Checking required ports..."

# Required ports for Redis Sentinel cluster
REQUIRED_PORTS=(6379 6380 6381 26379 26380 26381)
PORT_DESCRIPTIONS=(
    "Redis Master"
    "Redis Slave 1" 
    "Redis Slave 2"
    "Sentinel 1"
    "Sentinel 2"
    "Sentinel 3"
)

PORT_CONFLICTS=0
for i in "${!REQUIRED_PORTS[@]}"; do
    if ! check_port "${REQUIRED_PORTS[$i]}" "${PORT_DESCRIPTIONS[$i]}"; then
        ((PORT_CONFLICTS++))
    fi
done

if [ $PORT_CONFLICTS -eq 0 ]; then
    check_pass "All required ports are available"
else
    check_fail "$PORT_CONFLICTS port conflicts detected - please resolve before deployment"
fi

# System resources validation
log_section "SYSTEM RESOURCES"

echo -e "\n💾 Checking system resources..."

# Memory check
local total_memory=$(free -m | awk 'NR==2{printf "%.0f", $2}')
local available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')

echo -e "${BLUE}  Total Memory: ${total_memory}MB${NC}"
echo -e "${BLUE}  Available Memory: ${available_memory}MB${NC}"

if [ "$available_memory" -ge 4096 ]; then
    check_pass "Sufficient memory available (${available_memory}MB >= 4GB)"
elif [ "$available_memory" -ge 2048 ]; then
    check_warn "Limited memory available (${available_memory}MB, recommend >= 4GB)"
else
    check_fail "Insufficient memory (${available_memory}MB, minimum 2GB required)"
fi

# Disk space check
local disk_usage=$(df . | awk 'NR==2 {print $4}')
local disk_available_gb=$((disk_usage / 1024 / 1024))

echo -e "${BLUE}  Available Disk Space: ${disk_available_gb}GB${NC}"

if [ "$disk_available_gb" -ge 10 ]; then
    check_pass "Sufficient disk space (${disk_available_gb}GB >= 10GB)"
elif [ "$disk_available_gb" -ge 2 ]; then
    check_warn "Limited disk space (${disk_available_gb}GB, recommend >= 10GB)"
else
    check_fail "Insufficient disk space (${disk_available_gb}GB, minimum 2GB required)"
fi

# CPU cores check
local cpu_cores=$(nproc)
echo -e "${BLUE}  CPU Cores: ${cpu_cores}${NC}"

if [ "$cpu_cores" -ge 4 ]; then
    check_pass "Sufficient CPU cores (${cpu_cores} >= 4)"
elif [ "$cpu_cores" -ge 2 ]; then
    check_warn "Limited CPU cores (${cpu_cores}, recommend >= 4)"
else
    check_fail "Insufficient CPU cores (${cpu_cores}, minimum 2 required)"
fi

# Network connectivity validation
log_section "NETWORK CONNECTIVITY"

echo -e "\n🌐 Testing network connectivity..."

# Test internet connectivity
if ping -c 1 -W 5 8.8.8.8 &> /dev/null; then
    check_pass "Internet connectivity available"
else
    check_warn "Internet connectivity test failed (required for Docker image pulls)"
fi

# Test DNS resolution
if nslookup docker.io &> /dev/null; then
    check_pass "DNS resolution working"
else
    check_warn "DNS resolution test failed"
fi

# Test Docker Hub connectivity
if curl -s --connect-timeout 5 https://hub.docker.com &> /dev/null; then
    check_pass "Docker Hub accessible"
else
    check_warn "Docker Hub connectivity test failed"
fi

# Environment variables validation
log_section "ENVIRONMENT VARIABLES"

echo -e "\n🔐 Checking environment configuration..."

# Check if .env files exist
if [ -f ".env" ]; then
    check_pass ".env file exists"
else
    check_warn ".env file not found (will use defaults)"
fi

if [ -f ".env.production" ]; then
    check_pass ".env.production file exists"
else
    check_warn ".env.production file not found"
fi

# Filesystem permissions validation
log_section "FILESYSTEM PERMISSIONS"

echo -e "\n📁 Checking filesystem permissions..."

# Check write permissions for Redis data directories
if [ -w "." ]; then
    check_pass "Current directory is writable"
else
    check_fail "Current directory is not writable - cannot create Redis data directories"
fi

# Test directory creation
if mkdir -p test-permissions-redis 2>/dev/null; then
    rmdir test-permissions-redis
    check_pass "Can create directories for Redis data"
else
    check_fail "Cannot create directories - check filesystem permissions"
fi

# Process conflict detection
log_section "PROCESS CONFLICTS"

echo -e "\n🔍 Checking for process conflicts..."

# Check for existing Redis processes
if pgrep redis-server &> /dev/null; then
    local redis_pids=$(pgrep redis-server | tr '\n' ' ')
    check_warn "Redis server processes already running (PIDs: $redis_pids)"
    echo -e "${YELLOW}  Consider stopping existing Redis instances before deployment${NC}"
else
    check_pass "No conflicting Redis processes found"
fi

# Check for existing Sentinel processes
if pgrep redis-sentinel &> /dev/null; then
    local sentinel_pids=$(pgrep redis-sentinel | tr '\n' ' ')
    check_warn "Redis Sentinel processes already running (PIDs: $sentinel_pids)"
else
    check_pass "No conflicting Sentinel processes found"
fi

# Security validation
log_section "SECURITY CHECKS"

echo -e "\n🔒 Checking security configuration..."

# Check for default passwords in configuration files
if find . -name "*.conf" -exec grep -l "redis_master_password_2025" {} \; 2>/dev/null | grep -q "."; then
    check_warn "Default Redis password found in config files - consider changing in production"
else
    check_pass "No default passwords found in config files"
fi

# Check current user permissions
if [ "$(id -u)" -eq 0 ]; then
    check_warn "Running as root - consider using non-root user for security"
else
    check_pass "Running as non-root user"
fi

# Final validation summary
log_section "VALIDATION SUMMARY"

TOTAL=$((PASSED + FAILED + WARNINGS))
if [ $TOTAL -gt 0 ]; then
    SCORE=$((PASSED * 100 / TOTAL))
else
    SCORE=0
fi

echo ""
echo -e "${BLUE}📈 VALIDATION RESULTS${NC}"
echo -e "${BLUE}==================${NC}"
echo -e "${GREEN}✅ Passed: $PASSED${NC}"
echo -e "${RED}❌ Failed: $FAILED${NC}"
echo -e "${YELLOW}⚠️  Warnings: $WARNINGS${NC}"
echo -e "${BLUE}📉 Score: $SCORE%${NC}"
echo ""

# Deployment recommendation
if [ $FAILED -eq 0 ] && [ $SCORE -ge 90 ]; then
    echo -e "${GREEN}🎉 ENVIRONMENT READY FOR DEPLOYMENT!${NC} 🚀"
    echo -e "${GREEN}All critical requirements satisfied${NC}"
    echo -e "${GREEN}Proceed with Redis Sentinel cluster deployment${NC}"
    
    echo -e "\n${BLUE}📋 Next Steps:${NC}"
    echo -e "${BLUE}1. Run: chmod +x scripts/setup_production_redis.sh${NC}"
    echo -e "${BLUE}2. Run: ./scripts/setup_production_redis.sh${NC}"
    echo -e "${BLUE}3. Start cluster: ./start_redis_cluster.sh${NC}"
    
    exit_code=0
elif [ $FAILED -eq 0 ] && [ $WARNINGS -le 3 ]; then
    echo -e "${YELLOW}✅ ENVIRONMENT ACCEPTABLE WITH WARNINGS${NC} ⚠️"
    echo -e "${YELLOW}Deployment possible but consider addressing warnings${NC}"
    
    exit_code=0
elif [ $FAILED -le 2 ]; then
    echo -e "${YELLOW}⚠️  ENVIRONMENT NEEDS ATTENTION${NC}"
    echo -e "${YELLOW}Address failed checks before deployment${NC}"
    
    exit_code=1
else
    echo -e "${RED}❌ ENVIRONMENT NOT READY${NC}"
    echo -e "${RED}Multiple critical issues detected${NC}"
    echo -e "${RED}Fix all failed checks before deployment${NC}"
    
    exit_code=1
fi

if [ $FAILED -gt 0 ]; then
    echo -e "\n${RED}🔴 CRITICAL ISSUES TO RESOLVE:${NC}"
    echo -e "${RED}• Address all failed checks above${NC}"
    echo -e "${RED}• Ensure all required ports are available${NC}"
    echo -e "${RED}• Verify system resources meet requirements${NC}"
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "\n${YELLOW}🟡 RECOMMENDATIONS:${NC}"
    echo -e "${YELLOW}• Review all warnings for optimal performance${NC}"
    echo -e "${YELLOW}• Consider upgrading system resources if warned${NC}"
    echo -e "${YELLOW}• Change default passwords in production${NC}"
fi

echo -e "\n${BLUE}🏁 ENVIRONMENT VALIDATION COMPLETE${NC}"
echo -e "${BLUE}====================================${NC}"

exit $exit_code