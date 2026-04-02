# shared-protocol compatibility policy

This module is the single source of truth for cross-component DTOs and event schemas.

## Versioning

- `TaskEvent.eventVersion` is a **protocol contract version** for the event envelope and payload shapes.
- Current: **eventVersion = 1**

## New `TaskEvent.type` values under `eventVersion = 1`

- Add a JSON Schema under `src/main/resources/schema/events/v1/` and an example under
  `src/main/resources/examples/` (mirror the same file name under `src/test/resources/examples/` for contract tests).
- Extend `com.autocode.protocol.validation.TaskEventContractValidator` **only when** the platform must reject malformed
  payloads for that type; types that fall through the `default` branch rely on schema/documentation only.
- Prefer **optional** payload fields so existing consumers keep working when they ignore unknown keys.

## Backward compatibility rules

- Adding fields is allowed if the new field is **optional** and has no semantic effect when absent.
- Removing or renaming fields is not allowed in the same major protocol version.
- Changing an existing field's meaning is not allowed.
- For `TaskEvent.payload` (a `Map<String, Object>`), producers should follow the JSON Schemas in
  `src/main/resources/schema/events/v1/` for event-specific required keys.
- Standalone manifests (multi-artifact exports) use `src/main/resources/schema/manifest/v1/`; `schemaVersion = 1`
  matches the same compatibility rules as event payloads (optional additive fields only).
- For `ArtifactMetadata.build`: the `build` object is optional; when present, `command` is required (JSON Schema and
  `ArtifactMetadataContractValidator` agree). `ArtifactManifest` lists must not contain duplicate `artifactId` values.
- Service runtime descriptions (ports, health checks, env hints, startup) use `src/main/resources/schema/runtime/v1/`;
  `schemaVersion = 1` follows the same optional-additive rules.

## Payload DTOs and schema

The payload Java DTOs in `com.autocode.protocol.payload.*` are **canonical shapes** for producers/consumers, while
the JSON Schemas are the language-neutral source for validation and documentation.

Examples in `src/main/resources/examples/*.json` should stay copy-paste valid; contract tests typically duplicate the same
file name under `src/test/resources/examples/` (often with test-specific ids) so CI exercises deserialization + validators.

## Validation

`com.autocode.protocol.validation.TaskEventContractValidator` performs lightweight required-field checks for the
platform's key event types (v1). It is intended to be used by both control plane and runners before emitting/accepting events.

`com.autocode.protocol.validation.ArtifactManifestContractValidator` validates `ArtifactManifest` documents (v1) using the
same minimal required-field approach.

`com.autocode.protocol.validation.ServiceRuntimeDescriptorContractValidator` validates `ServiceRuntimeDescriptor` documents (v1).

