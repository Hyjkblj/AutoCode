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
- `APPROVAL_REQUIRED` requires `approvalId` + `context` (strong-binding context fields stay mandatory).
  - Runtime-aligned optional fields include `action`, `tool`, `command`, `cwd`, `workspaceRef`,
    `approvalTimeoutSeconds`, `riskScore`, `requiredPolicies`, and `toolVersion`.
- `APPROVAL_RESULT` requires `approvalId` + `decision`; consumers should tolerate lowercase/uppercase decision strings.
  - Runtime-aligned optional fields include `waitMs` (approval wait duration in milliseconds).
- `TOOL_START` keeps `tool` as the only required payload key (other fields like `action`/`command`/`cwd` are optional).
  - Runtime-aligned optional fields include `workspaceRef`, `intentSkill`, and `intentRoute`.
- `TOOL_END` requires `tool` + `status`; output/error/exitCode remain optional for compatibility.
- `BUILD_LOG` requires `message`; `buildId`/`level` are optional in v1.
- `FILE_PATCH_PREVIEW` requires at least one of `patch` or `files` (either representation is valid in v1).
- `SPEC_PROPOSED` supports optional nl2web intent hints: `target`, `templateId`, `exportMode`.
- `FILE_PATCH_PREVIEW` supports optional nl2web intent hints: `target`, `templateId`, `exportMode`.
- `ARTIFACT_READY` supports optional nl2web intent hints: `target`, `templateId`, `exportMode`.
- `TASK_DONE` requires `result`; additional completion metadata remains optional.
  - LLM/orchestrator optional fields include `intent`, `planName`, `steps`, `reviewApproved`, `reviewSummary`,
    `testStatus`, `testAttempts`, `testRetries`, `attempt`, `maxAttempts`.
- `TASK_FAILED` requires `reason`; additional diagnostics (status/detail/errorCode/exitCode/traceId/runId) are optional.
  - Orchestrator optional fields include `planName`.
  - LLM/fix-loop optional fields are supported in v1: `attempt`, `maxAttempts`, `lastTestError`,
    `riskLevel`, `issues`, `summary`.
- `TASK_CREATED` requires `projectId`; `assistant`/`riskPolicy` remain optional in v1.
- `TASK_STARTED` requires `nodeId`; additional lease/runtime metadata remains optional.
- `ASSISTANT_OUTPUT` requires `message`; `stage`/`command`/`traceId`/`runId` are optional.
  - LLM optional fields are supported in v1: `intent`, `confidence`, `reason`, `llmFallback`.
  - Review/fix-loop optional fields are supported in v1: `riskLevel`, `issues`, `summary`,
    `attempt`, `maxAttempts`, `lastTestError`.
- `HEARTBEAT` requires `payload` object only; all current keys (`nodeId`/`status`/`uptimeMs`) are optional for compatibility.
- `DEPLOY_PLAN` captures a normalized deployment request (required keys: `requestId`, `environment`, `artifact`).
  - Runtime-aligned optional fields include `traceId` and `runId`.
- `DEPLOY_RESULT` reports execution outcome (required keys: `requestId`, `status`).
  - Runtime-aligned optional fields include `traceId` and `runId`.

## Backward compatibility rules

- Adding fields is allowed if the new field is **optional** and has no semantic effect when absent.
- Removing or renaming fields is not allowed in the same major protocol version.
- Changing an existing field's meaning is not allowed.
- For `TaskEvent.payload` (a `Map<String, Object>`), producers should follow the JSON Schemas in
  `src/main/resources/schema/events/v1/` for event-specific required keys.
- For deploy events in v1, statuses/strategy values are intentionally open strings; consumers should tolerate
  unknown values and only enforce documented required keys.
- Tool manifests (`ToolManifest`/`ToolParamSpec`/`ToolPermissions`) are versioned by `ToolManifest.version`; runtime
  registries may keep multiple versions and resolve latest when no explicit version is requested.
- Tool manifests use `src/main/resources/schema/manifest/v1/tool_manifest.v1.schema.json`; required keys are
  `name`, `version`, and `action`, while additive optional fields remain v1-compatible.
- Standalone manifests (multi-artifact exports) use `src/main/resources/schema/manifest/v1/`; `schemaVersion = 1`
  matches the same compatibility rules as event payloads (optional additive fields only).
- Sandbox execute HTTP DTOs use `src/main/resources/schema/sandbox/v1/`; required request keys are `taskId` and
  `command`, and required response keys are `ok`, `status`, `retryable`.
- Sandbox health/error HTTP DTOs also use `src/main/resources/schema/sandbox/v1/`; health requires `ok` + `status`,
  and error responses require `ok` + `status` + `error`.
  - `sandbox_health_response.v1` fixes `ok = true`; `sandbox_error_response.v1` fixes `ok = false`.
- Sandbox tools HTTP DTOs use `src/main/resources/schema/sandbox/v1/sandbox_tools_response.v1.schema.json`;
  response requires `ok = true` and `tools[]`, where each tool entry follows `ToolManifest` v1 schema.
- For `ArtifactMetadata.build`: the `build` object is optional; when present, `command` is required (JSON Schema and
  `ArtifactMetadataContractValidator` agree). `ArtifactManifest` lists must not contain duplicate `artifactId` values.
  - For nl2web contracts, `fileName`/`sha256`/`mimeType` are alias fields to legacy `name`/`hash`/`mime`.
    Producers may send either set, and consumers should tolerate both.
- `CreateTaskRequest.intent` includes optional nl2web input fields: `target`, `templateId`, `exportMode`.
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

`com.autocode.protocol.validation.ToolManifestContractValidator` validates `ToolManifest` documents (v1) for required fields
(`name`/`version`/`action`), param shape, and permission constraints (for example `riskScore` in `[0,1]`).

`com.autocode.protocol.validation.SandboxExecuteContractValidator` validates sandbox execute request/response documents
(v1) using minimal required-field checks for cross-language compatibility.

`com.autocode.protocol.validation.SandboxHttpContractValidator` validates sandbox health/error/tools response documents
(v1) using the same minimal required-field approach.
