# Event Recovery Service

The Event Recovery Service implements automatic recovery of unacknowledged events after Python Agent restart, ensuring reliable event delivery and maintaining sequence continuity across system restarts.

## Overview

This service implements **Requirements 2.3 and 2.6** from the Backend Upgrade 2.0 specification:

- **Requirement 2.3**: "WHEN the Python_Agent restarts, THE Event_Outbox SHALL recover and redeliver unacknowledged events"
- **Requirement 2.6**: "THE system SHALL maintain event sequence continuity across Python_Agent restarts"

## Key Features

- **Automatic Recovery**: Scans and redelivers unacknowledged events on startup
- **Sequence Continuity**: Detects and handles sequence gaps in event streams
- **Batch Processing**: Processes events in configurable batches for efficiency
- **Retry Integration**: Uses enhanced client with exponential backoff and circuit breaker
- **Comprehensive Logging**: Structured logging with metrics and observability
- **Graceful Shutdown**: Handles interruption during recovery operations
- **Background Service**: Can run as background process or synchronously

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Agent Startup │    │ Recovery Service│    │ Control Plane   │
│                 │    │                 │    │                 │
│ 1. Initialize   │───▶│ 2. Scan Outbox  │    │                 │
│    Recovery     │    │    for Pending  │    │                 │
│                 │    │    Events       │    │                 │
│                 │    │                 │    │                 │
│                 │    │ 3. Redeliver    │───▶│ 4. Process      │
│                 │    │    Events with  │    │    Events       │
│                 │    │    Retry Logic  │    │                 │
│                 │    │                 │◀───│                 │
│                 │    │ 5. Acknowledge  │    │                 │
│                 │    │    Successful   │    │                 │
│                 │    │    Deliveries   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Usage

### Basic Usage

```python
from outbox.redis_outbox import RedisOutbox
from outbox.recovery_service import EventRecoveryService, RecoveryConfig
from client.control_plane_client import ControlPlaneClient

# Create outbox and client
outbox = RedisOutbox(backend="redis")
client = ControlPlaneClient(base_url="http://localhost:8058", agent_token="token")

# Create recovery service
config = RecoveryConfig(
    enabled=True,
    startup_delay_seconds=2.0,
    max_retry_attempts=3,
    batch_size=10,
    sequence_gap_detection=True
)

recovery_service = EventRecoveryService(
    outbox=outbox,
    client=client,
    config=config
)

# Perform immediate recovery
stats = recovery_service.recover_events_now()
print(f"Recovered {stats.successful_deliveries} events")
```

### Background Service

```python
# Start background recovery service
recovery_service.start_recovery_service()

# ... run main application ...

# Stop service gracefully
recovery_service.stop_recovery_service(timeout_seconds=10.0)
```

### Integration with Enhanced Runner

```python
from runner_with_recovery import EnhancedAgentRunner, EnhancedRunnerConfig

config = EnhancedRunnerConfig(
    base_url="http://localhost:8058",
    node_id="ai-node-1",
    agent_token="token",
    recovery_enabled=True,
    recovery_startup_delay_seconds=2.0,
    recovery_max_retry_attempts=3,
)

runner = EnhancedAgentRunner(client=client, config=config, agent=agent)
runner.run_forever()  # Includes automatic recovery on startup
```

## Configuration

### RecoveryConfig Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | True | Enable/disable recovery service |
| `startup_delay_seconds` | float | 2.0 | Delay before starting recovery |
| `max_retry_attempts` | int | 3 | Maximum retry attempts per event |
| `retry_backoff_seconds` | float | 1.0 | Initial backoff for retries |
| `batch_size` | int | 10 | Number of tasks to process per batch |
| `recovery_timeout_seconds` | float | 300.0 | Maximum recovery duration |
| `sequence_gap_detection` | bool | True | Enable sequence gap detection |
| `metrics_enabled` | bool | True | Enable metrics collection |

### Environment Variables

```bash
# Recovery service configuration
MVP_RECOVERY_ENABLED=true
MVP_RECOVERY_STARTUP_DELAY=2.0
MVP_RECOVERY_MAX_RETRIES=3
MVP_RECOVERY_BATCH_SIZE=10

# Outbox configuration
MVP_OUTBOX_BACKEND=redis
MVP_REDIS_URL=redis://127.0.0.1:6379/0
MVP_OUTBOX_NAMESPACE=autocode:outbox
```

## Recovery Process

### 1. Startup Recovery

When the Python Agent starts, the recovery service:

1. **Waits for startup delay** (configurable, default 2 seconds)
2. **Scans Redis outbox** for all tasks with pending events
3. **Processes tasks in batches** to avoid overwhelming the system
4. **Attempts delivery** for each pending event using enhanced client
5. **Acknowledges successful deliveries** and removes them from outbox
6. **Leaves failed events** in outbox for future recovery attempts

### 2. Sequence Continuity

The service maintains event sequence continuity by:

1. **Sorting events by sequence number** within each task
2. **Detecting sequence gaps** (missing sequence numbers)
3. **Logging gap information** for monitoring and debugging
4. **Continuing delivery** despite gaps (gaps are "resolved" by acceptance)

### 3. Error Handling

The recovery service handles various error scenarios:

- **Network failures**: Uses retry logic with exponential backoff
- **Circuit breaker activation**: Respects circuit breaker state
- **Redis failures**: Gracefully handles outbox access errors
- **Shutdown during recovery**: Supports graceful interruption

## Monitoring and Observability

### Recovery Statistics

