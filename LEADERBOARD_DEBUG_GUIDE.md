# Leaderboard Debug Guide

## Issue
Backend returns 200 OK but frontend shows "Failed to load leaderboard. Please try again" with no backend logging after startup.

## Changes Made for Debugging

### Backend Changes (`march_madness_backend/main.py`)

1. **Enhanced Logging**:
   - Added logging to leaderboard endpoint entry point
   - Added logging to successful leaderboard query completion
   - Added new test endpoints for debugging

2. **CORS Configuration**:
   - Added wildcard "*" origin temporarily for debugging
   - Enhanced CORS headers and settings

3. **New Debug Endpoints**:
   - `/health` - Simple health check
   - `/test-cors` - CORS verification
   - `/test-leaderboard` - Simple mock leaderboard data

### Frontend Changes (`march-madness-frontend/src/pages/Leaderboard.jsx`)

1. **Enhanced Error Logging**:
   - Added comprehensive error details logging
   - Added response status, data, and headers logging
   - Added request configuration logging

2. **Environment Debug Info**:
   - Logs environment mode (dev/prod)
   - Logs API_URL configuration
   - Logs current window location
   - Logs user agent

3. **Test Endpoints**:
   - Added calls to health, CORS test, and test-leaderboard endpoints
   - Each with separate error handling and logging

## How to Debug

### Step 1: Check Browser Console
Open the frontend in browser and check console for:

1. **Environment Info**:
   ```
   === LEADERBOARD DEBUG INFO ===
   Environment MODE: production
   API_URL from config: https://march-madness-backend-qyw5.onrender.com
   Current window.location: https://your-frontend-domain.onrender.com
   ```

2. **Test Endpoints Results**:
   - Health check: Should succeed if backend is reachable
   - CORS test: Should succeed if CORS is configured correctly
   - Test leaderboard: Should succeed if basic API calls work

3. **Main Leaderboard Request**:
   - Check the detailed error logging for the actual leaderboard call
   - Look for network errors, CORS errors, or response parsing issues

### Step 2: Check Backend Logs
Look for these log messages in backend:

1. **Request Logging**:
   ```
   🏆 Leaderboard request received - Filter: overall
   ```

2. **Success Logging**:
   ```
   🏆 Leaderboard query successful - Returned X users
   ```

3. **Test Endpoint Hits**:
   ```
   ❤️ Health check endpoint hit
   🧪 CORS test endpoint hit
   🧪 Test leaderboard endpoint hit
   ```

### Step 3: Identify the Issue

**If no backend logs appear**:
- Frontend can't reach backend at all
- Check API_URL configuration
- Check network connectivity
- Check CORS preflight failures

**If backend logs appear but frontend still fails**:
- Response parsing issue
- Content-type mismatch
- Response format issue
- Check detailed error logs in console

**If test endpoints work but main leaderboard fails**:
- Database connection issue
- Query execution problem
- Large response size issue

## Common Issues and Solutions

### 1. Wrong API_URL
**Symptoms**: No backend logs, network errors
**Solution**: Verify API_URL matches actual backend domain

### 2. CORS Issues
**Symptoms**: CORS preflight errors, blocked requests
**Solution**: Verify frontend domain is in CORS allow_origins

### 3. Response Size Issues
**Symptoms**: Timeout errors, partial responses
**Solution**: Check if leaderboard response is too large

### 4. Database Issues
**Symptoms**: Backend logs show request but error in query
**Solution**: Check database connection and query execution

## Next Steps

1. Deploy these changes to production
2. Check browser console for detailed debug information
3. Check backend logs for request patterns
4. Based on findings, apply specific fixes
5. Remove debug logging once issue is resolved

## Cleanup

After debugging, remove:
- Wildcard "*" from CORS origins
- Excessive console.log statements
- Test endpoints (optional, can keep for monitoring)
- Debug environment logging