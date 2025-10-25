# Production Runbook - telegram-training-bot

## 🚨 Incident Response

### Severity Levels
- **P1 (Critical):** Complete outage, page on-call immediately
- **P2 (High):** Degraded service, notify team
- **P3 (Medium):** Minor issues, address during business hours

### Emergency Contacts
- **On-Call Engineer:** (Configure in PagerDuty)
- **Team Lead:** TBD
- **Security Team:** security@example.com

---

## 🔧 Common Issues & Solutions

### Bot Not Responding

**Symptoms:**
- Health endpoint returns 500
- No messages being processed
- Metrics show zero requests

**Diagnosis:**
```bash
# Check bot status
docker-compose ps

# Check logs
docker-compose logs -f bot --tail=100

# Check health
curl http://localhost:8080/health
```

**Solutions:**
1. Check Redis connectivity: `redis-cli ping`
2. Check database: `psql $DATABASE_URL -c "SELECT 1"`
3. Verify environment variables
4. Restart services: `docker-compose restart bot`

---

### High Error Rate

**Symptoms:**
- Error rate > 5%
- Prometheus alert fired

**Diagnosis:**
```bash
# Check error logs
docker-compose logs bot | grep ERROR

# Check metrics
curl http://localhost:8080/metrics | grep bot_errors_total
```

**Solutions:**
1. Check recent deployments (rollback if needed)
2. Review error types in logs
3. Check external dependencies (Telegram API)
4. Verify configuration changes

---

### Memory Leak

**Symptoms:**
- Gradual memory increase
- Eventually OOM killed

**Diagnosis:**
```bash
# Monitor memory
watch -n 5 'docker stats --no-stream bot'

# Check metrics
curl http://localhost:8080/metrics | grep bot_memory_usage_bytes
```

**Solutions:**
1. Identify memory growth pattern
2. Check for unclosed connections
3. Review recent code changes
4. Consider increasing memory limits
5. Schedule regular restarts as temporary fix

---

### Redis Connection Lost

**Symptoms:**
- "Redis connection lost" in logs
- Users lose session state

**Diagnosis:**
```bash
# Check Redis
redis-cli -h localhost ping

# Check Sentinel
redis-cli -p 26379 sentinel masters
```

**Solutions:**
1. Check Redis Sentinel status
2. Verify network connectivity
3. Check Redis logs
4. Trigger manual failover if needed

---

## 📊 Performance Tuning

### Database Optimization
- Run VACUUM ANALYZE weekly
- Monitor slow queries
- Check index usage
- Review connection pool settings

### Redis Optimization
- Monitor memory usage
- Check eviction policy
- Review key TTLs
- Optimize data structures

### Application Optimization
- Review async operations
- Check for N+1 queries
- Monitor handler timeouts
- Optimize payload sizes

---

## 🔄 Deployment Procedures

### Standard Deployment
1. Run tests: `pytest tests/ -v`
2. Build Docker image
3. Deploy to staging
4. Run smoke tests
5. Deploy to production
6. Monitor for 15 minutes

### Rollback Procedure
1. Identify previous stable version
2. Pull previous Docker image
3. Update docker-compose
4. Restart services
5. Verify health
6. Monitor closely

### Database Migrations
1. Backup database first
2. Test migration on staging
3. Run migration: `alembic upgrade head`
4. Verify data integrity
5. Monitor performance

---

## 📈 Monitoring & Alerting

### Key Metrics to Watch
- Request rate and errors
- Response latency (P95, P99)
- Memory and CPU usage
- Database connection pool
- Redis operations

### Dashboards
- **Grafana:** http://grafana:3000
- **Prometheus:** http://prometheus:9090

### Alert Channels
- PagerDuty (Critical)
- Slack #bot-alerts (Warning)
- Email (Info)

---

## 🔐 Security Procedures

### Credential Rotation
1. Generate new credentials
2. Update Secrets Manager
3. Deploy with new secrets
4. Invalidate old credentials
5. Monitor for issues

### Security Incident
1. Isolate affected systems
2. Collect evidence
3. Notify security team
4. Patch vulnerability
5. Post-mortem analysis

---

## 🧪 Testing in Production

### Smoke Tests
```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# Basic functionality
pytest tests/smoke/ --target=production
```

### Load Testing
```bash
./scripts/run_load_test.sh production 100 5m
```

---

## 📞 Escalation Matrix

1. **First Response:** On-call engineer (15 min SLA)
2. **Escalation 1:** Team lead (30 min)
3. **Escalation 2:** Engineering manager (1 hour)
4. **Escalation 3:** CTO (Critical only)

---

## 📚 Additional Resources

- Architecture Diagram: `docs/architecture.md`
- API Documentation: `docs/API.md`
- SLA Metrics: `docs/SLA_METRICS.md`
- Monitoring Guide: `monitoring/README.md`
