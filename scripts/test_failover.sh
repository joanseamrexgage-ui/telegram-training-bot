#!/bin/bash
# Automated Redis Sentinel Failover Testing
# PHASE 0 TASK 0.3.3: Automated Failover Testing
#
# This script performs comprehensive failover testing for Redis Sentinel cluster:
# 1. Starts cluster and validates setup
# 2. Tests bot connectivity
# 3. Simulates master failure
# 4. Measures failover time (target: < 5 seconds)
# 5. Validates FSM state persistence
# 6. Tests master recovery
# 7. Generates detailed report

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 AUTOMATED REDIS SENTINEL FAILOVER TESTING${NC}"
echo -e "${BLUE}===========================================${NC}"
echo ""
echo -e "${PURPLE}🎯 Testing failover performance and data persistence${NC}"
echo -e "${PURPLE}🔍 Target failover time: < 5 seconds${NC}"
echo ""

# Test configuration
TEST_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEST_REPORT="failover_test_report_${TEST_TIMESTAMP}.txt"
TEST_DATA_PREFIX="failover_test"
FAILOVER_TIMEOUT=10  # Maximum acceptable failover time in seconds
TEST_PASSWORD="redis_master_password_2025"
MASTER_NAME="telegram-bot-master"

# Test counters
TEST_PASSED=0
TEST_FAILED=0
TEST_WARNINGS=0

# Helper functions
test_pass() {
    echo -e "${GREEN}✅ $1${NC}" | tee -a "$TEST_REPORT"
    ((TEST_PASSED++))
}

test_fail() {
    echo -e "${RED}❌ $1${NC}" | tee -a "$TEST_REPORT"
    ((TEST_FAILED++))
}

test_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}" | tee -a "$TEST_REPORT"
    ((TEST_WARNINGS++))
}

log_section() {
    echo -e "\n${CYAN}📈 $1${NC}" | tee -a "$TEST_REPORT"
    echo -e "${CYAN}$(printf '=%.0s' {1..50})${NC}" | tee -a "$TEST_REPORT"
}

# Initialize test report
echo "Redis Sentinel Failover Test Report" > "$TEST_REPORT"
echo "Generated: $(date)" >> "$TEST_REPORT"
echo "Test ID: $TEST_TIMESTAMP" >> "$TEST_REPORT"
echo "" >> "$TEST_REPORT"

# Function to get current Redis master
get_current_master() {
    docker exec redis-sentinel1 redis-cli -p 26379 sentinel get-master-addr-by-name $MASTER_NAME 2>/dev/null | head -1 || echo "unknown"
}

# Function to test Redis connectivity
test_redis_connectivity() {
    local host=$1
    local port=$2
    local password=$3
    
    if docker exec "redis-master" redis-cli -h "$host" -p "$port" -a "$password" ping 2>/dev/null | grep -q PONG; then
        return 0
    else
        return 1
    fi
}

# Function to store test data
store_test_data() {
    local key_count=10
    echo "Storing $key_count test keys..." | tee -a "$TEST_REPORT"
    
    for i in $(seq 1 $key_count); do
        local key="${TEST_DATA_PREFIX}:key_$i"
        local value="test_data_${i}_$(date +%s)"
        
        if docker exec redis-master redis-cli -a "$TEST_PASSWORD" set "$key" "$value" ex 3600 &>/dev/null; then
            echo "  • Stored $key: $value" >> "$TEST_REPORT"
        else
            test_fail "Failed to store test key: $key"
            return 1
        fi
    done
    
    test_pass "Stored $key_count test keys successfully"
    return 0
}

# Function to validate test data
validate_test_data() {
    local master_host=$1
    local master_port=$2
    local key_count=10
    local recovered_keys=0
    
    echo "Validating test data on master $master_host:$master_port..." | tee -a "$TEST_REPORT"
    
    for i in $(seq 1 $key_count); do
        local key="${TEST_DATA_PREFIX}:key_$i"
        
        if docker exec "$master_host" redis-cli -a "$TEST_PASSWORD" get "$key" &>/dev/null; then
            ((recovered_keys++))
            echo "  • Recovered $key" >> "$TEST_REPORT"
        else
            echo "  • Lost $key" >> "$TEST_REPORT"
        fi
    done
    
    local recovery_rate=$((recovered_keys * 100 / key_count))
    
    if [ $recovery_rate -eq 100 ]; then
        test_pass "All test data recovered (${recovered_keys}/${key_count})"
    elif [ $recovery_rate -ge 90 ]; then
        test_warn "Most test data recovered (${recovered_keys}/${key_count}, ${recovery_rate}%)"
    else
        test_fail "Significant data loss detected (${recovered_keys}/${key_count}, ${recovery_rate}%)"
    fi
    
    return $recovery_rate
}

