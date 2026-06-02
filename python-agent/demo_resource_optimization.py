#!/usr/bin/env python3
"""
Demonstration script for the resource optimization system.

Shows how the resource optimizer, monitor, and task queue manager work together
to provide dynamic scaling, cost monitoring, and efficient task batching.

Requirements: Task 33.2 - Optimize resource utilization
"""
import time
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from utils.resource_integration import (
    ResourceOptimizationManager,
    ResourceOptimizationConfig,
    initialize_resource_optimization,
)
from utils.resource_optimizer import ResourceMetrics, CostMetrics
from utils.task_queue_manager import TaskPriority


def demo_resource_optimization():
    """Demonstrate the complete resource optimization system."""
    print("=== Resource Optimization System Demo ===\n")
    
    # 1. Initialize the system
    print("1. Initializing resource optimization system...")
    config = ResourceOptimizationConfig(
        monitoring_enabled=True,
        monitoring_interval_seconds=5.0,  # Fast for demo
        cost_tracking_enabled=True,
        batching_enabled=True,
        max_batch_size=5,
        cpu_scale_up_threshold=75.0,
        memory_scale_up_threshold=80.0,
    )
    
    manager = initialize_resource_optimization(config)
    print(f"✓ System initialized with monitoring interval: {config.monitoring_interval_seconds}s")
    print(f"✓ CPU scale-up threshold: {config.cpu_scale_up_threshold}%")
    print(f"✓ Memory scale-up threshold: {config.memory_scale_up_threshold}%")
    print()
    
    # 2. Add some tasks to demonstrate batching
    print("2. Adding tasks to demonstrate intelligent batching...")
    task_ids = []
    
    # Add similar tasks that should be batched together
    for i in range(3):
        task_data = {
            "prompt": f"Analyze code file {i+1}",
            "intent": "analyze",
            "agentProfile": "coder",
        }
        task_id = manager.add_task(task_data, TaskPriority.NORMAL)
        task_ids.append(task_id)
        print(f"✓ Added task {i+1}: {task_id}")
    
    # Add a high-priority task
    urgent_task_data = {
        "prompt": "Fix critical security vulnerability",
        "intent": "code_change",
        "agentProfile": "security",
    }
    urgent_task_id = manager.add_task(urgent_task_data, TaskPriority.CRITICAL)
    task_ids.append(urgent_task_id)
    print(f"✓ Added critical task: {urgent_task_id}")
    print()
    
    # 3. Simulate system metrics to trigger scaling recommendations
    print("3. Simulating high system load to trigger scaling recommendations...")
    
    # Simulate high CPU usage
    high_cpu_metrics = ResourceMetrics(
        cpu_percent=85.0,  # Above 75% threshold
        memory_percent=60.0,
        network_io_mbps=15.0,
        active_connections=35,
        queue_depth=20,  # High queue depth
        pending_tasks=40,
        llm_tokens_per_minute=1500,
    )
    
    manager._optimizer.record_metrics(high_cpu_metrics)
    print(f"✓ Recorded high CPU metrics: {high_cpu_metrics.cpu_percent}%")
    print(f"✓ Queue depth: {high_cpu_metrics.queue_depth}")
    print()
    
    # 4. Get scaling recommendations
    print("4. Getting scaling recommendations...")
    recommendations = manager.get_scaling_recommendations()
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"Recommendation {i}:")
            print(f"  Resource: {rec.resource_type.value}")
            print(f"  Action: {rec.action.value}")
            print(f"  Current: {rec.current_value:.1f}")
            print(f"  Recommended: {rec.recommended_value:.1f}")
            print(f"  Reason: {rec.reason}")
            print(f"  Confidence: {rec.confidence:.2f}")
            print(f"  Cost Impact: ${rec.estimated_cost_impact:.2f}")
            print()
    else:
        print("No scaling recommendations at this time.")
        print()
    
    # 5. Simulate LLM usage and track costs
    print("5. Simulating LLM usage for cost tracking...")
    
    # Record some LLM usage
    manager.record_llm_usage(5000, 0.01)  # 5K tokens, $0.01
    manager.record_llm_usage(3000, 0.006)  # 3K tokens, $0.006
    manager.record_llm_usage(7000, 0.014)  # 7K tokens, $0.014
    
    print("✓ Recorded LLM usage: 15,000 tokens, $0.03 total")
    
    # Track cost metrics
    cost_metrics = CostMetrics(
        llm_api_cost_usd=0.03,
        compute_cost_usd=0.05,
        storage_cost_usd=0.01,
        network_cost_usd=0.005,
        total_cost_usd=0.095,
        cost_per_task=0.024,  # $0.024 per task
    )
    
    manager._optimizer.track_cost(cost_metrics)
    print(f"✓ Tracked cost metrics: ${cost_metrics.total_cost_usd:.3f} total")
    print(f"✓ Cost per task: ${cost_metrics.cost_per_task:.3f}")
    print()
    
    # 6. Get cost optimization recommendations
    print("6. Getting cost optimization recommendations...")
    cost_recommendations = manager.get_cost_optimization_recommendations()
    
    if cost_recommendations:
        for i, rec in enumerate(cost_recommendations, 1):
            print(f"Cost Recommendation {i}: {rec}")
    else:
        print("No cost optimization recommendations at this time.")
    print()
    
    # 7. Show system status
    print("7. Current system status:")
    status = manager.get_system_status()
    
    print(f"✓ System initialized: {status['initialized']}")
    print(f"✓ System running: {status['running']}")
    
    if 'resource_utilization' in status:
        resource_util = status['resource_utilization']
        if 'current_metrics' in resource_util:
            metrics = resource_util['current_metrics']
            print(f"✓ Current CPU: {metrics.get('cpu_percent', 0):.1f}%")
            print(f"✓ Current Memory: {metrics.get('memory_percent', 0):.1f}%")
            print(f"✓ Queue depth: {metrics.get('queue_depth', 0)}")
    
    if 'queue_status' in status:
        queue_status = status['queue_status']
        if 'metrics' in queue_status:
            queue_metrics = queue_status['metrics']
            print(f"✓ Total tasks: {queue_metrics.get('total_tasks', 0)}")
            print(f"✓ Queued tasks: {queue_metrics.get('queued_tasks', 0)}")
    
    print()
    
    # 8. Demonstrate normal load scenario
    print("8. Simulating normal system load...")
    
    normal_metrics = ResourceMetrics(
        cpu_percent=45.0,  # Normal CPU usage
        memory_percent=55.0,  # Normal memory usage
        network_io_mbps=8.0,
        active_connections=20,
        queue_depth=5,  # Low queue depth
        pending_tasks=10,
        llm_tokens_per_minute=800,
    )
    
    manager._optimizer.record_metrics(normal_metrics)
    print(f"✓ Recorded normal metrics: CPU {normal_metrics.cpu_percent}%, Memory {normal_metrics.memory_percent}%")
    
    # Check for recommendations with normal load
    normal_recommendations = manager.get_scaling_recommendations()
    if normal_recommendations:
        print(f"✓ {len(normal_recommendations)} scaling recommendations with normal load")
    else:
        print("✓ No scaling recommendations needed with normal load")
    
    print()
    
    # 9. Show queue summary
    print("9. Task queue summary:")
    if 'queue_status' in status:
        queue_summary = status['queue_status']
        
        if 'distribution' in queue_summary:
            distribution = queue_summary['distribution']
            
            if 'by_intent' in distribution:
                print("Tasks by intent:")
                for intent, count in distribution['by_intent'].items():
                    print(f"  {intent}: {count}")
            
            if 'by_priority' in distribution:
                print("Tasks by priority:")
                for priority, count in distribution['by_priority'].items():
                    print(f"  {priority}: {count}")
        
        if 'configuration' in queue_summary:
            config_info = queue_summary['configuration']
            print(f"Queue configuration:")
            print(f"  Max queue size: {config_info.get('max_queue_size', 'N/A')}")
            print(f"  Max batch size: {config_info.get('max_batch_size', 'N/A')}")
            print(f"  Max wait time: {config_info.get('max_wait_time', 'N/A')}s")
    
    print()
    print("=== Demo Complete ===")
    print("\nThe resource optimization system provides:")
    print("• Dynamic scaling recommendations based on system load")
    print("• Cost monitoring and optimization suggestions")
    print("• Intelligent task batching for efficiency")
    print("• Real-time resource utilization tracking")
    print("• Integration with existing orchestrator components")


if __name__ == "__main__":
    try:
        demo_resource_optimization()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()