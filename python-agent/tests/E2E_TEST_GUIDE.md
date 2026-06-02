# End-to-End Test Guide

## Overview

The E2E test suite (`test_e2e_task_lifecycle.py`) validates the complete task lifecycle from creation through execution to artifact delivery. These tests ensure all system components work together correctly.

## Test Coverage

### Task 8.1: Complete Task Lifecycle E2E Tests

**Validates: Requirements 6.5**

The E2E test suite covers:

1. **Task Creation through Control Plane API**
   - REST API task creation
   - Task idempotency verification
   - Task state transitions (PENDING → QUEUED → LEASED → RUNNING → SUCCEEDED)

2. **Python Agent Task Polling and Execution**
   - Agent registration
   - Task polling mechanism
   - Task lease acquisition
   - Task execution workflow

3. **Event Flow from Python Agent to Control Plane**
   - Event publishing with sequence numbers
   - ACK protocol verification
   - Event deduplication
   - Event persistence and retrieval

4. **Artifact Generation and Hosting**
   - Artifact creation and packaging
   - Artifact upload to Control Plane
   - Artifact download via HTTP
   - Artifact metadata validation

## Prerequisites

### 1. Running Services

The E2E tests require the following services to be running:

```bash
# Start all required services
docker-compose --profile fullstack up -d

# Verify services are healthy
docker-compose ps
```

Required services:
- `mysql` (port 3306)
- `redis` (port 6379)
- `control-plane` (port 8058)
- `pc-agent-java` (port 18080)
- `python-agent` (running)

### 2. Environment Configuration

Create or update `.env` file with required configuration:

```bash
# Control Plane Configuration
MVP_BASE_URL=http://localhost:8058
MVP_AGENT_TOKEN=agent-dev-token

# LLM Configuration (required for generation tests)
OPENAI_API_KEY=your-openai-api-key
# OR
ARK_API_KEY=your-ark-api-key

# Database Configuration
MVP_DB_PASSWORD=changeme
MVP_REDIS_PASSWORD=changeme

# Enable E2E Tests
RUN_E2E_TESTS=1
```

### 3. Python Dependencies

Install test dependencies:

```bash
cd python-agent
pip install -r requirements.txt
pip install pytest pytest-cov
```

## Running the Tests

### Run All E2E Tests

```bash
cd python-agent
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py -v -s
```

### Run Specific Test

```bash
# Test complete task lifecycle
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py::TestE2ETaskLifecycle::test_complete_task_lifecycle_web_generation -v -s

# Test task idempotency
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py::TestE2ETaskLifecycle::test_task_idempotency -v -s

# Test event ACK protocol
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py::TestE2ETaskLifecycle::test_event_ack_protocol -v -s

# Test agent polling
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py::TestE2ETaskLifecycle::test_agent_polling_and_execution -v -s

# Test artifact hosting
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py::TestE2EArtifactHosting::test_artifact_upload_and_download -v -s
```

### Run with Coverage

```bash
cd python-agent
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py --cov=. --cov-report=html -v -s
```

## Test Scenarios

### 1. Complete Task Lifecycle (Web Generation)

**Test:** `test_complete_task_lifecycle_web_generation`

**Flow:**
1. Create task via Control Plane REST API
2. Verify task enters QUEUED state
3. Wait for Python Agent to poll and lease task
4. Verify task enters RUNNING state
5. Wait for task completion (SUCCEEDED)
6. Verify events were published (TASK_STARTED, ARTIFACT_READY)
7. Verify artifact was generated and is valid ZIP

**Expected Duration:** 60-180 seconds (includes LLM generation)

**Success Criteria:**
- Task completes with SUCCEEDED status
- All expected events are published
- Artifact contains index.html, styles.css, app.js

### 2. Task Idempotency

**Test:** `test_task_idempotency`

**Flow:**
1. Create task with idempotency key
2. Create same task again with same idempotency key
3. Verify same task ID is returned

**Expected Duration:** 2-5 seconds

**Success Criteria:**
- Both requests return same task ID
- No duplicate tasks created

### 3. Event ACK Protocol

**Test:** `test_event_ack_protocol`

**Flow:**
1. Create test task
2. Publish event to Control Plane
3. Verify ACK response contains seq, accepted, duplicate fields
4. Publish same event again
5. Verify duplicate is detected

**Expected Duration:** 2-5 seconds

**Success Criteria:**
- First event: accepted=true, duplicate=false
- Second event: accepted=true, duplicate=true

### 4. Agent Polling and Execution

**Test:** `test_agent_polling_and_execution`

**Flow:**
1. Create test task
2. Register test agent
3. Poll for task
4. Verify task is leased
5. Verify task state transitions

**Expected Duration:** 5-10 seconds

**Success Criteria:**
- Agent successfully polls task
- Task enters LEASED or RUNNING state
- Task details match created task

### 5. Artifact Upload and Download

**Test:** `test_artifact_upload_and_download`

**Flow:**
1. Create test ZIP artifact
2. Upload to Control Plane
3. Download artifact via HTTP
4. Verify content and metadata

**Expected Duration:** 2-5 seconds

