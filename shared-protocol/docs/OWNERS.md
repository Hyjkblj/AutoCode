# shared-protocol Interface Ownership

Each cross-language interface has a designated owner responsible for:
- Reviewing protocol changes
- Ensuring semantic documentation is updated
- Enforcing the change synchronization rules

## Ownership table

| Interface | Owner | Semantic doc |
|-----------|-------|-------------|
| `EventAckResponse` | control-plane team | [event_ack_response.md](semantics/event_ack_response.md) |
| `AckErrorCode` | control-plane team | [event_ack_response.md](semantics/event_ack_response.md) |
| `TaskEvent` | control-plane team | [task_event.md](semantics/task_event.md) |
| `EventType` | control-plane team | [task_event.md](semantics/task_event.md) |
| `CreateTaskRequest` | control-plane team | — |
| `TaskSummary` | control-plane team | — |
| `ApprovalDecision` | control-plane team | — |
| `ApprovalContext` | control-plane team | — |
| `ArtifactManifest` | artifact-service team | — |
| `ArtifactMetadata` | artifact-service team | — |
| `ServiceRuntimeDescriptor` | control-plane team | — |
| `ToolManifest` | control-plane team | — |
| `SandboxExecute*` | sandbox team | — |
| `SandboxHealthResponse` | sandbox team | — |
| Event payloads (`*Payload`) | control-plane team | [task_event.md](semantics/task_event.md) |

## Change synchronization rules

When modifying any interface in `shared-protocol`, the following **four artifacts must be updated together** in the same PR:

1. **Java DTO** — the source class in `com.autocode.protocol.model.*` or `com.autocode.protocol.payload.*`
2. **JSON Schema** — the schema file in `src/main/resources/schema/`
3. **Example** — the example JSON in `src/main/resources/examples/` (and mirrored in `src/test/resources/examples/`)
4. **Semantic doc** — the markdown file in `docs/semantics/` (if one exists for the interface)

If a semantic doc does not yet exist for the interface being changed, one must be created as part of the PR.

### PR checklist

Add this checklist to any PR that touches `shared-protocol`:

```
## Protocol change checklist
- [ ] Java DTO updated
- [ ] JSON Schema updated (if applicable)
- [ ] Example JSON updated (if applicable)
- [ ] Semantic doc updated or created (if applicable)
- [ ] Contract validator updated (if new required field)
- [ ] COMPATIBILITY.md updated (if backward compatibility rules change)
```

## Hotfix exemption

In emergency situations, a protocol change may be shipped without all four artifacts **only if**:

1. The PR description explicitly states: `HOTFIX: semantic doc deferred`
2. The reason for deferral is documented
3. A follow-up issue is created to补全 the missing artifact within 48 hours
4. The PR is approved by the interface owner

Hotfix exemptions are auditable via git log — search for `HOTFIX: semantic doc deferred` to find deferred items.
