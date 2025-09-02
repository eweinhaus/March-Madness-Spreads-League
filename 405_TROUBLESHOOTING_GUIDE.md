# 405 Method Not Allowed - Troubleshooting Guide

## 🚨 Issue Summary
After recent changes to the lock of the week scoring logic, the backend deployment is showing 405 "Method Not Allowed" errors, preventing proper functionality.

## 🔍 Root Cause Analysis

The 405 error typically occurs when:
1. **HTTP method mismatch**: Frontend sends POST, backend expects GET (or vice versa)
2. **Route definition issues**: Missing or incorrectly defined routes
3. **Deployment configuration**: Proxy/load balancer blocking certain methods
4. **CORS preflight issues**: OPTIONS requests not handled properly

## 🛠️ Fixes Applied

### 1. Fixed Python Syntax Warnings
- Fixed invalid escape sequences in regex patterns that could cause parsing issues during deployment
- Changed `\.` to `\\.` in SQL regex patterns to prevent Python warnings

### 2. Enhanced Debugging
- Added comprehensive request logging with 405-specific error tracking
- Added debug endpoints:
  - `/debug/routes` - Lists all available routes and their methods
  - `/debug/submit_pick` - Tests HTTP methods on a submit_pick-like endpoint

### 3. CORS Configuration Verified
- Confirmed all necessary HTTP methods are allowed: `["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"]`
- All required origins are whitelisted

## 🧪 Testing Steps

### 1. Check Route Availability
```bash
curl -X GET https://your-backend-url.com/debug/routes
```
This will show all available routes and their supported methods.

### 2. Test Specific Endpoint
```bash
# Test POST method (what frontend uses)
curl -X POST https://your-backend-url.com/debug/submit_pick \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'

# Test OPTIONS method (CORS preflight)
curl -X OPTIONS https://your-backend-url.com/submit_pick \
  -H "Origin: https://your-frontend-url.com" \
  -H "Access-Control-Request-Method: POST"
```

### 3. Check Actual submit_pick Endpoint
```bash
# With authentication token
curl -X POST https://your-backend-url.com/submit_pick \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"game_id": 1, "picked_team": "Team A", "lock": false}'
```

## 🔧 Deployment-Specific Solutions

### For Render.com (Your Current Platform)
1. **Check Build Logs**: Look for Python syntax errors during deployment
2. **Environment Variables**: Ensure all required env vars are set
3. **Start Command**: Verify `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}` is correct

### If Issue Persists
1. **Rollback Option**: Consider reverting to previous working commit temporarily
2. **Gradual Deployment**: Deploy changes incrementally to isolate the issue
3. **Alternative Deployment**: Try deploying to a staging environment first

## 📊 Monitoring
- Check application logs for 405 error patterns
- Monitor the new debug endpoints for insights
- Use the enhanced error logging to identify specific problematic requests

## 🚀 Next Steps
1. Deploy these fixes to your staging/production environment
2. Test the debug endpoints to confirm route availability
3. Monitor logs for any remaining 405 errors
4. If issues persist, use the debugging information to narrow down the specific problematic endpoint

## 🔄 Rollback Plan
If these fixes don't resolve the issue, you can rollback to the previous working commit:
```bash
git revert HEAD
git push origin main
```

The centralized scoring function changes can be re-applied later once the 405 issue is resolved.