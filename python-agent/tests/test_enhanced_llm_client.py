"""
Unit tests for enhanced LLM client.

Tests the integration of enhanced caching with the existing LLM client.

Requirements: 12.4
"""
import unittest
from unittest.mock import MagicMock, patch

from llm.enhanced_llm_client import EnhancedLLMClient, create_enhanced_llm_client
from llm.llm_client import LLMClient, LLMSettings
from utils.observability import TaskObservability


class TestEnhancedLLMClient(unittest.TestCase):
    """Test cases for enhanced LLM client."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock base LLM client
        self.base_client = MagicMock(spec=LLMClient)
        self.base_client.settings = LLMSettings(
            backend="openai",
            model="gpt-4",
            temperature=0.2,
            timeout_seconds=120,
        )
        self.base_client.is_configured.return_value = True
        self.base_client.has_required_key.return_value = True
        self.base_client.required_key_name.return_value = None
        
        # Sample test data
        self.sample_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Generate a Python function."},
        ]
        self.sample_response = "def example(): pass"
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    @patch('llm.enhanced_llm_client.create_cache_monitor')
    def test_initialization_with_enhanced_caching(self, mock_monitor, mock_cache_manager):
        """Test initialization with enhanced caching enabled."""
        # Create enhanced client
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=True,
        )
        
        # Verify initialization
        self.assertEqual(client.base_client, self.base_client)
        self.assertTrue(client.enhanced_caching_enabled)
        
        # Verify enhanced components were created
        mock_cache_manager.assert_called_once()
        mock_monitor.assert_called_once()
        
        # Verify properties delegate to base client
        self.assertEqual(client.settings, self.base_client.settings)
        self.assertTrue(client.is_configured())
        self.assertTrue(client.has_required_key())
        self.assertIsNone(client.required_key_name())
    
    def test_initialization_without_enhanced_caching(self):
        """Test initialization with enhanced caching disabled."""
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=False,
        )
        
        self.assertFalse(client.enhanced_caching_enabled)
        self.assertIsNone(client.cache_manager)
        self.assertIsNone(client.cache_monitor)
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    def test_chat_with_enhanced_caching(self, mock_cache_manager_class):
        """Test chat with enhanced caching enabled."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        
        # Mock cache key generation
        mock_components = MagicMock()
        mock_cache_manager.generate_cache_key.return_value = ("test_key", mock_components)
        
        # Mock cache miss
        mock_cache_manager.get_cached_response.return_value = (False, "", None)
        
        # Mock base client response
        self.base_client.chat.return_value = self.sample_response
        
        # Create client and make request
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=False,
        )
        
        response = client.chat(self.sample_messages)
        
        # Verify response
        self.assertEqual(response, self.sample_response)
        
        # Verify cache operations
        mock_cache_manager.generate_cache_key.assert_called_once()
        mock_cache_manager.get_cached_response.assert_called_once_with("test_key")
        mock_cache_manager.store_cached_response.assert_called_once()
        mock_cache_manager.detect_bad_cache.assert_called()
        
        # Verify base client was called
        self.base_client.chat.assert_called_once_with(self.sample_messages)
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    def test_chat_with_cache_hit(self, mock_cache_manager_class):
        """Test chat with cache hit."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        
        # Mock cache key generation
        mock_components = MagicMock()
        mock_cache_manager.generate_cache_key.return_value = ("test_key", mock_components)
        
        # Mock cache hit
        mock_entry = MagicMock()
        mock_cache_manager.get_cached_response.return_value = (True, self.sample_response, mock_entry)
        
        # Mock bad cache detection (not bad)
        mock_cache_manager.detect_bad_cache.return_value = False
        
        # Create client and make request
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=False,
        )
        
        response = client.chat(self.sample_messages)
        
        # Verify response from cache
        self.assertEqual(response, self.sample_response)
        
        # Verify base client was NOT called (cache hit)
        self.base_client.chat.assert_not_called()
        
        # Verify bad cache detection was called
        mock_cache_manager.detect_bad_cache.assert_called_once_with("test_key", self.sample_response)
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    def test_chat_with_bad_cache_detection(self, mock_cache_manager_class):
        """Test chat with bad cache detection."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        
        # Mock cache key generation
        mock_components = MagicMock()
        mock_cache_manager.generate_cache_key.return_value = ("test_key", mock_components)
        
        # Mock cache hit with bad response
        bad_response = "Error: I cannot help with that."
        mock_entry = MagicMock()
        mock_cache_manager.get_cached_response.return_value = (True, bad_response, mock_entry)
        
        # Mock bad cache detection (is bad)
        mock_cache_manager.detect_bad_cache.return_value = True
        
        # Mock base client response
        self.base_client.chat.return_value = self.sample_response
        
        # Create client and make request
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=False,
        )
        
        response = client.chat(self.sample_messages)
        
        # Should get fresh response, not cached bad response
        self.assertEqual(response, self.sample_response)
        
        # Verify base client was called (bad cache detected)
        self.base_client.chat.assert_called_once_with(self.sample_messages)
        
        # Verify bad cache was detected
        mock_cache_manager.detect_bad_cache.assert_called()
    
    def test_chat_fallback_to_base_client(self):
        """Test fallback to base client when enhanced caching fails."""
        # Mock base client response
        self.base_client.chat.return_value = self.sample_response
        
        # Create client with enhanced caching disabled
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=False,
        )
        
        response = client.chat(self.sample_messages)
        
        # Should get response from base client
        self.assertEqual(response, self.sample_response)
        self.base_client.chat.assert_called_once_with(self.sample_messages)
    
    def test_generate_method(self):
        """Test generate method."""
        # Mock base client response
        self.base_client.chat.return_value = self.sample_response
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=False,
        )
        
        response = client.generate("Generate a function", "You are a coder")
        
        # Verify response
        self.assertEqual(response, self.sample_response)
        
        # Verify messages were constructed correctly
        expected_messages = [
            {"role": "system", "content": "You are a coder"},
            {"role": "user", "content": "Generate a function"},
        ]
        self.base_client.chat.assert_called_once_with(expected_messages)
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    def test_cache_warming(self, mock_cache_manager_class):
        """Test cache warming functionality."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        mock_cache_manager.warm_cache.return_value = 5
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=False,
        )
        
        # Warm cache
        warmed_count = client.warm_cache()
        
        # Verify warming
        self.assertEqual(warmed_count, 5)
        mock_cache_manager.warm_cache.assert_called_once_with(None)
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    def test_cache_invalidation(self, mock_cache_manager_class):
        """Test cache invalidation functionality."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        mock_cache_manager.invalidate_preemptively.return_value = 3
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=False,
        )
        
        # Invalidate pattern
        invalidated_count = client.invalidate_cache_pattern("error")
        
        # Verify invalidation
        self.assertEqual(invalidated_count, 3)
        mock_cache_manager.invalidate_preemptively.assert_called_once_with("error")
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    @patch('llm.enhanced_llm_client.create_cache_monitor')
    def test_cache_status(self, mock_monitor, mock_cache_manager_class):
        """Test cache status reporting."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        
        # Mock cache metrics
        mock_metrics = MagicMock()
        mock_metrics.hit_rate = 0.95
        mock_metrics.semantic_hit_rate = 0.80
        mock_metrics.bad_cache_rate = 0.02
        mock_metrics.total_requests = 100
        mock_metrics.cache_warmings = 5
        mock_metrics.preemptive_invalidations = 2
        mock_cache_manager.get_cache_metrics.return_value = mock_metrics
        
        # Mock base client stats
        mock_base_stats = MagicMock()
        mock_base_stats.enabled = True
        mock_base_stats.hit_rate = 0.90
        mock_base_stats.size = 50
        mock_base_stats.requests = 100
        self.base_client.cache_stats.return_value = mock_base_stats
        
        # Mock monitor
        mock_cache_monitor = MagicMock()
        mock_monitor.return_value = mock_cache_monitor
        mock_cache_monitor.get_current_status.return_value = {"monitoring": "active"}
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=True,
        )
        
        # Get status
        status = client.get_cache_status()
        
        # Verify status structure
        self.assertIn("enhanced_caching_enabled", status)
        self.assertIn("base_client_configured", status)
        self.assertIn("base_cache", status)
        self.assertIn("enhanced_cache", status)
        self.assertIn("monitoring", status)
        
        # Verify enhanced cache metrics
        enhanced_cache = status["enhanced_cache"]
        self.assertEqual(enhanced_cache["hit_rate"], 0.95)
        self.assertEqual(enhanced_cache["semantic_hit_rate"], 0.80)
        self.assertEqual(enhanced_cache["bad_cache_rate"], 0.02)
        self.assertEqual(enhanced_cache["total_requests"], 100)
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    def test_cache_optimization(self, mock_cache_manager_class):
        """Test cache optimization."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        mock_cache_manager.warm_cache.return_value = 3
        mock_cache_manager.invalidate_preemptively.return_value = 2
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=False,
        )
        
        # Optimize cache
        result = client.optimize_cache()
        
        # Verify optimization
        self.assertEqual(result["cache_warmed"], 3)
        self.assertEqual(result["bad_cache_invalidated"], 2)
        self.assertIn("timestamp", result)
        
        # Verify methods were called
        mock_cache_manager.warm_cache.assert_called_once()
        mock_cache_manager.invalidate_preemptively.assert_called_once_with("error")
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    @patch('llm.enhanced_llm_client.create_cache_monitor')
    def test_monitoring_alerts(self, mock_monitor, mock_cache_manager_class):
        """Test monitoring alerts functionality."""
        # Mock cache monitor
        mock_cache_monitor = MagicMock()
        mock_monitor.return_value = mock_cache_monitor
        
        # Mock alerts
        mock_alerts = [
            {"type": "hit_rate_low", "severity": "critical", "message": "Test alert"},
        ]
        mock_cache_monitor.get_current_status.return_value = {
            "alerts": {"recent_alerts": mock_alerts}
        }
        mock_cache_monitor.acknowledge_alerts.return_value = 1
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=True,
        )
        
        # Get alerts
        alerts = client.get_monitoring_alerts()
        self.assertEqual(alerts, mock_alerts)
        
        # Acknowledge alerts
        acknowledged = client.acknowledge_alerts(["hit_rate_low"])
        self.assertEqual(acknowledged, 1)
        mock_cache_monitor.acknowledge_alerts.assert_called_once_with(["hit_rate_low"])
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    def test_metrics_recording(self, mock_cache_manager_class):
        """Test metrics recording integration."""
        # Mock cache manager
        mock_cache_manager = MagicMock()
        mock_cache_manager_class.return_value = mock_cache_manager
        
        # Mock observability
        mock_observation = MagicMock(spec=TaskObservability)
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=False,
        )
        
        # Record metrics
        client.record_cache_metrics(mock_observation, stage="TestStage")
        
        # Verify both base and enhanced metrics were recorded
        self.base_client.record_cache_metrics.assert_called_once()
        mock_cache_manager.record_cache_metrics.assert_called_once_with(mock_observation, "TestStage")
    
    @patch('llm.enhanced_llm_client.EnhancedCacheManager')
    @patch('llm.enhanced_llm_client.create_cache_monitor')
    def test_shutdown(self, mock_monitor, mock_cache_manager_class):
        """Test client shutdown."""
        # Mock cache monitor
        mock_cache_monitor = MagicMock()
        mock_monitor.return_value = mock_cache_monitor
        
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=True,
            enable_monitoring=True,
        )
        
        # Shutdown
        client.shutdown()
        
        # Verify monitor was stopped
        mock_cache_monitor.stop_monitoring.assert_called_once()
    
    def test_create_enhanced_llm_client_function(self):
        """Test create_enhanced_llm_client factory function."""
        with patch('llm.enhanced_llm_client.LLMClient') as mock_llm_client:
            mock_base_client = MagicMock()
            mock_llm_client.return_value = mock_base_client
            
            with patch('llm.enhanced_llm_client.EnhancedLLMClient') as mock_enhanced_client:
                # Create client using factory function
                create_enhanced_llm_client(
                    backend="openai",
                    model="gpt-4",
                    temperature=0.3,
                    enable_enhanced_caching=True,
                    enable_monitoring=False,
                )
                
                # Verify base client was created with correct parameters
                mock_llm_client.assert_called_once_with(
                    backend="openai",
                    model="gpt-4",
                    temperature=0.3,
                    timeout_seconds=None,
                )
                
                # Verify enhanced client was created
                mock_enhanced_client.assert_called_once_with(
                    base_client=mock_base_client,
                    enable_enhanced_caching=True,
                    enable_monitoring=False,
                )
    
    def test_delegation_methods(self):
        """Test methods that delegate to base client."""
        client = EnhancedLLMClient(
            base_client=self.base_client,
            enable_enhanced_caching=False,
        )
        
        # Test delegation methods
        client.clear_cache(reset_stats=True)
        self.base_client.clear_cache.assert_called_once_with(reset_stats=True)
        
        client.discard_last_cache_entry(reason="test")
        self.base_client.discard_last_cache_entry.assert_called_once_with(reason="test")
        
        client.discard_cache_entries_since(10, reason="test")
        self.base_client.discard_cache_entries_since.assert_called_once_with(10, reason="test")
        
        client.cache_event_cursor()
        self.base_client.cache_event_cursor.assert_called_once()
        
        client.last_cache_event()
        self.base_client.last_cache_event.assert_called_once()


if __name__ == '__main__':
    unittest.main()