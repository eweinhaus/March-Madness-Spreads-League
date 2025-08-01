#!/usr/bin/env python3
"""
Test script to add a simple authentication endpoint
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth import verify_token
import requests

def test_simple_auth():
    """Test authentication with a simple approach"""
    print("=== Testing Simple Authentication ===")
    
    # Get a token
    response = requests.post(
        "http://localhost:8000/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": "adminEthan", "password": "test123"}
    )
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        print(f"✅ Got token: {token[:50]}...")
        
        # Test direct verification
        username = verify_token(token)
        print(f"✅ Direct verification: {username}")
        
        # Test with a simple curl command
        import subprocess
        result = subprocess.run([
            "curl", "-s", "-X", "GET", "http://localhost:8000/users/me",
            "-H", f"Authorization: Bearer {token}"
        ], capture_output=True, text=True)
        
        print(f"✅ Curl status: {result.returncode}")
        print(f"✅ Curl output: {result.stdout}")
        if result.stderr:
            print(f"⚠️ Curl stderr: {result.stderr}")
        
    else:
        print(f"❌ Failed to get token: {response.status_code}")

if __name__ == "__main__":
    test_simple_auth() 