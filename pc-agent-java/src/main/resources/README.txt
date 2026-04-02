# MVP agent config uses environment variables:
# MVP_BASE_URL=http://localhost:8080
# MVP_NODE_ID=node-local-1
# MVP_AGENT_TOKEN=agent-dev-token
# MVP_POLL_INTERVAL_MS=1500
# MVP_HEARTBEAT_INTERVAL_MS=10000
# MVP_APPROVAL_TIMEOUT_SECONDS=120
# MVP_ALLOWED_COMMAND_PREFIXES=git status,git diff,mvn test,npm test,gradle test
# Optional after successful command.exec: upload file(s) then emit ARTIFACT_READY (paths must match MVP_ALLOWED_WORKSPACE_PREFIXES when set)
# MVP_POST_SUCCESS_ARTIFACT_PATH=target/dist.zip
# MVP_POST_SUCCESS_ARTIFACT_PATHS=target/a.zip,target/b.zip
# MVP_ARTIFACT_LOGICAL_NAME=dist
# MVP_ARTIFACT_UPLOAD_MAX_BYTES=268435456
