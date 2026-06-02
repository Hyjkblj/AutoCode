# Redis-based Persistent Outbox

This module implements the outbox pattern using Redis for reliable event delivery in the Python Agent. It ensures events are persisted before delivery attempts and can survive system restarts and failures.

## Overview

The outbox pattern is a critical component for achieving reliable event delivery in distributed systems. This implementation provides:

- **Event Persistence**: Events are stored in Redis before delivery attempts
- **JSON Schema Validation**: All events are validated against a strict schema
- **Atomic Operations**: Redis transactions ensure data consistency
- **Recovery Support**: Undelivered events are recovered after system restart
- **Sequence Management**: Maintains event ordering per task
- **Fallback Support**: Falls back to in-memory storage if Redis is unavailable

## Requirements Satisfied

This implementation satisfies **Requirement 2.1** from the Backend Upgrade 2.0 specification:

> "WHEN an event is published, THE Event_Outbox SHALL persist it to Redis before attempting delivery"

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   BaseAgent     │    │   RedisOutbox   │    │ Control Plane   │
│                 │    │                 │    │                 │
│ 1. Build Event  │───▶│ 2. Persist      │    │                 │
│                 │    │    to Redis     │    │                 │
│ 3. Deliver      │────┼─────────────────┼───▶│ 4. Process      │
│    Event        │    │                 │    │    Event        │
│                 │    │                 │◀───│                 │
│ 5. Acknowledge  │───▶│ 6. Remove from  │    │                 │
│    Success      │    │    Outbox       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Key Components

### RedisOutbox Class

The main class that implements the persistent outbox pattern:

```python
from outbox.redis_outbox import RedisOutbox

# Create outbox with Redis backend
outbox = RedisOutbox(
    backend="redis",
    redis_url="redis://localhost:6379/0",
    namespace="autocode:outbox",
    ttl_seconds=86400  # 24 hours
)

# Store event before delivery
outbox.store_event(task_id, event)

# Acknowledge successful delivery
outbox.acknowledge_event(task_id, event_id)

# Get pending events for recovery
pending = outbox.get_pending_events(task_id)
```

### Event Schema

All events must conform to this JSON schema:

```json
{
  "type": "object",
  "required": ["eventId", "eventVersion", "taskId", "assistant", "type", "timestamp", "seq", "payload"],
  "properties": {
    "eventId": {"type": "string", "pattern": "^evt_[a-f0-9]{32}$"},
    "eventVersion": {"type": "integer", "minimum": 1},
    "taskId": {"type": "string", "minLength": 1},
    "assistant": {"type": "string", "minLength": 1},
    "type": {"type": "string", "minLength": 1},
    "timestamp": {"type": "string", "format": "date-time"},
    "seq": {"type": "integer", "minimum": 0},
    "payload": {"type": "object"},
    "sessionId": {"type": "string"}  // optional
  }
}
```

### PersistentBaseAgent

Enhanced BaseAgent that integrates with RedisOutbox:

```python
from outbox.integration_example import PersistentBaseAgent

class MyAgent(PersistentBaseAgent):
    def handle_task(self, task, client):
        # Events are automatically persisted before delivery
        self.publish_event(task, client, "TASK_STARTED", {"message": "Started"})
        
        # Do work...
        
        self.publish_event(task, client, "TASK_DONE", {"result": "success"})
        
        # Clean up outbox data
        self.cleanup_completed_task(task["taskId"])
```

## Configuration

### Environment Variables

- `MVP_OUTBOX_BACKEND`: Backend type ("redis" or "memory")
- `MVP_REDIS_URL`: Redis connection URL (default: "redis://127.0.0.1:6379/0")

### Redis Configuration

The outbox uses the following Redis data structures:

- **Events**: `{namespace}:events:{task_id}` - List of pending events
- **Sequences**: `{namespace}:seq:{task_id}` - Sequence counter per task

### TTL Management

All outbox data has a configurable TTL (default 24 hours) to prevent unbounded growth.

## Usage Patterns

### Basic Usage

```python
from outbox.redis_outbox import RedisOutbox

outbox = RedisOutbox()

# Store event
event = {
    "eventId": "evt_" + uuid4().hex,
    "eventVersion": 1,
    "taskId": "task_123",
    "assistant": "ai-agent",
    "type": "TASK_STARTED",
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "seq": 0,
    "payload": {"message": "Task started"}
}

outbox.store_event("task_123", event)

# Attempt delivery...
# On success:
outbox.acknowledge_event("task_123", event["eventId"])
```

### Recovery After Restart

```python
# During agent startup
outbox = RedisOutbox()
pending_tasks = outbox.get_all_pending_tasks()

for task_id in pending_tasks:
    pending_events = outbox.get_pending_events(task_id)
    for event in pending_events:
        try:
            # Retry delivery
            client.publish_event(task_id, event)
            outbox.acknowledge_event(task_id, event["eventId"])
        except Exception:
            # Keep in outbox for next retry
            continue
```

### Integration with BaseAgent

```python
from outbox.integration_example import PersistentBaseAgent

class MyAgent(PersistentBaseAgent):
    def __init__(self):
        outbox = RedisOutbox(namespace="myagent:outbox")
        super().__init__(outbox=outbox)
    
    def handle_task(self, task, client):
        # Automatic recovery of pending events
        # Automatic persistence before delivery
        # Automatic acknowledgment on success
        self.publish_event(task, client, "TASK_STARTED", {})
```

