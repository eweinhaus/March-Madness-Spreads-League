# March Madness Spreads - Scaling & Optimization Guide

## 🚨 CRITICAL: SCALING ALERT SYSTEM

**If you see this log message in your backend:**
```
🚨 SCALING ALERT: User count has exceeded 25! Refer to SCALING_GUIDE.md for immediate action.
```

**This means you need to scale your infrastructure immediately!**

---

## 📊 Current Configuration (Render.com Basic-1GB)

### Resource Limits
- **CPU**: 0.5 cores (500ms processing time per second)
- **RAM**: 1GB total (shared between app and database)
- **Database**: Shared PostgreSQL instance
- **Cost**: ~$5/month

### Current Optimizations
- **Connection Pool**: 6 max connections
- **Request Queue**: 8 max concurrent requests
- **Cache TTL**: 60 seconds (response cache), 120 seconds (game scores)
- **Database Timeouts**: 5s statement timeout, 10s idle timeout
- **Memory Settings**: 1MB work_mem, 512KB temp_buffers

---

## 📈 User Capacity Analysis

### ✅ Optimal Performance (1-8 users)
- **Response Time**: 1-4 seconds
- **Cache Hit Rate**: 60-80%
- **Resource Usage**: 40-60%
- **Status**: Excellent

### ⚠️ Acceptable Performance (9-20 users)
- **Response Time**: 4-15 seconds (with queuing)
- **Cache Hit Rate**: 50-70%
- **Resource Usage**: 60-85%
- **Status**: Good with queuing

### 🚨 Critical Performance (21-25 users)
- **Response Time**: 15-30 seconds
- **Cache Hit Rate**: 40-60%
- **Resource Usage**: 85-95%
- **Status**: Poor, frequent timeouts

### ❌ System Failure (26+ users)
- **Response Time**: 30+ seconds or timeouts
- **Cache Hit Rate**: <40%
- **Resource Usage**: 95%+
- **Status**: System failure, crashes possible

---

## 🔧 Scaling Options

### Option 1: Render.com Standard-1GB (Recommended for 25-50 users)
```yaml
Plan: Standard-1GB
CPU: 1 core (2x improvement)
RAM: 1GB (dedicated)
Database: Shared PostgreSQL
Cost: ~$7/month
```

**Recommended Configuration:**
```python
# Connection pool for Standard-1GB
pool = SimpleConnectionPool(
    minconn=2,
    maxconn=12,  # Increased from 6
    dsn=database_url
)

# Request queue for Standard-1GB
max_concurrent_requests = 15  # Increased from 8

# Database settings for Standard-1GB
cur.execute("SET statement_timeout = '10s'")  # Increased from 5s
cur.execute("SET work_mem = '2MB'")  # Increased from 1MB
cur.execute("SET temp_buffers = '1MB'")  # Increased from 512KB
```

### Option 2: Render.com Standard-2GB (Recommended for 50+ users)
```yaml
Plan: Standard-2GB
CPU: 1 core
RAM: 2GB (dedicated)
Database: Dedicated PostgreSQL
Cost: ~$15/month
```

**Recommended Configuration:**
```python
# Connection pool for Standard-2GB
pool = SimpleConnectionPool(
    minconn=3,
    maxconn=20,  # Much higher capacity
    dsn=database_url
)

# Request queue for Standard-2GB
max_concurrent_requests = 25  # Much higher capacity

# Database settings for Standard-2GB
cur.execute("SET statement_timeout = '15s'")
cur.execute("SET work_mem = '4MB'")
cur.execute("SET temp_buffers = '2MB'")
```

### Option 3: Dedicated Infrastructure (100+ users)
```yaml
Plan: Custom
CPU: 2+ cores
RAM: 4GB+
Database: Dedicated PostgreSQL
Cost: $25+/month
```

---

## 🚀 Performance Optimization Strategies

### 1. Caching Strategy
```python
# Response Cache (in-memory)
cache_ttl = 60  # seconds
cache_size_limit = 100  # entries

# Game Scores Cache
game_scores_cache_duration = 120  # seconds

# Browser Cache Headers
'/api/gamescores': 'public, max-age=120'  # 2 minutes
'/live_games': 'public, max-age=60'       # 1 minute
'/leaderboard': 'public, max-age=300'     # 5 minutes
```

### 2. Database Optimization
```sql
-- Conservative settings for Basic-1GB
SET statement_timeout = '5s';
SET idle_in_transaction_session_timeout = '10s';
SET work_mem = '1MB';
SET temp_buffers = '512KB';
SET max_parallel_workers_per_gather = 0;

-- Standard-1GB settings
SET statement_timeout = '10s';
SET work_mem = '2MB';
SET temp_buffers = '1MB';

-- Standard-2GB settings
SET statement_timeout = '15s';
SET work_mem = '4MB';
SET temp_buffers = '2MB';
```

