#!/bin/bash
# Production Deployment Script for telegram-training-bot v3.2
# Usage: ./deploy_production.sh [--no-backup] [--skip-tests] [--force]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
BACKUP=true
RUN_TESTS=true
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-backup)
            BACKUP=false
            shift
            ;;
        --skip-tests)
            RUN_TESTS=false
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./deploy_production.sh [--no-backup] [--skip-tests] [--force]"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}🚀 telegram-training-bot v3.2 Production Deployment${NC}"
echo "=============================================="

# Check environment file
if [ ! -f .env.production ]; then
    echo -e "${RED}❌ .env.production not found${NC}"
    echo "Please copy .env.production.template to .env.production and configure it"
    exit 1
fi

# Load environment
source .env.production

# Verify required variables
REQUIRED_VARS=("BOT_TOKEN" "DB_PASSWORD" "ADMIN_PASSWORD_HASH")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}❌ Required variable $var is not set in .env.production${NC}"
        exit 1
    fi
done

# Check if default passwords are still in use
if [[ "$DB_PASSWORD" == "CHANGE_ME"* ]] || [[ "$ADMIN_PASSWORD_HASH" == "CHANGE_ME"* ]]; then
    echo -e "${RED}❌ Default passwords detected in .env.production${NC}"
    echo "Please set strong passwords before deployment"
    exit 1
fi

# Run tests
if [ "$RUN_TESTS" = true ]; then
    echo -e "${YELLOW}🧪 Running test suite...${NC}"
    if ! pytest tests/ -v --maxfail=5; then
        echo -e "${RED}❌ Tests failed${NC}"
        if [ "$FORCE" = false ]; then
            echo "Use --force to deploy anyway (not recommended)"
            exit 1
        else
            echo -e "${YELLOW}⚠️ Continuing despite test failures (--force specified)${NC}"
        fi
    fi
    echo -e "${GREEN}✅ Tests passed${NC}"
fi

# Backup database
if [ "$BACKUP" = true ]; then
    echo -e "${YELLOW}💾 Creating database backup...${NC}"
    mkdir -p backups
    BACKUP_FILE="backups/backup_$(date +%Y%m%d_%H%M%S).sql"

    if docker-compose ps | grep -q postgres; then
        docker-compose exec -T postgres pg_dump -U botuser training_bot > "$BACKUP_FILE" 2>/dev/null || true
        if [ -f "$BACKUP_FILE" ]; then
            echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
        else
            echo -e "${YELLOW}⚠️ Backup failed (database may not exist yet)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ PostgreSQL not running, skipping backup${NC}"
    fi
fi

# Run database migrations
echo -e "${YELLOW}🗄️ Running database migrations...${NC}"
if command -v alembic &> /dev/null; then
    alembic upgrade head
    echo -e "${GREEN}✅ Migrations applied${NC}"
else
    echo -e "${YELLOW}⚠️ Alembic not installed, skipping migrations${NC}"
    echo "Install with: pip install alembic"
fi

# Stop existing containers
echo -e "${YELLOW}🛑 Stopping existing containers...${NC}"
docker-compose -f docker-compose.production.yml down

# Build new images
echo -e "${YELLOW}🔨 Building new images...${NC}"
docker-compose -f docker-compose.production.yml build --no-cache

# Start services
echo -e "${YELLOW}🚀 Starting services...${NC}"
docker-compose -f docker-compose.production.yml up -d

# Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 30

# Health checks
echo -e "${YELLOW}🏥 Performing health checks...${NC}"

# Check PostgreSQL
if docker-compose -f docker-compose.production.yml exec -T postgres pg_isready -U botuser -d training_bot > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL: HEALTHY${NC}"
else
    echo -e "${RED}❌ PostgreSQL: UNHEALTHY${NC}"
    HEALTH_CHECK_FAILED=true
fi

# Check Redis Master
if docker-compose -f docker-compose.production.yml exec -T redis-master redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis Master: HEALTHY${NC}"
else
    echo -e "${RED}❌ Redis Master: UNHEALTHY${NC}"
    HEALTH_CHECK_FAILED=true
fi

# Check Redis Sentinel
if docker-compose -f docker-compose.production.yml exec -T redis-sentinel1 redis-cli -p 26379 sentinel master mymaster > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis Sentinel: HEALTHY${NC}"
else
    echo -e "${RED}❌ Redis Sentinel: UNHEALTHY${NC}"
    HEALTH_CHECK_FAILED=true
fi

# Check bot container
if docker-compose -f docker-compose.production.yml ps | grep -q "bot.*Up"; then
    echo -e "${GREEN}✅ Bot: RUNNING${NC}"
else
    echo -e "${RED}❌ Bot: NOT RUNNING${NC}"
    HEALTH_CHECK_FAILED=true
fi

# Final status
echo ""
echo "=============================================="
if [ -z "$HEALTH_CHECK_FAILED" ]; then
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""
    echo "📊 Monitoring URLs:"
    echo "  Grafana: http://localhost:3000 (admin / \$GRAFANA_PASSWORD)"
    echo "  Prometheus: http://localhost:9090"
    echo ""
    echo "📝 Logs:"
    echo "  docker-compose -f docker-compose.production.yml logs -f bot"
    echo ""
    echo "🔍 Check status:"
    echo "  docker-compose -f docker-compose.production.yml ps"
    exit 0
else
    echo -e "${RED}❌ Deployment completed with errors${NC}"
    echo ""
    echo "Check logs:"
    echo "  docker-compose -f docker-compose.production.yml logs"
    exit 1
fi
