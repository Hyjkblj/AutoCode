#!/usr/bin/env python3
"""
Unit tests for the smoke test suite
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add the scripts directory to the path so we can import the smoke test module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the smoke test classes by executing the file content
with open(os.path.join(os.path.dirname(__file__), 'smoke-test.py'), 'r', encoding='utf-8') as f:
    smoke_test_content = f.read()
# Remove the main execution part
smoke_test_content = smoke_test_content.split('if __name__ == "__main__":')[0]
exec(smoke_test_content)


class TestSmokeTestSuite(unittest.TestCase):
    """Test cases for the SmokeTestSuite class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.suite = SmokeTestSuite(
            base_url="http://localhost",
            operator_token="test-token",
            username="test-user",
            password="test-pass",
            project_id="test-proj"
        )
    
    def test_initialization(self):
        """Test that the smoke test suite initializes correctly"""
        self.assertEqual(self.suite.base_url, "http://localhost")
        self.assertEqual(self.suite.operator_token, "test-token")
        self.assertEqual(self.suite.username, "test-user")
        self.assertEqual(self.suite.password, "test-pass")
        self.assertEqual(self.suite.project_id, "test-proj")
        
        # Check that all required service endpoints are configured
        self.assertGreater(len(self.suite.service_endpoints), 0)
        
        # Check that required services are properly marked
        required_services = [ep for ep in self.suite.service_endpoints if ep.required]
        self.assertGreater(len(required_services), 0)
        
        # Verify Control Plane and Java Sandbox are in the list
        service_names = [ep.name for ep in self.suite.service_endpoints]
        self.assertIn("Control Plane", service_names)
        self.assertIn("Java Sandbox", service_names)
    
    def test_service_endpoint_configuration(self):
        """Test that service endpoints are properly configured"""
        for endpoint in self.suite.service_endpoints:
            # Each endpoint should have required fields
            self.assertIsInstance(endpoint.name, str)
            self.assertGreater(len(endpoint.name), 0)
            self.assertIsInstance(endpoint.port, int)
            self.assertGreater(endpoint.port, 0)
            self.assertLess(endpoint.port, 65536)
            self.assertIsInstance(endpoint.health_path, str)
            self.assertTrue(endpoint.health_path.startswith('/'))
            self.assertIsInstance(endpoint.timeout, int)
            self.assertGreater(endpoint.timeout, 0)
            self.assertIsInstance(endpoint.required, bool)
            self.assertIsInstance(endpoint.description, str)
    
    def test_port_accessibility_check(self):
        """Test port accessibility checking"""
        # Test with a port that should be closed
        success, message = self.suite.check_port_accessibility("127.0.0.1", 99999, timeout=1)
        self.assertFalse(success)
        self.assertTrue("not accessible" in message or "failed" in message or "port must be" in message)
        
        # Test with invalid host
        success, message = self.suite.check_port_accessibility("invalid-host-name", 80, timeout=1)
        self.assertFalse(success)
        self.assertTrue("failed" in message or "timed out" in message)
    
    def test_test_result_creation(self):
        """Test that test results are created correctly"""
        def dummy_test():
            import time
            time.sleep(0.001)  # Small delay to ensure duration > 0
            return True, "Test passed", {"key": "value"}
        
        result = self.suite.run_test("Dummy Test", dummy_test)
        
        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.name, "Dummy Test")
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Test passed")
        self.assertIsInstance(result.duration, float)
        self.assertGreaterEqual(result.duration, 0)  # Allow for very fast execution
        self.assertEqual(result.details, {"key": "value"})
    
    def test_test_result_exception_handling(self):
        """Test that exceptions in tests are handled correctly"""
        def failing_test():
            raise ValueError("Test error")
        
        result = self.suite.run_test("Failing Test", failing_test)
        
        self.assertIsInstance(result, TestResult)
        self.assertEqual(result.name, "Failing Test")
        self.assertFalse(result.success)
        self.assertIn("Test error", result.message)
        self.assertIsInstance(result.duration, float)
        self.assertIsNotNone(result.details)
        self.assertIn("exception", result.details)
    
    @patch('socket.socket')
    def test_port_accessibility_success(self, mock_socket):
        """Test successful port accessibility check"""
        # Mock successful connection
        mock_sock = Mock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock
        
        success, message = self.suite.check_port_accessibility("127.0.0.1", 8080, timeout=5)
        
        self.assertTrue(success)
        self.assertIn("accessible", message)
        mock_sock.connect_ex.assert_called_once_with(("127.0.0.1", 8080))
        mock_sock.close.assert_called_once()
    
    def test_service_health_endpoint_validation(self):
        """Test that service health endpoints are valid"""
        # All service endpoints should have valid health paths
        valid_health_paths = [
            "/actuator/health",  # Spring Boot
            "/sandbox/health",   # Java Sandbox
            "/healthz",          # Gateway
            "/-/healthy",        # Prometheus/Alertmanager
            "/api/health"        # Grafana
        ]
        
        for endpoint in self.suite.service_endpoints:
            self.assertIn(endpoint.health_path, valid_health_paths,
                         f"Invalid health path for {endpoint.name}: {endpoint.health_path}")
    
    def test_required_vs_optional_services(self):
        """Test that core services are required and observability services are optional"""
        required_services = [ep.name for ep in self.suite.service_endpoints if ep.required]
        optional_services = [ep.name for ep in self.suite.service_endpoints if not ep.required]
        
        # Core services should be required
        self.assertIn("Control Plane", required_services)
        self.assertIn("Java Sandbox", required_services)
        
        # Observability services should be optional
        self.assertIn("Prometheus", optional_services)
        self.assertIn("Grafana", optional_services)
        self.assertIn("Alertmanager", optional_services)