## Error Handling

### Validation Errors

```python
from outbox.redis_outbox import EventValidationError

try:
    outbox.store_event(task_id, invalid_event)
except EventValidationError as e:
    print(f"Event validation failed: {e}")
```

### Redis Failures

The outbox automatically falls back to in-memory storage if Redis is unavailable:

```python
# Will use Redis if available, memory otherwise
outbox = RedisOutbox(backend="redis")

# Force memory backend for testing
outbox = RedisOutbox(backend="memory")
```

## Testing

### Unit Tests

```bash
cd python-agent
python -m pytest tests/test_redis_outbox.py -v
```

### Property-Based Tests

```bash
cd python-agent
python -m pytest tests/test_redis_outbox_properties.py -v
```

### Integration Example

```bash
cd python-agent
python -m outbox.integration_example
```

## Performance Considerations

### Redis Operations

- **Store Event**: O(1) - Single RPUSH operation
- **Acknowledge Event**: O(n) - Where n is number of pending events for task
- **Get Pending**: O(n) - Where n is number of pending events for task
- **Recovery**: O(m*n) - Where m is number of tasks, n is average events per task

### Memory Usage

- Each event consumes ~1-2KB in Redis (depending on payload size)
- TTL ensures automatic cleanup of old data
- Local fallback uses minimal memory for small event counts

### Optimization Tips

1. **Batch Operations**: Group multiple events when possible
2. **TTL Tuning**: Adjust TTL based on your recovery requirements
3. **Namespace Isolation**: Use different namespaces for different agent types
4. **Monitoring**: Monitor Redis memory usage and event counts

## Monitoring

### Key Metrics

- Number of pending events per task
- Event delivery success/failure rates
- Redis connection health
- Outbox storage usage

### Logging

The outbox logs important events:

- Event storage operations
- Validation failures
- Redis connection issues
- Recovery operations

## Security Considerations

### Data Protection

- Events may contain sensitive data - ensure Redis is properly secured
- Use Redis AUTH and TLS for production deployments
- Consider encryption for sensitive payload data

### Access Control

- Limit Redis access to authorized agents only
- Use separate Redis databases/namespaces for different environments
- Implement proper network security for Redis connections

## Migration Guide

### From In-Memory Outbox

1. Install jsonschema dependency: `pip install jsonschema>=4.0.0`
2. Replace BaseAgent with PersistentBaseAgent
3. Configure Redis connection
4. Test with memory backend first
5. Deploy with Redis backend

### Configuration Changes

```python
# Old (in-memory)
class MyAgent(BaseAgent):
    pass

# New (persistent)
from outbox.redis_outbox import RedisOutbox
from outbox.integration_example import PersistentBaseAgent

class MyAgent(PersistentBaseAgent):
    def __init__(self):
        outbox = RedisOutbox(namespace="myagent:outbox")
        super().__init__(outbox=outbox)
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify connection URL and credentials
   - Check network connectivity

2. **Event Validation Failed**
   - Verify event structure matches schema
   - Check eventId format (must start with "evt_")
   - Ensure all required fields are present

3. **Events Not Acknowledged**
   - Check Control Plane is responding
   - Verify event delivery logic
   - Check for network issues

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

outbox = RedisOutbox()
# Debug information will be logged
```

## Future Enhancements

- **Batch Operations**: Support for batch event storage and acknowledgment
- **Compression**: Optional compression for large event payloads
- **Encryption**: Built-in encryption for sensitive event data
- **Metrics**: Built-in Prometheus metrics for monitoring
- **Dead Letter Queue**: Automatic handling of permanently failed events

## Related Components

### Event Recovery Service

The Event Recovery Service (`recovery_service.py`) provides automatic recovery of unacknowledged events after Python Agent restart:

```python
from outbox.recovery_service import EventRecoveryService, RecoveryConfig

# Create recovery service
config = RecoveryConfig(
    enabled=True,
    startup_delay_seconds=2.0,
    max_retry_attempts=3,
    sequence_gap_detection=True
)

recovery_service = EventRecoveryService(
    outbox=outbox,
    client=client,
    config=config
)

# Perform recovery on startup
stats = recovery_service.recover_events_now()
print(f"Recovered {stats.successful_deliveries} events")
```

**Key Features:**
- Automatic event recovery on Python Agent restart
- Sequence continuity validation and gap detection
- Integration with enhanced client retry logic
- Background service with graceful shutdown
- Comprehensive metrics and structured logging

See [RECOVERY_SERVICE.md](RECOVERY_SERVICE.md) for detailed documentation.

### Enhanced Agent Runner

The Enhanced Agent Runner (`runner_with_recovery.py`) integrates the recovery service with the agent lifecycle:

```python
from runner_with_recovery import EnhancedAgentRunner, EnhancedRunnerConfig

config = EnhancedRunnerConfig(
    base_url="http://localhost:8058",
    node_id="ai-node-1",
    agent_token="token",
    recovery_enabled=True,
    recovery_startup_delay_seconds=2.0,
)

runner = EnhancedAgentRunner(client=client, config=config, agent=agent)
runner.run_forever()  # Includes automatic recovery on startup
```

**Requirements Satisfied:**
- ✅ **Requirement 2.3**: Event recovery after Python Agent restart
- ✅ **Requirement 2.6**: Event sequence continuity across restarts
- ✅ **Property 5**: Event Recovery After Restart validation
- ✅ **Property 8**: Event Sequence Continuity validation