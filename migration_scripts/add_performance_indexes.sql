-- ============================================================================
-- Database Performance Indexes for telegram-training-bot
-- ============================================================================
--
-- This script adds production-optimized indexes to improve query performance.
--
-- Usage:
--   psql -U botuser -d training_bot -f migration_scripts/add_performance_indexes.sql
--
-- Or with Alembic migration:
--   alembic revision -m "add performance indexes"
--   (then copy contents to the upgrade() function)
--
-- ============================================================================

-- Enable timing to see performance impact
\timing on

BEGIN;

-- ============================================================================
-- USERS TABLE INDEXES
-- ============================================================================

-- Primary lookup by telegram_id (most common query)
-- Using HASH index for exact match lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_telegram_id_hash
ON users USING hash (telegram_id);

-- Composite index for filtering by department and park
-- Useful for admin queries: "Show all sales staff in Moscow park"
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_department_park
ON users (department, park_location)
WHERE is_blocked = false;

-- Index for admin user management
-- Find active users, exclude blocked
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active
ON users (is_blocked, created_at DESC)
WHERE is_blocked = false;

-- Index for user search by username
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_username
ON users (username)
WHERE username IS NOT NULL;

-- Position-based queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_position
ON users (position, department);

-- ============================================================================
-- USER_ACTIVITY TABLE INDEXES
-- ============================================================================

-- Timestamp-based queries (most recent activities)
-- Essential for "recent activity" and "active users" queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_timestamp_desc
ON user_activity (timestamp DESC);

-- User activity lookup
-- Find all activities for a specific user
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_user_action
ON user_activity (user_id, action, timestamp DESC);

-- Section-based analytics
-- "Which sections are most popular?"
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_section_timestamp
ON user_activity (section, timestamp DESC)
WHERE section IS NOT NULL;

-- Action-based analytics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_action
ON user_activity (action, timestamp DESC);

-- Partial index for recent activity (last 30 days)
-- Significantly speeds up "active users" queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_recent
ON user_activity (user_id, timestamp DESC)
WHERE timestamp > NOW() - INTERVAL '30 days';

-- ============================================================================
-- STATISTICS AND ANALYTICS INDEXES
-- ============================================================================

-- Daily statistics queries
-- Enables fast "users active today" queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_date
ON user_activity (DATE(timestamp), user_id);

-- Hourly activity distribution
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_hour
ON user_activity (EXTRACT(HOUR FROM timestamp), DATE(timestamp));

-- ============================================================================
-- ADMIN AND SECURITY INDEXES
-- ============================================================================

-- Find blocked users
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_blocked
ON users (is_blocked, updated_at DESC)
WHERE is_blocked = true;

-- Track user updates
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_updated
ON users (updated_at DESC);

-- ============================================================================
-- PARTIAL INDEXES FOR ACTIVE DATA
-- ============================================================================

-- Active users in last 24 hours
-- Dramatically speeds up "daily active users" metric
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_24h
ON user_activity (user_id)
WHERE timestamp > NOW() - INTERVAL '24 hours';

-- Active users in last 7 days
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_7d
ON user_activity (user_id)
WHERE timestamp > NOW() - INTERVAL '7 days';

-- ============================================================================
-- COVERING INDEXES FOR COMMON QUERIES
-- ============================================================================

-- Cover common user profile queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_profile_covering
ON users (telegram_id) INCLUDE (full_name, department, position, park_location);

-- Cover activity summary queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_summary_covering
ON user_activity (user_id, timestamp DESC)
INCLUDE (action, section);

-- ============================================================================
-- GIN INDEXES FOR FULL-TEXT SEARCH (if needed)
-- ============================================================================

-- Full-text search on user names (optional, comment out if not needed)
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_fulltext
-- ON users USING gin(to_tsvector('russian', full_name));

-- ============================================================================
-- VERIFY INDEXES
-- ============================================================================

-- Show all indexes on users table
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'users'
ORDER BY indexname;

-- Show all indexes on user_activity table
SELECT
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'user_activity'
ORDER BY indexname;

-- ============================================================================
-- INDEX SIZE REPORT
-- ============================================================================

SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('users', 'user_activity')
ORDER BY pg_relation_size(indexname::regclass) DESC;

-- ============================================================================
-- QUERY PERFORMANCE TESTING
-- ============================================================================

-- Test query: Find active users in last 24 hours
EXPLAIN ANALYZE
SELECT DISTINCT user_id
FROM user_activity
WHERE timestamp > NOW() - INTERVAL '24 hours';

-- Test query: User profile lookup
EXPLAIN ANALYZE
SELECT telegram_id, full_name, department, position, park_location
FROM users
WHERE telegram_id = 12345;

-- Test query: Recent user activities
EXPLAIN ANALYZE
SELECT action, section, timestamp
FROM user_activity
WHERE user_id = 12345
ORDER BY timestamp DESC
LIMIT 50;

-- ============================================================================
-- MAINTENANCE RECOMMENDATIONS
-- ============================================================================

-- Schedule regular VACUUM and ANALYZE
-- Add to cron or pg_cron:
-- SELECT cron.schedule('0 2 * * *', $$VACUUM ANALYZE users, user_activity$$);

-- Monitor index usage
-- Run periodically to identify unused indexes:
--
-- SELECT
--     schemaname,
--     tablename,
--     indexname,
--     idx_scan,
--     idx_tup_read,
--     idx_tup_fetch
-- FROM pg_stat_user_indexes
-- WHERE schemaname = 'public'
-- AND idx_scan = 0
-- ORDER BY pg_relation_size(indexrelid) DESC;

COMMIT;

-- ============================================================================
-- NOTES
-- ============================================================================
--
-- 1. CONCURRENTLY option allows index creation without blocking writes
-- 2. Partial indexes reduce storage and improve performance for filtered queries
-- 3. INCLUDE clause creates covering indexes for index-only scans
-- 4. Hash indexes are fast for equality lookups but don't support range queries
-- 5. B-tree indexes (default) support both equality and range queries
--
-- Performance Impact:
-- - Expect 10-100x speedup on filtered queries
-- - Index-only scans eliminate table lookups entirely
-- - Partial indexes reduce index maintenance overhead
--
-- Trade-offs:
-- - Indexes consume disk space (~5-20% of table size)
-- - INSERT/UPDATE/DELETE slightly slower due to index maintenance
-- - Worth it for read-heavy workloads (typical for this bot)
--
-- ============================================================================