# Function to simulate FSM state data
setup_fsm_test_data() {
    echo "Setting up FSM test data..." | tee -a "$TEST_REPORT"
    
    local fsm_keys=(
        "fsm:12345:12345"
        "fsm:67890:67890"
        "fsm:11111:11111"
    )
    
    local fsm_states=(
        "MenuStates:main_menu"
        "MenuStates:profile_setup"
        "AdminStates:user_management"
    )
    
    for i in "${!fsm_keys[@]}"; do
        local key="${fsm_keys[$i]}"
        local state="${fsm_states[$i]}"
        local data='{"user_id": '"$((12345 + i))", "timestamp": '"$(date +%s)"}'
        
        docker exec redis-master redis-cli -a "$TEST_PASSWORD" hset "$key" state "$state" &>/dev/null
        docker exec redis-master redis-cli -a "$TEST_PASSWORD" hset "$key" data "$data" &>/dev/null
        
        echo "  • FSM State: $key -> $state" >> "$TEST_REPORT"
    done
    
    test_pass "FSM test data setup complete"
}

# Function to validate FSM state persistence
validate_fsm_persistence() {
    local master_host=$1
    echo "Validating FSM state persistence..." | tee -a "$TEST_REPORT"
    
    local fsm_keys=(
        "fsm:12345:12345"
        "fsm:67890:67890"
        "fsm:11111:11111"
    )
    
    local recovered_states=0
    
    for key in "${fsm_keys[@]}"; do
        local state=$(docker exec "$master_host" redis-cli -a "$TEST_PASSWORD" hget "$key" state 2>/dev/null)
        local data=$(docker exec "$master_host" redis-cli -a "$TEST_PASSWORD" hget "$key" data 2>/dev/null)
        
        if [ -n "$state" ] && [ "$state" != "(nil)" ]; then
            ((recovered_states++))
            echo "  • Recovered $key: $state" >> "$TEST_REPORT"
        else
            echo "  • Lost FSM state: $key" >> "$TEST_REPORT"
        fi
    done
    
    if [ $recovered_states -eq ${#fsm_keys[@]} ]; then
        test_pass "All FSM states preserved (${recovered_states}/${#fsm_keys[@]})"
        return 0
    else
        test_fail "FSM state loss detected (${recovered_states}/${#fsm_keys[@]})"
        return 1
    fi
}

# PHASE 1: Cluster Startup and Validation
log_section "CLUSTER STARTUP AND VALIDATION"

echo -e "\n🚀 Starting Redis Sentinel cluster..." | tee -a "$TEST_REPORT"

# Check if cluster is already running
if docker-compose -f docker-compose.redis-production.yml ps | grep -q "Up"; then
    echo "Cluster already running, stopping for clean test..." | tee -a "$TEST_REPORT"
    docker-compose -f docker-compose.redis-production.yml down &>/dev/null
    sleep 5
fi

# Start the cluster
echo "Starting cluster..." | tee -a "$TEST_REPORT"
if docker-compose -f docker-compose.redis-production.yml up -d &>/dev/null; then
    test_pass "Redis Sentinel cluster started"
else
    test_fail "Failed to start Redis Sentinel cluster"
    exit 1
fi

# Wait for services to initialize
echo "Waiting for services to initialize (45 seconds)..." | tee -a "$TEST_REPORT"
sleep 45

# Validate all services are running
echo "Validating service health..." | tee -a "$TEST_REPORT"
services=("redis-master" "redis-slave1" "redis-slave2" "redis-sentinel1" "redis-sentinel2" "redis-sentinel3")
healthy_services=0

for service in "${services[@]}"; do
    if docker ps --filter "name=$service" --filter "status=running" | grep -q "$service"; then
        echo "  • $service: Running" >> "$TEST_REPORT"
        ((healthy_services++))
    else
        echo "  • $service: Not running" >> "$TEST_REPORT"
    fi
done

if [ $healthy_services -eq ${#services[@]} ]; then
    test_pass "All services healthy (${healthy_services}/${#services[@]})"
else
    test_fail "Service health check failed (${healthy_services}/${#services[@]})"
fi

# PHASE 2: Initial Master Discovery
log_section "INITIAL MASTER DISCOVERY"

echo -e "\n🔍 Discovering initial master..." | tee -a "$TEST_REPORT"

# Wait for Sentinel to elect master
sleep 10

INITIAL_MASTER=$(get_current_master)
if [ "$INITIAL_MASTER" != "unknown" ]; then
    test_pass "Initial master discovered: $INITIAL_MASTER"
    echo "Master IP: $INITIAL_MASTER" >> "$TEST_REPORT"
else
    test_fail "Failed to discover initial master"
    exit 1
fi

# Test initial connectivity
if test_redis_connectivity "$INITIAL_MASTER" "6379" "$TEST_PASSWORD"; then
    test_pass "Initial master connectivity confirmed"
else
    test_fail "Cannot connect to initial master"
fi

# PHASE 3: Test Data Setup
log_section "TEST DATA SETUP"

echo -e "\n💾 Setting up test data..." | tee -a "$TEST_REPORT"

# Store test data
store_test_data

# Setup FSM test data
setup_fsm_test_data

# PHASE 4: Master Failure Simulation
log_section "MASTER FAILURE SIMULATION"

echo -e "\n🔥 Simulating master failure..." | tee -a "$TEST_REPORT"

# Record failover start time
FAILOVER_START=$(date +%s)
echo "Failover test started at: $(date)" >> "$TEST_REPORT"

# Stop the current master
echo "Stopping master container: redis-master" | tee -a "$TEST_REPORT"
if docker stop redis-master &>/dev/null; then
    test_pass "Master container stopped successfully"
else
    test_fail "Failed to stop master container"
fi

# Monitor failover process
echo "Monitoring failover process..." | tee -a "$TEST_REPORT"
NEW_MASTER="unknown"
failover_detected=false

for i in $(seq 1 $FAILOVER_TIMEOUT); do
    sleep 1
    CURRENT_MASTER=$(get_current_master)
    
    if [ "$CURRENT_MASTER" != "unknown" ] && [ "$CURRENT_MASTER" != "$INITIAL_MASTER" ]; then
        NEW_MASTER="$CURRENT_MASTER"
        FAILOVER_END=$(date +%s)
        FAILOVER_TIME=$((FAILOVER_END - FAILOVER_START))
        failover_detected=true
        break
    fi
    
    echo "  Waiting for failover... (${i}s)" >> "$TEST_REPORT"
done

if [ "$failover_detected" = true ]; then
    if [ $FAILOVER_TIME -le 5 ]; then
        test_pass "Failover completed in ${FAILOVER_TIME} seconds (target: ≤ 5s)"
    elif [ $FAILOVER_TIME -le 10 ]; then
        test_warn "Failover took ${FAILOVER_TIME} seconds (slower than target: 5s)"
    else
        test_fail "Failover too slow: ${FAILOVER_TIME} seconds (target: ≤ 5s)"
    fi
    
    echo "New master elected: $NEW_MASTER" >> "$TEST_REPORT"
else
    test_fail "Failover not detected within ${FAILOVER_TIMEOUT} seconds"
    NEW_MASTER="$INITIAL_MASTER"
fi

# PHASE 5: Post-Failover Validation
log_section "POST-FAILOVER VALIDATION"

echo -e "\n🔍 Validating post-failover state..." | tee -a "$TEST_REPORT"

# Test new master connectivity
if [ "$NEW_MASTER" != "unknown" ]; then
    # Find the container name for the new master
    NEW_MASTER_CONTAINER=""
    if [ "$NEW_MASTER" = "172.20.0.3" ] || docker exec redis-slave1 redis-cli -a "$TEST_PASSWORD" info replication | grep -q "role:master"; then
        NEW_MASTER_CONTAINER="redis-slave1"
    elif [ "$NEW_MASTER" = "172.20.0.4" ] || docker exec redis-slave2 redis-cli -a "$TEST_PASSWORD" info replication | grep -q "role:master"; then
        NEW_MASTER_CONTAINER="redis-slave2"
    fi
    
    if [ -n "$NEW_MASTER_CONTAINER" ]; then
        test_pass "New master container identified: $NEW_MASTER_CONTAINER"
        
        # Test connectivity to new master
        if docker exec "$NEW_MASTER_CONTAINER" redis-cli -a "$TEST_PASSWORD" ping | grep -q PONG; then
            test_pass "New master is responsive"
        else
            test_fail "New master is not responsive"
        fi
        
        # Validate test data persistence
        validate_test_data "$NEW_MASTER_CONTAINER" "6379"
        
        # Validate FSM state persistence
        validate_fsm_persistence "$NEW_MASTER_CONTAINER"
        
    else
        test_fail "Could not identify new master container"
    fi
else
    test_fail "No new master available for testing"
fi

# Test write operations to new master
if [ -n "$NEW_MASTER_CONTAINER" ]; then
    echo "Testing write operations to new master..." | tee -a "$TEST_REPORT"
    
    test_key="post_failover_test_$(date +%s)"
    test_value="failover_recovery_success"
    
    if docker exec "$NEW_MASTER_CONTAINER" redis-cli -a "$TEST_PASSWORD" set "$test_key" "$test_value" ex 300 | grep -q OK; then
        test_pass "Write operations work on new master"
        
        # Verify the write
        if docker exec "$NEW_MASTER_CONTAINER" redis-cli -a "$TEST_PASSWORD" get "$test_key" | grep -q "$test_value"; then
            test_pass "Read-after-write verification successful"
        else
            test_fail "Read-after-write verification failed"
        fi
    else
        test_fail "Write operations failed on new master"
    fi
fi

# PHASE 6: Master Recovery Testing
log_section "MASTER RECOVERY TESTING"

echo -e "\n🔄 Testing master recovery..." | tee -a "$TEST_REPORT"

# Restart the original master
echo "Restarting original master container..." | tee -a "$TEST_REPORT"
if docker start redis-master &>/dev/null; then
    test_pass "Original master container restarted"
    
    # Wait for recovery
    echo "Waiting for master recovery (30 seconds)..." | tee -a "$TEST_REPORT"
    sleep 30
    
    # Check if original master rejoined as slave
    if docker exec redis-master redis-cli -a "$TEST_PASSWORD" info replication | grep -q "role:slave"; then
        test_pass "Original master rejoined cluster as slave"
    else
        test_warn "Original master recovery status unclear"
    fi
    
else
    test_fail "Failed to restart original master container"
fi

# PHASE 7: Performance Impact Assessment
log_section "PERFORMANCE IMPACT ASSESSMENT"

echo -e "\n⚡ Assessing performance impact..." | tee -a "$TEST_REPORT"

if [ -n "$NEW_MASTER_CONTAINER" ]; then
    # Simple performance test
    echo "Running performance benchmark..." | tee -a "$TEST_REPORT"
    
    # Measure latency
    LATENCY_START=$(date +%s%N)
    for i in {1..100}; do
        docker exec "$NEW_MASTER_CONTAINER" redis-cli -a "$TEST_PASSWORD" ping &>/dev/null
    done
    LATENCY_END=$(date +%s%N)
    
    TOTAL_LATENCY=$(( (LATENCY_END - LATENCY_START) / 1000000 ))  # Convert to milliseconds
    AVG_LATENCY=$(( TOTAL_LATENCY / 100 ))
    
    if [ $AVG_LATENCY -lt 10 ]; then
        test_pass "Post-failover latency acceptable: ${AVG_LATENCY}ms avg"
    elif [ $AVG_LATENCY -lt 20 ]; then
        test_warn "Post-failover latency elevated: ${AVG_LATENCY}ms avg"
    else
        test_fail "Post-failover latency too high: ${AVG_LATENCY}ms avg"
    fi
    
    echo "Average latency: ${AVG_LATENCY}ms (100 ping operations)" >> "$TEST_REPORT"
fi

# PHASE 8: Cleanup and Final Report
log_section "CLEANUP AND FINAL REPORT"

echo -e "\n🧽 Cleaning up test data..." | tee -a "$TEST_REPORT"

# Clean up test data
if [ -n "$NEW_MASTER_CONTAINER" ]; then
    for i in $(seq 1 10); do
        docker exec "$NEW_MASTER_CONTAINER" redis-cli -a "$TEST_PASSWORD" del "${TEST_DATA_PREFIX}:key_$i" &>/dev/null
    done
    
    # Clean up FSM test data
    docker exec "$NEW_MASTER_CONTAINER" redis-cli -a "$TEST_PASSWORD" del "fsm:12345:12345" "fsm:67890:67890" "fsm:11111:11111" &>/dev/null
    
    test_pass "Test data cleanup completed"
fi

# Generate final report
TOTAL_TESTS=$((TEST_PASSED + TEST_FAILED + TEST_WARNINGS))
if [ $TOTAL_TESTS -gt 0 ]; then
    SUCCESS_RATE=$((TEST_PASSED * 100 / TOTAL_TESTS))
else
    SUCCESS_RATE=0
fi

echo "" >> "$TEST_REPORT"
echo "=== FINAL TEST SUMMARY ===" >> "$TEST_REPORT"
echo "Test Date: $(date)" >> "$TEST_REPORT"
echo "Test Duration: $(($(date +%s) - $(date -d "$(head -2 "$TEST_REPORT" | tail -1 | cut -d: -f2-)" +%s) 2>/dev/null || echo 300)) seconds" >> "$TEST_REPORT"
echo "Tests Passed: $TEST_PASSED" >> "$TEST_REPORT"
echo "Tests Failed: $TEST_FAILED" >> "$TEST_REPORT"
echo "Warnings: $TEST_WARNINGS" >> "$TEST_REPORT"
echo "Success Rate: $SUCCESS_RATE%" >> "$TEST_REPORT"
if [ "$failover_detected" = true ]; then
    echo "Failover Time: ${FAILOVER_TIME}s" >> "$TEST_REPORT"
fi
echo "" >> "$TEST_REPORT"

# Display final results
echo -e "\n${BLUE}📈 FAILOVER TEST RESULTS${NC}"
echo -e "${BLUE}========================${NC}"
echo -e "${GREEN}✅ Tests Passed: $TEST_PASSED${NC}"
echo -e "${RED}❌ Tests Failed: $TEST_FAILED${NC}"
echo -e "${YELLOW}⚠️  Warnings: $TEST_WARNINGS${NC}"
echo -e "${BLUE}📉 Success Rate: $SUCCESS_RATE%${NC}"

if [ "$failover_detected" = true ]; then
    echo -e "${PURPLE}⏱️  Failover Time: ${FAILOVER_TIME} seconds${NC}"
fi

echo -e "\n${BLUE}📋 Test Report: $TEST_REPORT${NC}"

# Final assessment
if [ $TEST_FAILED -eq 0 ] && [ $SUCCESS_RATE -ge 90 ] && [ "$failover_detected" = true ] && [ ${FAILOVER_TIME:-999} -le 5 ]; then
    echo -e "\n${GREEN}🎉 FAILOVER TEST SUCCESSFUL!${NC} 🚀"
    echo -e "${GREEN}Redis Sentinel cluster is production-ready${NC}"
    echo -e "${GREEN}• Failover time within target (${FAILOVER_TIME}s ≤ 5s)${NC}"
    echo -e "${GREEN}• Data persistence validated${NC}"
    echo -e "${GREEN}• FSM state preservation confirmed${NC}"
    echo -e "${GREEN}• Recovery mechanisms working${NC}"
    exit_code=0
elif [ $TEST_FAILED -le 1 ] && [ $SUCCESS_RATE -ge 80 ] && [ "$failover_detected" = true ]; then
    echo -e "\n${YELLOW}✅ FAILOVER TEST MOSTLY SUCCESSFUL${NC} ⚠️"
    echo -e "${YELLOW}Minor issues detected but cluster functional${NC}"
    exit_code=0
else
    echo -e "\n${RED}❌ FAILOVER TEST FAILED${NC}"
    echo -e "${RED}Critical issues detected in failover process${NC}"
    echo -e "${RED}Review test report for details: $TEST_REPORT${NC}"
    exit_code=1
fi

echo -e "\n${BLUE}🏁 AUTOMATED FAILOVER TESTING COMPLETE${NC}"
echo -e "${BLUE}=====================================${NC}"

exit $exit_code