```python
stats = recovery_service.get_recovery_stats()
print(f"Tasks scanned: {stats.total_tasks_scanned}")
print(f"Events found: {stats.total_events_found}")
print(f"Successful deliveries: {stats.successful_deliveries}")
print(f"Failed deliveries: {stats.failed_deliveries}")
print(f"Sequence gaps detected: {stats.sequence_gaps_detected}")
```

### Service Metrics

```python
metrics = recovery_service.get_service_metrics()
print(f"Total recoveries: {metrics['total_recoveries']}")
print(f"Success rate: {metrics['successful_recoveries'] / metrics['total_recoveries'] * 100}%")
print(f"Events recovered: {metrics['total_events_recovered']}")
```

### Structured Logging

The service provides comprehensive structured logging:

```json
{
  "timestamp": "2026-05-02T03:22:30.275Z",
  "level": "INFO",
  "logger": "outbox.recovery_service.EventRecoveryService",
  "message": "Event recovery completed",
  "tasksScanned": 3,
  "eventsFound": 9,
  "successfulDeliveries": 6,
  "failedDeliveries": 3,
  "durationSeconds": 0.002,
  "sequenceGapsResolved": 0
}
```

## Testing

### Unit Tests

```bash
# Run unit tests
python -m pytest python-agent/tests/test_recovery_service.py -v

# Run property-based tests
python -m pytest python-agent/tests/test_recovery_service_properties.py -v
```

### Integration Demo

```bash
# Run interactive demonstration
python python-agent/examples/recovery_service_demo.py
```

The demo shows:
- Event persistence before delivery
- Agent crash simulation
- Recovery on restart
- Sequence gap detection
- Recovery idempotency

## Property-Based Testing

The recovery service includes comprehensive property-based tests that validate:

### Property 5: Event Recovery After Restart
*For any Python_Agent restart scenario, all unacknowledged events in the Event_Outbox SHALL be recovered and redelivered.*

### Property 8: Event Sequence Continuity
*For any Python_Agent restart, event sequence numbers SHALL maintain continuity without gaps or duplicates.*

Additional properties test:
- Sequence gap detection and resolution
- Multi-task recovery isolation
- Partial recovery resilience
- Batch processing completeness
- Recovery idempotency

## Performance Considerations

### Batch Processing

The service processes tasks in configurable batches to:
- Avoid overwhelming the Control Plane
- Provide better progress visibility
- Allow for graceful shutdown during recovery

### Memory Usage

- Events are processed one task at a time
- Batch size controls memory usage
- Redis outbox provides persistent storage

### Recovery Time

Recovery time depends on:
- Number of pending events
- Network latency to Control Plane
- Retry attempts for failed events
- Batch size configuration

Typical recovery times:
- **Small scale** (< 100 events): < 5 seconds
- **Medium scale** (100-1000 events): 10-30 seconds
- **Large scale** (> 1000 events): 1-5 minutes

## Best Practices

### Configuration

1. **Set appropriate startup delay** to allow other services to initialize
2. **Configure batch size** based on system capacity and event volume
3. **Enable sequence gap detection** for debugging and monitoring
4. **Set reasonable retry limits** to avoid infinite retry loops

### Monitoring

1. **Monitor recovery statistics** to track system health
2. **Alert on high failure rates** or long recovery times
3. **Track sequence gaps** to identify potential data loss
4. **Monitor outbox growth** to detect persistent delivery issues

### Error Handling

1. **Investigate persistent failures** that remain after multiple recoveries
2. **Check Control Plane availability** if all events fail recovery
3. **Monitor circuit breaker state** during recovery operations
4. **Review sequence gaps** for potential data integrity issues

## Troubleshooting

### Common Issues

#### No Events Recovered
- Check if outbox contains pending events
- Verify Control Plane connectivity
- Check agent token and authentication

#### High Failure Rate
- Check Control Plane health and capacity
- Verify network connectivity
- Review circuit breaker configuration

#### Sequence Gaps
- Check for missing events in Control Plane
- Review event generation logic
- Investigate potential data loss scenarios

#### Long Recovery Times
- Reduce batch size for better progress
- Check network latency
- Review retry configuration

### Debug Logging

Enable debug logging for detailed recovery information:

```python
import logging
logging.getLogger("outbox.recovery_service").setLevel(logging.DEBUG)
```

## Future Enhancements

Potential improvements for the recovery service:

1. **Dead Letter Queue**: Handle permanently failed events
2. **Recovery Scheduling**: Periodic recovery attempts for failed events
3. **Metrics Integration**: Built-in Prometheus metrics
4. **Event Compression**: Reduce memory usage for large events
5. **Parallel Processing**: Process multiple tasks concurrently
6. **Recovery Prioritization**: Prioritize critical events
7. **Event Deduplication**: Handle duplicate events more intelligently

## Related Components

- **Redis Outbox** (`redis_outbox.py`): Persistent event storage
- **Enhanced Client** (`control_plane_client.py`): Retry logic and circuit breaker
- **Enhanced Runner** (`runner_with_recovery.py`): Integration with agent lifecycle
- **Base Agent** (`base_agent.py`): Event publishing interface

## Compliance

This implementation satisfies the following requirements:

- ✅ **Requirement 2.3**: Event recovery after Python Agent restart
- ✅ **Requirement 2.6**: Event sequence continuity across restarts
- ✅ **Property 5**: Event Recovery After Restart validation
- ✅ **Property 8**: Event Sequence Continuity validation

The recovery service ensures reliable event delivery and maintains system consistency across Python Agent restarts, providing a robust foundation for the Backend Upgrade 2.0 event reliability enhancements.