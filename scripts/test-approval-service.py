#!/usr/bin/env python3
"""
Smoke test for the Approval Service.
Tests basic functionality of the approval service endpoints.
"""

import requests
import json
import time
import sys
from typing import Dict, Any

def test_approval_service():
    """Test the approval service endpoints."""
    base_url = "http://localhost:8064"
    
    print("🔍 Testing Approval Service...")
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/api/v1/approvals/health", timeout=5)
        if response.status_code == 200 and response.text == "OK":
            print("   ✅ Health check passed")
        else:
            print(f"   ❌ Health check failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False
    
    # Test 2: Spring Boot actuator health
    print("2. Testing actuator health...")
    try:
        response = requests.get(f"{base_url}/actuator/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            if health_data.get("status") == "UP":
                print("   ✅ Actuator health check passed")
            else:
                print(f"   ❌ Actuator health check failed: {health_data}")
                return False
        else:
            print(f"   ❌ Actuator health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Actuator health check failed: {e}")
        return False
    
    # Test 3: Create approval request
    print("3. Testing approval creation...")
    approval_request = {
        "approvalId": "smoke_test_001",
        "taskId": "task_smoke_001",
        "action": "app.generate",
        "tool": "command.exec",
        "command": "echo 'smoke test'",
        "riskScore": 0.3
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/approvals",
            json=approval_request,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code == 201:
            approval_data = response.json()
            if approval_data.get("approvalId") == "smoke_test_001":
                print("   ✅ Approval creation passed")
            else:
                print(f"   ❌ Approval creation failed: unexpected data {approval_data}")
                return False
        else:
            print(f"   ❌ Approval creation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Approval creation failed: {e}")
        return False
    
    # Test 4: Get approval
    print("4. Testing approval retrieval...")
    try:
        response = requests.get(f"{base_url}/api/v1/approvals/smoke_test_001", timeout=5)
        if response.status_code == 200:
            approval_data = response.json()
            if approval_data.get("approvalId") == "smoke_test_001" and approval_data.get("decision") == "PENDING":
                print("   ✅ Approval retrieval passed")
            else:
                print(f"   ❌ Approval retrieval failed: unexpected data {approval_data}")
                return False
        else:
            print(f"   ❌ Approval retrieval failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Approval retrieval failed: {e}")
        return False
    
    # Test 5: List pending approvals
    print("5. Testing pending approvals list...")
    try:
        response = requests.get(f"{base_url}/api/v1/approvals?pendingOnly=true", timeout=5)
        if response.status_code == 200:
            approvals = response.json()
            if isinstance(approvals, list) and any(a.get("approvalId") == "smoke_test_001" for a in approvals):
                print("   ✅ Pending approvals list passed")
            else:
                print(f"   ❌ Pending approvals list failed: smoke test approval not found")
                return False
        else:
            print(f"   ❌ Pending approvals list failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Pending approvals list failed: {e}")
        return False
    
    print("🎉 All approval service tests passed!")
    return True

def test_gateway_routing():
    """Test approval service through the gateway."""
    gateway_url = "http://localhost:8080"
    
    print("\n🌐 Testing Gateway Routing to Approval Service...")
    
    try:
        response = requests.get(f"{gateway_url}/api/v1/approvals/health", timeout=10)
        if response.status_code == 200 and response.text == "OK":
            print("   ✅ Gateway routing to approval service works")
            return True
        else:
            print(f"   ❌ Gateway routing failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Gateway routing failed: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Starting Approval Service Smoke Tests\n")
    
    # Wait for services to be ready
    print("⏳ Waiting for services to be ready...")
    time.sleep(5)
    
    success = True
    
    # Test direct service access
    if not test_approval_service():
        success = False
    
    # Test gateway routing
    if not test_gateway_routing():
        success = False
    
    if success:
        print("\n🎉 All tests passed! Approval service is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check the service logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()