### 3. Connection Pool Sizing
```python
# Basic-1GB (current)
minconn=1, maxconn=6

# Standard-1GB
minconn=2, maxconn=12

# Standard-2GB
minconn=3, maxconn=20

# Dedicated
minconn=5, maxconn=50
```

### 4. Request Queue Sizing
```python
# Basic-1GB (current)
max_concurrent_requests = 8

# Standard-1GB
max_concurrent_requests = 15

# Standard-2GB
max_concurrent_requests = 25

# Dedicated
max_concurrent_requests = 50
```

---

## 📊 Monitoring & Alerts

### Health Check Endpoints
- **`/health/db`**: Database and pool status
- **`/traffic/status`**: Current traffic levels and recommendations

### Key Metrics to Monitor
1. **Active Requests**: Should stay under max_concurrent_requests
2. **Queue Length**: Should be 0 for optimal performance
3. **Cache Hit Rate**: Should be >50% for good performance
4. **Response Times**: Should be <5s for most requests
5. **Error Rates**: Should be <5% for good performance

### Scaling Triggers
- **User Count > 25**: Immediate scaling required
- **Response Time > 10s**: Consider optimization
- **Error Rate > 10%**: Investigate immediately
- **Cache Hit Rate < 40%**: Optimize caching

---

## 🔄 Migration Steps

### Step 1: Upgrade Render.com Plan
1. Go to Render.com dashboard
2. Select your service
3. Click "Settings" → "Plan"
4. Choose Standard-1GB or Standard-2GB
5. Deploy the changes

### Step 2: Update Configuration
1. Update connection pool settings
2. Update request queue limits
3. Update database timeout settings
4. Deploy updated code

### Step 3: Monitor Performance
1. Check `/health/db` endpoint
2. Monitor response times
3. Watch error rates
4. Verify user experience

---

## 🚨 Emergency Procedures

### If System is Overloaded (26+ users)
1. **Immediate**: Upgrade to Standard-1GB plan
2. **Short-term**: Implement user limits in frontend
3. **Medium-term**: Optimize database queries
4. **Long-term**: Consider dedicated infrastructure

### If System Crashes
1. **Check logs**: Look for memory/CPU errors
2. **Restart service**: May resolve temporary issues
3. **Scale up**: Upgrade plan immediately
4. **Optimize**: Reduce connection pool if needed

---

## 💰 Cost Analysis

| Plan | Users | Cost/Month | Cost per User |
|------|-------|------------|---------------|
| Basic-1GB | 1-20 | $5 | $0.25 |
| Standard-1GB | 25-50 | $7 | $0.14 |
| Standard-2GB | 50-100 | $15 | $0.15 |
| Dedicated | 100+ | $25+ | $0.25+ |

---

## 📝 Configuration Files

### Current Settings (Basic-1GB)
```python
# main.py - Connection Pool
pool = SimpleConnectionPool(minconn=1, maxconn=6)

# main.py - Request Queue
max_concurrent_requests = 8

# main.py - Cache Settings
cache_ttl = 60
game_scores_cache_duration = 120
```

### Standard-1GB Settings
```python
# main.py - Connection Pool
pool = SimpleConnectionPool(minconn=2, maxconn=12)

# main.py - Request Queue
max_concurrent_requests = 15

# main.py - Cache Settings
cache_ttl = 120
game_scores_cache_duration = 300
```

### Standard-2GB Settings
```python
# main.py - Connection Pool
pool = SimpleConnectionPool(minconn=3, maxconn=20)

# main.py - Request Queue
max_concurrent_requests = 25

# main.py - Cache Settings
cache_ttl = 300
game_scores_cache_duration = 600
```

---

## 🎯 Quick Reference

### When to Scale
- **User count > 25**: Upgrade to Standard-1GB
- **User count > 50**: Upgrade to Standard-2GB
- **User count > 100**: Consider dedicated infrastructure

### Performance Targets
- **Response Time**: <5s for 90% of requests
- **Cache Hit Rate**: >50%
- **Error Rate**: <5%
- **Uptime**: >99%

### Monitoring Commands
```bash
# Check health
curl http://your-app.onrender.com/health/db

# Check traffic
curl http://your-app.onrender.com/traffic/status

# Check user count (in database)
SELECT COUNT(*) FROM users WHERE created_at >= '2025-01-01';
```

---

**Last Updated**: August 19, 2025
**Current Plan**: Render.com Basic-1GB
**Max Users**: 25 (with current optimizations)
**Next Upgrade**: Standard-1GB at 25+ users 