**Success Criteria:**
- Upload returns artifact ID
- Download succeeds with correct Content-Type
- Downloaded data is valid ZIP

## Troubleshooting

### Tests Skip with "E2E tests require RUN_E2E_TESTS=1"

**Solution:** Set the environment variable:
```bash
export RUN_E2E_TESTS=1
```

### Connection Refused to Control Plane

**Symptoms:**
```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Solutions:**
1. Verify Control Plane is running:
   ```bash
   docker-compose ps control-plane
   curl http://localhost:8058/actuator/health
   ```

2. Check Control Plane logs:
   ```bash
   docker-compose logs control-plane
   ```

3. Restart services:
   ```bash
   docker-compose --profile fullstack restart
   ```

### Task Timeout

**Symptoms:**
```
TimeoutError: Task did not complete within 120 seconds
```

**Solutions:**
1. Check Python Agent is running:
   ```bash
   docker-compose ps python-agent
   docker-compose logs python-agent
   ```

2. Verify LLM API key is configured:
   ```bash
   echo $OPENAI_API_KEY
   # or
   echo $ARK_API_KEY
   ```

3. Increase timeout in test (for slow LLM responses):
   ```python
   timeout_seconds=300  # 5 minutes
   ```

### Authentication Errors

**Symptoms:**
```
HTTP 401: Unauthorized
HTTP 403: Forbidden
```

**Solutions:**
1. Verify agent token matches configuration:
   ```bash
   # In .env
   MVP_AGENT_TOKEN=agent-dev-token
   ```

2. Check Control Plane authentication mode:
   ```bash
   docker-compose exec control-plane env | grep MVP_AUTH_MODE
   ```

### Artifact Not Found

**Symptoms:**
```
HTTP 404: Artifact not found
```

**Solutions:**
1. Check artifact directory permissions:
   ```bash
   docker-compose exec control-plane ls -la /app/data/artifacts
   ```

2. Verify artifact was uploaded:
   ```bash
   docker-compose logs control-plane | grep "artifact"
   ```

## CI Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Compose
        run: |
          docker-compose --profile fullstack up -d
          docker-compose ps
      
      - name: Wait for services
        run: |
          timeout 120 bash -c 'until curl -f http://localhost:8058/actuator/health; do sleep 2; done'
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd python-agent
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run E2E tests
        env:
          RUN_E2E_TESTS: 1
          MVP_BASE_URL: http://localhost:8058
          MVP_AGENT_TOKEN: agent-dev-token
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          cd python-agent
          pytest tests/test_e2e_task_lifecycle.py -v --cov=. --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./python-agent/coverage.xml
      
      - name: Cleanup
        if: always()
        run: docker-compose down -v
```

## Performance Benchmarks

Expected test execution times (with running services):

| Test | Duration | Notes |
|------|----------|-------|
| `test_task_idempotency` | 2-5s | Fast, no LLM calls |
| `test_event_ack_protocol` | 2-5s | Fast, no LLM calls |
| `test_agent_polling_and_execution` | 5-10s | Fast, minimal execution |
| `test_artifact_upload_and_download` | 2-5s | Fast, no LLM calls |
| `test_complete_task_lifecycle_web_generation` | 60-180s | Slow, includes LLM generation |

**Total Suite Duration:** 70-200 seconds

## Best Practices

### 1. Test Isolation

Each test should:
- Use unique project IDs
- Use unique idempotency keys
- Clean up resources (handled by fixtures)

### 2. Test Data

- Use descriptive prompts that clearly indicate test purpose
- Use realistic but simple generation requests
- Avoid complex prompts that might timeout

### 3. Assertions

- Verify state transitions explicitly
- Check both success and error cases
- Validate data structures completely

### 4. Debugging

Enable verbose output:
```bash
RUN_E2E_TESTS=1 pytest tests/test_e2e_task_lifecycle.py -v -s --log-cli-level=DEBUG
```

View service logs during test:
```bash
# In another terminal
docker-compose logs -f control-plane python-agent
```

## Future Enhancements

Potential additions to the E2E test suite:

1. **Backend Generation Tests**
   - Flask backend generation
   - FastAPI backend generation
   - Database initialization validation

2. **Error Handling Tests**
   - Task cancellation
   - Task timeout
   - Agent crash recovery

3. **Concurrency Tests**
   - Multiple agents polling
   - Distributed lock verification
   - Race condition testing

4. **Performance Tests**
   - Load testing with multiple concurrent tasks
   - Throughput measurement
   - Latency benchmarking

5. **Security Tests**
   - Authentication verification
   - Authorization checks
   - Input validation

## References

- **Requirements:** `.kiro/specs/backend-upgrade-2.0/requirements.md` (Requirement 6.5)
- **Design:** `.kiro/specs/backend-upgrade-2.0/design.md`
- **Tasks:** `.kiro/specs/backend-upgrade-2.0/tasks.md` (Task 8.1)
- **Control Plane API:** `control-plane-spring/src/main/java/com/autocode/controlplane/api/`
- **Python Agent:** `python-agent/orchestrator/agent_orchestrator.py`
