"""
Example demonstrating enhanced LLM cache capabilities.

This example shows how to use the enhanced LLM client with intelligent caching,
monitoring, and optimization features.

Requirements: 12.4
"""
import time
from typing import List

from llm.enhanced_llm_client import create_enhanced_llm_client


def demonstrate_enhanced_caching():
    """Demonstrate enhanced caching features."""
    print("=== Enhanced LLM Cache Demonstration ===\n")
    
    # Create enhanced LLM client with monitoring
    client = create_enhanced_llm_client(
        backend="openai",
        model="gpt-4",
        temperature=0.2,
        enable_enhanced_caching=True,
        enable_monitoring=True,
    )
    
    print("1. Enhanced LLM client created with intelligent caching and monitoring")
    print(f"   - Client configured: {client.is_configured()}")
    print(f"   - Enhanced caching enabled: {client.enhanced_caching_enabled}")
    print()
    
    # Demonstrate cache status
    status = client.get_cache_status()
    print("2. Initial cache status:")
    print(f"   - Enhanced caching: {status['enhanced_caching_enabled']}")
    print(f"   - Base cache enabled: {status['base_cache']['enabled']}")
    if 'enhanced_cache' in status:
        enhanced = status['enhanced_cache']
        print(f"   - Hit rate: {enhanced['hit_rate']:.2%}")
        print(f"   - Total requests: {enhanced['total_requests']}")
    print()
    
    # Simulate some LLM requests
    print("3. Making sample LLM requests...")
    
    sample_requests = [
        "Generate a Python function to calculate fibonacci numbers",
        "Create a function for sorting a list of numbers",
        "Write a function to reverse a string",
        "Generate a Python function to calculate fibonacci numbers",  # Duplicate for cache hit
        "Create a simple web scraper function",
    ]
    
    for i, prompt in enumerate(sample_requests, 1):
        print(f"   Request {i}: {prompt[:50]}...")
        
        start_time = time.time()
        try:
            # This would normally call the LLM, but will use mock/test mode
            response = client.generate(prompt, "You are a helpful Python developer.")
            response_time = time.time() - start_time
            
            print(f"   Response time: {response_time:.3f}s")
            print(f"   Response length: {len(response)} characters")
            
        except Exception as e:
            print(f"   Error: {e}")
        
        print()
    
    # Show updated cache status
    print("4. Updated cache status after requests:")
    status = client.get_cache_status()
    if 'enhanced_cache' in status:
        enhanced = status['enhanced_cache']
        print(f"   - Hit rate: {enhanced['hit_rate']:.2%}")
        print(f"   - Semantic hit rate: {enhanced['semantic_hit_rate']:.2%}")
        print(f"   - Bad cache rate: {enhanced['bad_cache_rate']:.2%}")
        print(f"   - Total requests: {enhanced['total_requests']}")
        print(f"   - Cache warmings: {enhanced['cache_warmings']}")
        print(f"   - Preemptive invalidations: {enhanced['preemptive_invalidations']}")
    print()
    
    # Demonstrate cache warming
    print("5. Demonstrating cache warming...")
    warmed_count = client.warm_cache()
    print(f"   - Warmed {warmed_count} cache entries")
    print()
    
    # Demonstrate cache optimization
    print("6. Demonstrating cache optimization...")
    optimization_result = client.optimize_cache()
    print(f"   - Cache warmed: {optimization_result['cache_warmed']} entries")
    print(f"   - Bad cache invalidated: {optimization_result['bad_cache_invalidated']} entries")
    print()
    
    # Show monitoring alerts
    print("7. Checking monitoring alerts...")
    alerts = client.get_monitoring_alerts()
    if alerts:
        print(f"   - Found {len(alerts)} alerts:")
        for alert in alerts:
            print(f"     * {alert['type']}: {alert['severity']} - {alert['message']}")
    else:
        print("   - No alerts found")
    print()
    
    # Demonstrate cache invalidation
    print("8. Demonstrating cache invalidation...")
    invalidated_count = client.invalidate_cache_pattern("error")
    print(f"   - Invalidated {invalidated_count} cache entries matching 'error' pattern")
    print()
    
    # Final cache metrics
    print("9. Final cache metrics:")
    cache_stats = client.cache_stats()
    if hasattr(cache_stats, 'hit_rate'):
        print(f"   - Base cache hit rate: {cache_stats.hit_rate:.2%}")
        print(f"   - Base cache size: {cache_stats.size}")
        print(f"   - Base cache requests: {cache_stats.requests}")
    
    if 'monitoring' in status:
        monitoring = status['monitoring']
        print(f"   - Monitoring active: {monitoring.get('monitoring_active', False)}")
        if 'metrics' in monitoring:
            metrics = monitoring['metrics']
            print(f"   - Cache size: {metrics.get('cache_size_mb', 0):.1f} MB")
    print()
    
    # Cleanup
    print("10. Shutting down enhanced client...")
    client.shutdown()
    print("    - Enhanced caching components shut down successfully")
    print()
    
    print("=== Enhanced Cache Demonstration Complete ===")


