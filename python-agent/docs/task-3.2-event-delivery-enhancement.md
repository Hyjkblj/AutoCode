# Task 3.2: Enhanced Event Delivery with Retry and Backoff

## Overview

Task 3.2 enhances the Control Plane client with exponential backoff retry logic, circuit breaker integration, and comprehensive observability. This implementation fulfills **Requirement 2.2**: "WHEN the Control_Plane is unavailable, THE Python_Agent SHALL retry event delivery with exponential backoff up to 5 attempts."

## Key Features

### 1. Exponential Backoff Retry Logic
- **Pattern**: 1s, 2s, 4s, 8s, 16s delays between retry attempts
- **Maximum Attempts**: 5 (enforced per requirement)
- **Initial Backoff**: Minimum 1.0 seconds (enforced per requirement)
- **Retryable Errors**: Network timeouts, 5xx HTTP errors, connection failures
- **Non-Retryable Errors**: 4xx client errors (except 408, 425, 429)

### 2. Circuit Breaker Integration
- **Failure Threshold**: 3 consecutive failures trigger circuit breaker
- **Recovery Timeout**: 60 seconds in half-open state
- **Behavior**: Blocks requests when open, preventing cascade failures
- **Integration**: Seamlessly works with retry logic

### 3. Structured Logging
- **Context Fields**: taskId, traceId, runId, eventType, attempt, error details
- **Log Levels**: INFO for success/start, WARNING for retries, ERROR for final failure
- **Observability**: Integration with TaskObservability framework
- **Metrics**: Delivery success/failure rates, circuit breaker state

### 4. Event Delivery Metrics
- **Success Rate**: Percentage of successful deliveries
- **Failure Rate**: Percentage of failed deliveries
- **Circuit Breaker Stats**: Opens, recovery attempts
- **Retry Statistics**: Exhausted retries, total attempts

## Implementation Details

### Enhanced ControlPlaneClient

```python
class ControlPlaneClient:
    def __init__(self, base_url: str, agent_token: str, ...):
        # Circuit breaker for event delivery
        self._event_circuit_breaker = CircuitBreaker(
            name="control_plane_events",
            failure_threshold=3,
            recovery_timeout_seconds=60.0
        )
        
        # Structured logging
        self._logger = logging.getLogger(f"{__name__}.ControlPlaneClient")
        
        # Metrics tracking
        self._event_delivery_metrics = {...}
```

### Retry Logic Implementation

```python
def publish_event_with_retry_result(
    self,
    task_id: str,
    event: dict[str, Any],
    *,
    max_attempts: int = 5,
    initial_backoff_seconds: float = 1.0,
    observability: TaskObservability | None = None,
) -> PublishEventResult:
    """
    Implements exponential backoff: 1s, 2s, 4s, 8s, 16s
    Integrates with circuit breaker for failure detection
    Provides structured logging and metrics
    """
```

### Integration with Redis Outbox

The enhanced client integrates seamlessly with the Redis outbox from Task 3.1:

1. **Event Storage**: Events are stored in outbox before delivery attempts
2. **Retry Coordination**: Failed events remain in outbox for recovery
3. **Acknowledgment**: Successful deliveries are acknowledged in outbox
4. **Recovery**: Unacknowledged events are redelivered after restart

## Usage Examples

### Basic Usage

```python
client = ControlPlaneClient(
    base_url="http://localhost:8058",
    agent_token="your-token"
)

# Simple retry with defaults (5 attempts, 1s initial backoff)
response = client.publish_event_with_retry(task_id, event)

# Advanced usage with observability
result = client.publish_event_with_retry_result(
    task_id,
    event,
    max_attempts=5,
    initial_backoff_seconds=1.0,
    observability=observability_context
)
```

### With Outbox Integration

```python
# Store in outbox first
outbox.store_event(task_id, event)

# Attempt delivery with retry
result = client.publish_event_with_retry_result(task_id, event)

if result.response:
    # Success - acknowledge in outbox
    outbox.acknowledge_event(task_id, event["eventId"])
else:
    # Failed - event remains in outbox for recovery
    logger.error(f"Event delivery failed: {result.final_error}")
```

### Metrics Monitoring

