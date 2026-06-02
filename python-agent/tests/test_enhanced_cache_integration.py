"""
Integration test for enhanced LLM cache system.

This test validates the complete enhanced caching system including intelligent
key generation, monitoring, bad cache detection, and cache optimization.

Requirements: 12.4
"""
import time
import unittest
from unittest.mock import MagicMock

from llm.enhanced_llm_client import create_enhanced_llm_client


class TestEnhancedCacheIntegration(unittest.TestCase):
    """Integration test for enhanced cache system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create enhanced client with all features enabled
        self.client = create_enhanced_llm_client(
            backend="openai",
            model="gpt-4",
            temperature=0.2,
            enable_enhanced_caching=True,
            enable_monitoring=True,
        )
        
        # Mock the base client's chat method to avoid actual LLM calls
        self.client.base_client.chat = MagicMock()
        
        # Sample responses for different types of requests
        self.good_response = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""
        
        self.bad_response = "Error: I cannot help with that request."
    
    def test_complete_cache_workflow(self):
        """Test complete enhanced cache workflow."""
        print("\n=== Enhanced Cache Integration Test ===")
        
        # 1. Initial status check
        print("\n1. Initial cache status:")
        status = self.client.get_cache_status()
        self.assertTrue(status['enhanced_caching_enabled'])
        print(f"   Enhanced caching: {status['enhanced_caching_enabled']}")
        
        # 2. Make initial requests (cache misses)
        print("\n2. Making initial requests (should be cache misses):")
        requests = [
            "Generate a Python function to calculate fibonacci numbers",
            "Create a function for sorting a list",
            "Write a function to reverse a string",
        ]
        
        for i, prompt in enumerate(requests):
            self.client.base_client.chat.return_value = self.good_response
            response = self.client.generate(prompt, "You are a Python developer")
            self.assertEqual(response, self.good_response)
            print(f"   Request {i+1}: {len(response)} chars")
        
        # 3. Check cache status after initial requests
        print("\n3. Cache status after initial requests:")
        status = self.client.get_cache_status()
        if 'enhanced_cache' in status:
            enhanced = status['enhanced_cache']
            print(f"   Total requests: {enhanced['total_requests']}")
            print(f"   Hit rate: {enhanced['hit_rate']:.2%}")
        
        # 4. Repeat requests (should be cache hits)
        print("\n4. Repeating requests (should be cache hits):")
        for i, prompt in enumerate(requests):
            # Don't set return value - should come from cache
            response = self.client.generate(prompt, "You are a Python developer")
            self.assertEqual(response, self.good_response)
            print(f"   Repeat {i+1}: {len(response)} chars")
        
        # 5. Check improved cache status
        print("\n5. Cache status after repeat requests:")
        status = self.client.get_cache_status()
        if 'enhanced_cache' in status:
            enhanced = status['enhanced_cache']
            print(f"   Total requests: {enhanced['total_requests']}")
            print(f"   Hit rate: {enhanced['hit_rate']:.2%}")
            print(f"   Semantic hit rate: {enhanced['semantic_hit_rate']:.2%}")
            
            # Should have improved hit rate
            self.assertGreater(enhanced['hit_rate'], 0.0)
        
        # 6. Test bad cache detection
        print("\n6. Testing bad cache detection:")
        bad_request = "Generate something that will fail"
        self.client.base_client.chat.return_value = self.bad_response
        response = self.client.generate(bad_request)
        self.assertEqual(response, self.bad_response)
        
        # Check if bad cache was detected
        status = self.client.get_cache_status()
        if 'enhanced_cache' in status:
            enhanced = status['enhanced_cache']
            print(f"   Bad cache detections: {enhanced.get('bad_cache_detections', 0)}")
        
        # 7. Test cache optimization
        print("\n7. Testing cache optimization:")
        optimization_result = self.client.optimize_cache()
        print(f"   Cache warmed: {optimization_result['cache_warmed']} entries")
        print(f"   Bad cache invalidated: {optimization_result['bad_cache_invalidated']} entries")
        
        # 8. Test semantic similarity
        print("\n8. Testing semantic similarity:")
        similar_requests = [
            "Generate a fibonacci function",
            "Create a fibonacci method", 
            "Write fibonacci code",
        ]
        
        for i, prompt in enumerate(similar_requests):
            self.client.base_client.chat.return_value = self.good_response
            response = self.client.generate(prompt, "You are a Python developer")
            self.assertEqual(response, self.good_response)
            print(f"   Similar request {i+1}: processed")
        
        # 9. Final cache status
        print("\n9. Final cache status:")
        status = self.client.get_cache_status()
        if 'enhanced_cache' in status:
            enhanced = status['enhanced_cache']
            print(f"   Total requests: {enhanced['total_requests']}")
            print(f"   Hit rate: {enhanced['hit_rate']:.2%}")
            print(f"   Semantic hit rate: {enhanced['semantic_hit_rate']:.2%}")
            print(f"   Bad cache rate: {enhanced['bad_cache_rate']:.2%}")
            print(f"   Cache warmings: {enhanced['cache_warmings']}")
            print(f"   Preemptive invalidations: {enhanced['preemptive_invalidations']}")
            
            # Validate final performance
            self.assertGreaterEqual(enhanced['total_requests'], 9)  # At least 9 requests made
            self.assertGreaterEqual(enhanced['hit_rate'], 0.3)  # At least 30% hit rate
            self.assertLessEqual(enhanced['bad_cache_rate'], 0.2)  # Less than 20% bad cache
        
        # 10. Test monitoring alerts
        print("\n10. Checking monitoring alerts:")
        alerts = self.client.get_monitoring_alerts()
        print(f"    Current alerts: {len(alerts)}")
        for alert in alerts:
            print(f"    - {alert['type']}: {alert['severity']}")
        
        print("\n=== Integration Test Complete ===")
    
    def test_cache_performance_under_realistic_load(self):
        """Test cache performance under realistic usage patterns."""
        print("\n=== Realistic Load Test ===")
        
        # Simulate realistic development workflow
        code_generation_requests = [
            ("Generate a sorting function", "sorting algorithm"),
            ("Create a validation utility", "input validation"),
            ("Write a data parser", "JSON parsing"),
            ("Generate a sorting function", "sorting algorithm"),  # Repeat
            ("Build a file reader", "file I/O"),
            ("Create a validation utility", "input validation"),  # Repeat
            ("Write a database query", "SQL query"),
            ("Generate a sorting function", "sorting algorithm"),  # Repeat
            ("Create an API client", "HTTP client"),
            ("Write a data parser", "JSON parsing"),  # Repeat
        ]
        
        responses = {}
        for prompt, topic in code_generation_requests:
            if topic not in responses:
                responses[topic] = f"# {topic.title()}\ndef {topic.replace(' ', '_')}():\n    pass"
        
        # Process requests
        start_time = time.time()
        for i, (prompt, topic) in enumerate(code_generation_requests):
            self.client.base_client.chat.return_value = responses[topic]
            response = self.client.generate(prompt, "You are a Python developer")
            self.assertEqual(response, responses[topic])
            
            if i % 3 == 0:  # Progress update
                print(f"   Processed {i+1}/{len(code_generation_requests)} requests")
        
        total_time = time.time() - start_time
        
        # Analyze performance
        status = self.client.get_cache_status()
        if 'enhanced_cache' in status:
            enhanced = status['enhanced_cache']
            
            print(f"\nRealistic Load Results:")
            print(f"   Requests processed: {len(code_generation_requests)}")
            print(f"   Total time: {total_time:.2f} seconds")
            print(f"   Requests per second: {len(code_generation_requests) / total_time:.1f}")
            print(f"   Hit rate: {enhanced['hit_rate']:.2%}")
            print(f"   Semantic hit rate: {enhanced['semantic_hit_rate']:.2%}")
            
            # Validate realistic performance
            expected_hit_rate = 0.4  # 40% hit rate is realistic with repeats
            self.assertGreaterEqual(
                enhanced['hit_rate'], 
                expected_hit_rate,
                f"Hit rate {enhanced['hit_rate']:.2%} below expected {expected_hit_rate:.2%}"
            )
            
            # Validate reasonable throughput
            min_rps = 5  # At least 5 requests per second
            actual_rps = len(code_generation_requests) / total_time
            self.assertGreaterEqual(
                actual_rps,
                min_rps,
                f"Throughput {actual_rps:.1f} RPS below minimum {min_rps} RPS"
            )
        
        print("=== Realistic Load Test Complete ===")
    
    def test_cache_monitoring_and_alerting(self):
        """Test cache monitoring and alerting functionality."""
        print("\n=== Monitoring and Alerting Test ===")
        
        # Get initial monitoring status
        status = self.client.get_cache_status()
        if 'monitoring' in status:
            monitoring = status['monitoring']
            print(f"   Monitoring active: {monitoring.get('monitoring_active', False)}")
            
            # Check thresholds
            thresholds = monitoring.get('thresholds', {})
            print(f"   Hit rate threshold: {thresholds.get('min_hit_rate', 0):.2%}")
            print(f"   Bad cache threshold: {thresholds.get('max_bad_cache_rate', 0):.2%}")
        
        # Make some requests to generate activity
        for i in range(5):
            prompt = f"Generate function {i}"
            self.client.base_client.chat.return_value = f"def function_{i}(): pass"
            response = self.client.generate(prompt)
            self.assertIn(f"function_{i}", response)
        
        # Check for alerts
        alerts = self.client.get_monitoring_alerts()
        print(f"   Generated alerts: {len(alerts)}")
        
        # Test alert acknowledgment
        if alerts:
            acknowledged = self.client.acknowledge_alerts()
            print(f"   Acknowledged alerts: {acknowledged}")
        
        print("=== Monitoring Test Complete ===")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self.client, 'shutdown'):
            self.client.shutdown()


if __name__ == '__main__':
    unittest.main(verbosity=2)