class TestServiceEndpoint(unittest.TestCase):
    """Test cases for the ServiceEndpoint dataclass"""
    
    def test_service_endpoint_creation(self):
        """Test ServiceEndpoint creation with all parameters"""
        endpoint = ServiceEndpoint(
            name="Test Service",
            port=8080,
            health_path="/health",
            timeout=10,
            required=True,
            description="Test service description"
        )
        
        self.assertEqual(endpoint.name, "Test Service")
        self.assertEqual(endpoint.port, 8080)
        self.assertEqual(endpoint.health_path, "/health")
        self.assertEqual(endpoint.timeout, 10)
        self.assertTrue(endpoint.required)
        self.assertEqual(endpoint.description, "Test service description")
    
    def test_service_endpoint_defaults(self):
        """Test ServiceEndpoint creation with default values"""
        endpoint = ServiceEndpoint(
            name="Test Service",
            port=8080,
            health_path="/health"
        )
        
        self.assertEqual(endpoint.timeout, 5)  # Default timeout
        self.assertTrue(endpoint.required)     # Default required
        self.assertEqual(endpoint.description, "")  # Default description


class TestTestResult(unittest.TestCase):
    """Test cases for the TestResult dataclass"""
    
    def test_test_result_creation(self):
        """Test TestResult creation"""
        result = TestResult(
            name="Test Name",
            success=True,
            duration=1.23,
            message="Test message",
            details={"key": "value"}
        )
        
        self.assertEqual(result.name, "Test Name")
        self.assertTrue(result.success)
        self.assertEqual(result.duration, 1.23)
        self.assertEqual(result.message, "Test message")
        self.assertEqual(result.details, {"key": "value"})
    
    def test_test_result_without_details(self):
        """Test TestResult creation without details"""
        result = TestResult(
            name="Test Name",
            success=False,
            duration=2.45,
            message="Test failed"
        )
        
        self.assertEqual(result.name, "Test Name")
        self.assertFalse(result.success)
        self.assertEqual(result.duration, 2.45)
        self.assertEqual(result.message, "Test failed")
        self.assertIsNone(result.details)


if __name__ == "__main__":
    # Run the unit tests
    unittest.main(verbosity=2)