```python
# Get delivery metrics
metrics = client.get_event_delivery_metrics()
print(f"Success rate: {metrics['successRate']}%")
print(f"Circuit breaker state: {metrics['circuitBreakerState']}")

# Reset metrics (useful for testing)
client.reset_metrics()
```

## Testing

### Property-Based Tests

The implementation includes comprehensive property-based tests that validate:

- **Property 4**: Event Delivery Retry with Backoff
- Exponential backoff timing accuracy
- Maximum attempt enforcement
- Circuit breaker integration
- Non-retryable error handling
- Metrics tracking accuracy

### Test Coverage

```bash
# Run retry-specific tests
python -m pytest tests/test_control_plane_client_retry.py -v

# Run all control plane client tests
python -m pytest tests/test_control_plane_client*.py -v
```

## Configuration

### Environment Variables

- `MVP_OUTBOX_BACKEND`: Backend type for outbox (redis/memory)
- `MVP_REDIS_URL`: Redis connection URL for outbox

### Client Configuration

```python
client = ControlPlaneClient(
    base_url="http://localhost:8058",
    agent_token="your-token",
    timeout_seconds=15  # Request timeout
)

# Circuit breaker is automatically configured with:
# - failure_threshold=3
# - recovery_timeout_seconds=60.0
```

## Error Handling

### Error Categories

1. **Retryable Errors**:
   - Network timeouts (`URLError`, `TimeoutError`)
   - Server errors (5xx HTTP status codes)
   - Specific client errors (408, 425, 429)

2. **Non-Retryable Errors**:
   - Client errors (4xx except 408, 425, 429)
   - Authentication failures
   - Malformed requests

3. **Circuit Breaker Errors**:
   - `CircuitBreakerOpenError` when circuit is open
   - Prevents cascade failures during outages

### Error Response

```python
result = client.publish_event_with_retry_result(task_id, event)

if not result.response:
    print(f"Delivery failed after {result.attempts} attempts")
    print(f"Total delay: {result.total_delay_seconds}s")
    print(f"Circuit breaker triggered: {result.circuit_breaker_triggered}")
    print(f"Final error: {result.final_error}")
```

## Observability

### Structured Logging

All retry attempts include structured context:

```json
{
  "taskId": "task-123",
  "traceId": "trace-456", 
  "runId": "run-789",
  "eventType": "TASK_PROGRESS",
  "attempt": 2,
  "backoffSeconds": 2.0,
  "error": "Connection failed",
  "retryable": true
}
```

### Metrics Integration

The client integrates with the observability framework:

```python
# Record event publish metrics
observability.record_event_publish(event_type, attempts=attempt_count)

# Record delivery success/failure
observability.record_metric(
    "event_delivery_success_total",
    1,
    unit="count",
    attempts=str(attempt)
)
```

## Performance Characteristics

### Timing Analysis

For maximum 5 attempts with 1s initial backoff:
- **Total Time**: ~15 seconds (1 + 2 + 4 + 8 = 15s backoff)
- **Network Time**: 5 × timeout_seconds (default 15s each)
- **Maximum Duration**: ~90 seconds total

### Resource Usage

- **Memory**: Minimal overhead for metrics and circuit breaker state
- **CPU**: Low impact from exponential backoff calculations
- **Network**: Efficient retry pattern prevents overwhelming servers

## Integration Points

### Task 3.1 Integration (Redis Outbox)
- Events stored before delivery attempts
- Failed events remain for recovery
- Successful deliveries acknowledged

### Task 3.3 Integration (Recovery Service)
- Background recovery uses same retry logic
- Consistent backoff patterns across components
- Shared circuit breaker state

### Observability Framework
- Structured logging with trace correlation
- Metrics collection and reporting
- Error categorization and tracking

## Compliance

This implementation fully satisfies:

- **Requirement 2.2**: Exponential backoff up to 5 attempts
- **Property 4**: Event Delivery Retry with Backoff validation
- **Circuit Breaker Integration**: Failure detection and recovery
- **Structured Logging**: Comprehensive observability
- **Metrics Tracking**: Success/failure rate monitoring

## Future Enhancements

Potential improvements for future iterations:

1. **Adaptive Backoff**: Adjust timing based on server response patterns
2. **Jitter**: Add randomization to prevent thundering herd
3. **Priority Queuing**: Different retry strategies for event types
4. **Batch Delivery**: Group events for efficiency
5. **Health Checks**: Proactive circuit breaker management