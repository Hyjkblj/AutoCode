# TaskEvent — Semantic Contract

**Interface**: `com.autocode.protocol.model.TaskEvent`
**Owner**: control-plane team
**Since**: eventVersion 1
**Producers**: python-agent, pc-agent-java
**Consumers**: control-plane-spring, event-service

---

## Business meaning

`TaskEvent` is the **fundamental unit of communication** between agents and the control plane. Every state change, progress update, artifact notification, and error report flows through a `TaskEvent`.

The control plane uses events to:
- Drive the task state machine (QUEUED → RUNNING → DONE/FAILED/CANCELED)
- Record audit trail of what happened during task execution
- Trigger downstream actions (artifact hosting, approval flows, notifications)

## Field semantics

| Field | Type | Required | Meaning |
|-------|------|----------|---------|
| `eventId` | string | yes | Globally unique ID (e.g. `evt_<uuid>`). Used for deduplication. |
| `taskId` | string | yes | The task this event belongs to. Must match an existing task. |
| `sessionId` | string | no | Execution session identifier. Groups events from a single agent run. |
| `assistant` | string | no | Agent identity (e.g. `coder`, `reviewer`). |
| `type` | EventType | yes | The event type. Determines payload schema and state transition. |
| `timestamp` | Instant | yes | When the event occurred on the agent. ISO-8601. |
| `payload` | Map | yes | Type-specific data. Schema varies by `type`. |
| `seq` | long | no | Agent-side sequence number. Control plane reassigns on ingest. |
| `eventVersion` | int | yes | Protocol version. Current: 1. |

## Event types and state transitions

| EventType | From states | To state | Required payload keys |
|-----------|-------------|----------|----------------------|
| `TASK_CREATED` | (none) | QUEUED | `projectId` |
| `TASK_STARTED` | QUEUED | RUNNING | `nodeId` |
| `TASK_DONE` | RUNNING | DONE | `result` |
| `TASK_FAILED` | RUNNING | FAILED | `reason` |
| `HEARTBEAT` | any (informational) | — | (none) |
| `ASSISTANT_OUTPUT` | any active | — | `message` |
| `TOOL_START` | any active | — | `tool` |
| `TOOL_END` | any active | — | `tool`, `status` |
| `FILE_PATCH_PREVIEW` | any active | — | `patch` or `files` |
| `SPEC_PROPOSED` | any active | — | `artifact` |
| `ARTIFACT_READY` | any active | — | (none) |
| `BUILD_STARTED` | any active | — | (none) |
| `BUILD_LOG` | any active | — | `message` |
| `BUILD_DONE` | any active | — | (none) |
| `APPROVAL_REQUIRED` | any active | — | `approvalId`, `context` |
| `APPROVAL_RESULT` | any active | — | `approvalId`, `decision` |
| `DEPLOY_PLAN` | any active | — | `requestId`, `environment`, `artifact` |
| `DEPLOY_RESULT` | any active | — | `requestId`, `status` |

## Deduplication

Events are deduplicated by `eventId`:
1. **Redis fast path**: `event:dedup:{eventId}` key with 24h TTL
2. **DB reliable path**: `task_events` table unique constraint on `eventId`

When a duplicate is detected, the control plane returns `EventAckResponse.duplicate(seq)` with the original sequence number.

## Ordering

- `seq` assigned by the control plane is the **canonical order** within a task.
- Agent-side `seq` values are informational only and may be reassigned.
- Events with `eventVersion > 1` must be rejected by the control plane until it is upgraded.

## JSON wire format

```json
{
  "event": {
    "eventId": "evt_abc123",
    "taskId": "tsk_xyz",
    "sessionId": "sess_001",
    "assistant": "coder",
    "type": "TASK_STARTED",
    "timestamp": "2026-05-07T10:30:00Z",
    "payload": {
      "nodeId": "node_001"
    },
    "seq": 1,
    "eventVersion": 1
  }
}
```

Note: The agent wraps this in `AgentEventRequest` with an `event` field when calling `POST /api/v1/events/ingest`.