def demonstrate_cache_monitoring():
    """Demonstrate cache monitoring features."""
    print("=== Cache Monitoring Demonstration ===\n")
    
    # Create client with monitoring
    client = create_enhanced_llm_client(
        enable_enhanced_caching=True,
        enable_monitoring=True,
    )
    
    print("1. Cache monitoring features:")
    
    # Get monitoring status
    status = client.get_cache_status()
    if 'monitoring' in status:
        monitoring = status['monitoring']
        print(f"   - Monitoring active: {monitoring.get('monitoring_active', False)}")
        print(f"   - Total alerts: {monitoring.get('alerts', {}).get('total_alerts', 0)}")
        print(f"   - Unacknowledged alerts: {monitoring.get('alerts', {}).get('unacknowledged_alerts', 0)}")
        
        # Show thresholds
        thresholds = monitoring.get('thresholds', {})
        print(f"   - Min hit rate threshold: {thresholds.get('min_hit_rate', 0):.2%}")
        print(f"   - Max bad cache rate: {thresholds.get('max_bad_cache_rate', 0):.2%}")
        print(f"   - Max cache size: {thresholds.get('max_cache_size_mb', 0):.1f} MB")
        
        # Show performance trend
        trend = monitoring.get('performance_trend', {})
        print(f"   - Performance trend: {trend.get('trend', 'unknown')}")
    
    print()
    
    # Demonstrate alert acknowledgment
    print("2. Alert management:")
    alerts = client.get_monitoring_alerts()
    if alerts:
        print(f"   - Current alerts: {len(alerts)}")
        acknowledged = client.acknowledge_alerts()
        print(f"   - Acknowledged: {acknowledged} alerts")
    else:
        print("   - No alerts to acknowledge")
    
    print()
    
    # Cleanup
    client.shutdown()
    print("3. Monitoring demonstration complete")
    print()


def demonstrate_intelligent_key_generation():
    """Demonstrate intelligent cache key generation."""
    print("=== Intelligent Cache Key Generation ===\n")
    
    # Create client
    client = create_enhanced_llm_client(
        enable_enhanced_caching=True,
        enable_monitoring=False,
    )
    
    print("1. Demonstrating semantic similarity in cache keys:")
    
    # Similar requests that should have similar cache keys
    similar_requests = [
        ("Generate a function to calculate fibonacci", "You are a Python developer"),
        ("Create a method for fibonacci calculation", "You are a Python developer"),
        ("Write a fibonacci function", "You are a Python developer"),
    ]
    
    print("   Similar requests (should have similar intent hashes):")
    for i, (prompt, system) in enumerate(similar_requests, 1):
        print(f"   {i}. {prompt}")
    
    print()
    
    # Different complexity requests
    complexity_requests = [
        ("Hello", ""),  # Simple
        ("Generate a complex sorting algorithm with optimization", "You are an expert developer"),  # Complex
    ]
    
    print("2. Demonstrating complexity-based cache prioritization:")
    for i, (prompt, system) in enumerate(complexity_requests, 1):
        complexity = "Simple" if len(prompt) < 20 else "Complex"
        print(f"   {i}. {complexity}: {prompt}")
    
    print()
    
    # Cleanup
    client.shutdown()
    print("3. Key generation demonstration complete")
    print()


if __name__ == "__main__":
    """Run all demonstrations."""
    try:
        demonstrate_enhanced_caching()
        print("\n" + "="*60 + "\n")
        
        demonstrate_cache_monitoring()
        print("\n" + "="*60 + "\n")
        
        demonstrate_intelligent_key_generation()
        
    except Exception as e:
        print(f"Demonstration error: {e}")
        print("Note: This example requires proper LLM configuration to work fully.")
        print("In test/development mode, it will demonstrate the caching structure.")