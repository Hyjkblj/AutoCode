# ACK Response Handling in ControlPlaneClient

This document describes the enhanced ACK response handling implemented in Task 4.2, which provides explicit acknowledgment semantics for event delivery between the Python Agent and Control Plane.

## Overview

The Control Plane now returns explicit ACK responses for all event publications, providing:

- **Sequence Number**: Confirms the sequence number of the acknowledged event
- **Acceptance Status**: Indicates whether the event was accepted and processed
- **Duplicate Detection**: Identifies if the event was a duplicate
- **Error Codes**: Provides specific error information when events are not accepted

This implements Requirements 2.4 (Event ACK Protocol Compliance) and 2.5 (Event Deduplication).

## ACK Response Format

### Control Plane Response Structure

```json
{
  "success": true,
  "data": {
    "seq": 123,
    "accepted": true,
    "duplicate": false,
    "errorCode": null
  }
}
```

### ACK Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `seq` | integer | Sequence number of the acknowledged event |
| `accepted` | boolean | Whether the event was accepted and processed |
| `duplicate` | boolean | Whether the event was identified as a duplicate |
| `errorCode` | string\|null | Error code if not accepted (null if accepted) |

### Error Codes

#### Non-Retryable Errors
- `INVALID_NODE_ID`: Node ID format is invalid
- `NODE_NOT_REGISTERED`: Node is not registered with the Control Plane
- `MISSING_EVENT_ID`: Event is missing required eventId field
- `TASK_NOT_FOUND`: Specified task does not exist

#### Retryable Errors
- `PROCESSING_ERROR`: Temporary processing error occurred
- Other unknown errors are treated as retryable

## Enhanced Client Methods

### 1. `publish_event_with_ack()`

Returns only the ACK response data for successful deliveries.

```python
ack_response = client.publish_event_with_ack(
    task_id="task-123",
    event={
        "type": "TASK_STARTED",
        "eventId": "evt-456",
        "seq": 1,
        "timestamp": "2024-01-15T10:00:00Z",
        "payload": {"status": "started"}
    },
    max_attempts=5,
    initial_backoff_seconds=1.0,
    observability=observability_context
)

if ack_response:
    print(f"Event acknowledged: seq={ack_response['seq']}")
    if ack_response['duplicate']:
        print("Event was a duplicate")
```

### 2. `publish_event_with_retry_result()`

Returns comprehensive delivery result including ACK response.

```python
result = client.publish_event_with_retry_result(
    task_id="task-123",
    event=event_data,
    max_attempts=3
)

print(f"Delivery attempts: {result.attempts}")
print(f"Total delay: {result.total_delay_seconds}s")

if result.ack_response:
    print(f"ACK: {result.ack_response}")
if result.final_error:
    print(f"Final error: {result.final_error}")
```

### 3. `extract_ack_response()`

Extracts ACK response data from raw Control Plane response.

```python
raw_response = client.publish_event(task_id, event)
ack_response = client.extract_ack_response(raw_response)

if ack_response:
    print(f"Extracted ACK: {ack_response}")
```

### 4. `validate_ack_response()`

Validates ACK response structure and optionally checks sequence number.

```python
is_valid = client.validate_ack_response(ack_response, expected_seq=123)
if not is_valid:
    print("Invalid ACK response format")
```

## Error Handling

### Exception Handling

```python
try:
    ack_response = client.publish_event_with_ack(task_id, event)
    print(f"Success: {ack_response}")
    
except ControlPlaneRequestError as e:
    if e.retryable:
        print(f"Retryable error: {e}")
        # Could retry with different parameters
    else:
        print(f"Non-retryable error: {e}")
        # Fix the issue before retrying
```

### Error Classification

The client automatically classifies errors as retryable or non-retryable based on the ACK response error code:

- **Non-retryable**: Configuration or validation errors that won't be fixed by retrying
- **Retryable**: Temporary errors that may succeed on retry

## Duplicate Event Handling

When the Control Plane detects a duplicate event:

```python
ack_response = client.publish_event_with_ack(task_id, duplicate_event)

if ack_response and ack_response['duplicate']:
    print(f"Event was duplicate but acknowledged (seq: {ack_response['seq']})")
    # Event was already processed, no need to retry
```

## Monitoring and Metrics

### Delivery Metrics

```python
metrics = client.get_event_delivery_metrics()
print(f"Success rate: {metrics['successRate']}%")
print(f"Circuit breaker state: {metrics['circuitBreakerState']}")
```

### Structured Logging

The client provides structured logging for ACK responses:

```
INFO - Received ACK response - taskId=task-123 eventType=TASK_STARTED ackSeq=123 ackAccepted=true ackDuplicate=false
```

## Integration with Outbox Pattern

The ACK response handling integrates with the persistent outbox pattern:

1. **Event Stored**: Event is persisted to outbox before delivery attempt
2. **ACK Received**: Control Plane returns explicit ACK response
3. **Event Marked**: Event is marked as delivered in outbox based on ACK
4. **Duplicate Handling**: Duplicate ACKs are handled gracefully

## Schema Validation

The ACK response format is defined in the shared protocol schema:

```
shared-protocol/src/main/resources/schema/events/v1/event_ack.v1.schema.json
```

This ensures consistency between the Control Plane (Java) and Python Agent implementations.

## Best Practices

### 1. Always Check ACK Responses

```python
ack_response = client.publish_event_with_ack(task_id, event)
if ack_response and ack_response['accepted']:
    # Event was successfully processed
    handle_success(ack_response)
else:
    # Event was not accepted
    handle_failure(ack_response)
```

### 2. Handle Duplicates Gracefully

```python
if ack_response and ack_response['duplicate']:
    # Event was already processed - this is normal
    logger.info(f"Duplicate event acknowledged: {ack_response['seq']}")
    return  # Don't treat as error
```

### 3. Use Appropriate Retry Limits

```python
# For critical events, use more retries
critical_result = client.publish_event_with_retry_result(
    task_id, critical_event, max_attempts=5
)

# For non-critical events, fail fast
non_critical_result = client.publish_event_with_retry_result(
    task_id, status_event, max_attempts=2
)
```

### 4. Monitor Delivery Metrics

```python
# Periodically check delivery health
metrics = client.get_event_delivery_metrics()
if metrics['failureRate'] > 5.0:  # More than 5% failure rate
    logger.warning(f"High event delivery failure rate: {metrics['failureRate']}%")
```

## Migration Guide

### From Legacy Event Publishing

**Before (Legacy):**
```python
response = client.publish_event(task_id, event)
# No explicit ACK handling
```

**After (With ACK):**
```python
ack_response = client.publish_event_with_ack(task_id, event)
if ack_response and ack_response['accepted']:
    # Confirmed delivery
    pass
```

### Backward Compatibility

The existing `publish_event()` and `publish_event_with_retry()` methods continue to work but don't provide ACK response parsing. For new code, use the ACK-aware methods.

## Testing

Comprehensive tests are available in:
- `tests/test_ack_response_handling.py`: ACK response extraction and validation
- `examples/ack_response_example.py`: Usage examples and demonstrations

Run tests with:
```bash
python -m pytest tests/test_ack_response_handling.py -v
```