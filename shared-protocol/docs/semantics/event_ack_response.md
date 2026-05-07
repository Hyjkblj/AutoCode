# EventAckResponse — Semantic Contract

**Interface**: `com.autocode.protocol.model.EventAckResponse`
**Owner**: control-plane team
**Since**: eventVersion 1
**Consumers**: python-agent, pc-agent-java, event-service

---

## Business meaning

`EventAckResponse` is the **sole acknowledgment** returned to an agent after it publishes a `TaskEvent`.

It answers three questions:

1. **Was the event accepted?** (`accepted`) — If `false`, the agent must NOT retry for the same `eventId` unless `errorCode` is retryable.
2. **Was it a duplicate?** (`duplicate`) — If `true`, the event was already processed. The agent should treat this as success.
3. **What sequence number was assigned?** (`seq`) — The monotonic sequence for this event within the task. Agents may use this for gap detection, but the control plane is the source of truth.

## Field semantics

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `seq` | long | yes | Monotonic sequence number assigned to this event within the task. 0 when event is rejected. |
| `accepted` | boolean | yes | `true` = event was persisted (may be duplicate). `false` = event was rejected. |
| `duplicate` | boolean | yes | `true` = eventId was already seen. `accepted` is also `true` in this case. |
| `errorCode` | string\|null | no | Present only when `accepted=false`. One of `AckErrorCode` values. |

## State machine

```
                 ┌─────────────────────────────────────────┐
                 │           EventAckResponse               │
                 ├─────────────────────────────────────────┤
 accepted=true   │  duplicate=false  → first-time accepted  │
                 │  duplicate=true   → duplicate (idempotent)│
                 ├─────────────────────────────────────────┤
 accepted=false  │  errorCode=XXX    → rejected, see code    │
                 └─────────────────────────────────────────┘
```

## Error codes (AckErrorCode)

| Code | Retryable | Meaning |
|------|-----------|---------|
| `MISSING_EVENT_ID` | no | eventId was null or blank |
| `NODE_NOT_REGISTERED` | no | nodeId not found in registry |
| `INVALID_NODE_ID` | no | nodeId was blank after trim |
| `TASK_NOT_FOUND` | no | taskId does not exist |
| `ACCESS_DENIED` | no | auth failed for this task |
| `INVALID_EVENT` | no | event structure invalid |
| `ILLEGAL_STATE_TRANSITION` | no | event type not allowed in current task state |
| `PROCESSING_ERROR` | yes | transient server error, safe to retry |

## Agent behavior contract

- On `accepted=true`: mark event as delivered. Do NOT resend.
- On `accepted=true, duplicate=true`: mark event as delivered. Log duplicate for observability.
- On `accepted=false, errorCode in NON_RETRYABLE_ACK_ERRORS`: mark event as failed. Do NOT retry.
- On `accepted=false, errorCode=PROCESSING_ERROR`: retry with exponential backoff.
- On `accepted=false, errorCode=null`: treat as PROCESSING_ERROR (retryable).

## JSON wire format

```json
{
  "ok": true,
  "payload": {
    "seq": 42,
    "accepted": true,
    "duplicate": false,
    "errorCode": null
  }
}
```

Note: The control plane wraps this in `ApiResponse<EventAckResponse>` with `ok`/`payload`/`error` envelope.
The agent should read `payload` for the ACK fields.
