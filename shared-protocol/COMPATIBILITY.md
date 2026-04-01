# shared-protocol compatibility policy

This module is the single source of truth for cross-component DTOs and event schemas.

## Versioning

- `TaskEvent.eventVersion` is a **protocol contract version** for the event envelope and payload shapes.
- Current: **eventVersion = 1**

## Backward compatibility rules

- Adding fields is allowed if the new field is **optional** and has no semantic effect when absent.
- Removing or renaming fields is not allowed in the same major protocol version.
- Changing an existing field's meaning is not allowed.
- For `TaskEvent.payload` (a `Map<String, Object>`), producers should follow the JSON Schemas in
  `src/main/resources/schema/events/v1/` for event-specific required keys.

## Payload DTOs and schema

The payload Java DTOs in `com.autocode.protocol.payload.*` are **canonical shapes** for producers/consumers, while
the JSON Schemas are the language-neutral source for validation and documentation.

## Validation

`com.autocode.protocol.validation.TaskEventContractValidator` performs lightweight required-field checks for the
platform's key event types (v1). It is intended to be used by both control plane and runners before emitting/accepting events.

