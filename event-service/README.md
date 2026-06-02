# Event Service

Standalone Spring Boot microservice for event processing, deduplication, and ACK protocol.

## Overview

The Event Service is an independent microservice extracted from the Control Plane as part of the Java microservices decomposition strategy (Requirement 11.1). It handles:

- **Event Processing**: Receives and persists events from Python agents
- **Event Deduplication**: Redis-based duplicate detection (Requirement 2.5)
- **ACK Protocol**: Explicit acknowledgment with sequence numbers (Requirement 2.4)
- **Sequence Continuity**: Maintains event ordering across restarts (Requirement 2.6)

## Architecture

### Service Boundaries

The Event Service owns:
- Event persistence (MySQL database)
- Event deduplication state (Redis)
- Event ACK protocol implementation
- Event sequence management

### Data Ownership

- **Database**: `event_db` (MySQL)
  - Table: `events` - stores all event records
- **Redis**: Event deduplication keys
  - `event:dedup:{eventId}` - marks processed events
  - `event:seq:{eventId}` - stores original sequence numbers

## API Endpoints

### POST /events/ingest

Ingest an event with ACK protocol.

**Parameters:**
- `taskId` (required): Task identifier
- `nodeId` (optional): Agent node identifier

**Request Body:**
```json
{
  "event": {
    "eventId": "evt_123",
    "taskId": "task_456",
    "sessionId": "session_789",
    "assistant": "coder",
    "type": "TASK_STARTED",
    "timestamp": "2024-01-01T00:00:00Z",
    "payload": {},
    "seq": 1,
    "eventVersion": 1
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "seq": 1,
    "accepted": true,
    "duplicate": false,
    "errorCode": null
  }
}
```

**Error Codes:**
- `MISSING_EVENT_ID`: Event ID is null or blank
- `MISSING_EVENT_DATA`: Event data is missing from request
- `INVALID_NODE_ID`: Node ID is blank
- `PROCESSING_ERROR`: Internal processing error
- `PAYLOAD_SERIALIZATION_ERROR`: Failed to serialize payload

### GET /events/task/{taskId}

Retrieve all events for a specific task.

**Response:**
```json
{
  "success": true,
  "taskId": "task_456",
  "count": 5,
  "events": [...]
}
```

### GET /events/health

Health check endpoint.

**Response:**
```json
{
  "success": true,
  "status": "healthy",
  "message": "Event processing healthy"
}
```

## Configuration

### Environment Variables

- `EVENT_DB_URL`: MySQL database URL (default: `jdbc:mysql://localhost:3306/event_db`)
- `EVENT_DB_USER`: Database username (default: `root`)
- `EVENT_DB_PASSWORD`: Database password (default: empty)
- `EVENT_REDIS_HOST`: Redis host (default: `localhost`)
- `EVENT_REDIS_PORT`: Redis port (default: `6379`)
- `EVENT_REDIS_PASSWORD`: Redis password (default: `changeme`)
- `EVENT_DEDUP_TTL_HOURS`: Deduplication TTL in hours (default: `24`)
- `CONTROL_PLANE_URL`: Control Plane URL for service-to-service communication (default: `http://localhost:8058`)

### Port

The service runs on port **8082** by default.

## Running the Service

### Standalone

```bash
cd event-service
mvn spring-boot:run
```

### Docker Compose

The service is integrated into the main `docker-compose.yml` file.

```bash
docker-compose up event-service
```

## Database Schema

### events table

| Column | Type | Description |
|--------|------|-------------|
| event_id | VARCHAR(64) | Primary key, unique event identifier |
| task_id | VARCHAR(64) | Associated task identifier |
| session_id | VARCHAR(64) | Session identifier |
| assistant | VARCHAR(64) | Assistant/agent identifier |
| event_type | VARCHAR(64) | Type of event |
| event_timestamp | TIMESTAMP | Event occurrence time |
| payload_json | TEXT | Event payload as JSON |
| seq_num | BIGINT | Sequence number |
| event_version | INT | Event schema version |
| created_at | TIMESTAMP | Record creation time |
| node_id | VARCHAR(64) | Optional node identifier |

**Indexes:**
- `idx_events_task_seq` on (task_id, seq_num)
- `idx_events_timestamp` on (event_timestamp)

## Redis Keys

### Deduplication Keys

- **Pattern**: `event:dedup:{eventId}`
- **Value**: `"processed"`
- **TTL**: 24 hours (configurable)
- **Purpose**: Mark events as processed

### Sequence Keys

- **Pattern**: `event:seq:{eventId}`
- **Value**: Sequence number as string
- **TTL**: 24 hours (configurable)
- **Purpose**: Store original sequence for duplicate ACKs

## Monitoring

### Health Checks

- **Endpoint**: `/events/health`
- **Checks**: Redis connectivity
- **Actuator**: `/actuator/health` (includes database checks)

### Metrics

Prometheus metrics are exposed at `/actuator/prometheus`:

- JVM metrics
- HTTP request metrics
- Database connection pool metrics
- Redis connection metrics

### Logging

Structured logging with:
- Event IDs
- Task IDs
- Sequence numbers
- Error details

## Testing

### Unit Tests

```bash
mvn test
```

### Integration Tests

Integration tests require:
- MySQL database
- Redis instance

```bash
mvn verify
```

## Service-to-Service Communication

The Event Service is designed to be called by:
- **Python Agent**: Publishes events via `/events/ingest`
- **Control Plane**: May query events via `/events/task/{taskId}`
- **Gateway Service**: Routes requests to Event Service

## Migration from Control Plane

The Event Service was extracted from the Control Plane's event handling logic:

**Original Location:**
- `control-plane-spring/src/main/java/com/autocode/event/`

**Migration Steps:**
1. ✅ Create independent Spring Boot application
2. ✅ Migrate event processing logic
3. ✅ Migrate deduplication service
4. ✅ Set up independent database
5. ⏳ Update Python Agent to call Event Service
6. ⏳ Update Gateway to route to Event Service
7. ⏳ Implement canary deployment
8. ⏳ Remove event logic from Control Plane

## Requirements Validation

This service implements:

- **Requirement 2.4**: Event ACK Protocol Compliance
  - Explicit ACK responses with sequence numbers
  - Acceptance status indication
  - Proper error handling and codes

- **Requirement 2.5**: Event Deduplication
  - Redis-based duplicate detection
  - Sequence number preservation for duplicates
  - TTL-based cleanup

- **Requirement 2.6**: Event Sequence Continuity
  - Maintains sequence ordering
  - Supports sequence queries

- **Requirement 11.1**: Clear Service Boundaries
  - Independent data ownership
  - Well-defined API contracts
  - Isolated deployment

## Future Enhancements

1. **Event Streaming**: Add Kafka/RabbitMQ for event streaming
2. **Event Replay**: Support for event replay and time-travel debugging
3. **Event Aggregation**: Aggregate events for analytics
4. **Circuit Breaker**: Add circuit breaker for Control Plane calls
5. **Rate Limiting**: Implement per-task rate limiting
6. **Event Validation**: Schema validation for event payloads
