# AutoCode Backend Upgrade 2.0 - Smoke Test Suite

## Overview

The smoke test suite provides comprehensive end-to-end validation of the AutoCode Backend Upgrade 2.0 system. It verifies system health, service accessibility, and complete task lifecycle functionality within 30 seconds as required by **Requirement 1.5**.

## Features

### Service Health Validation
- **Control Plane** (Port 8058): Task lifecycle management
- **Java Sandbox** (Port 18080): Secure code execution environment  
- **Spring Cloud Gateway** (Port 8080): Unified API gateway (optional)
- **Prometheus** (Port 9090): Metrics collection (optional)
- **Grafana** (Port 3000): Monitoring dashboards (optional)
- **Alertmanager** (Port 9093): Alert management (optional)

### End-to-End Task Flow Testing
1. **Task Creation**: Creates a test task via Control Plane API
2. **Task Execution**: Monitors task processing and event publishing
3. **Event Publishing**: Validates event flow between Python Agent and Control Plane
4. **Artifact Generation**: Checks for generated code artifacts

### Authentication Testing
- JWT-based authentication with fallback to operator token
- Validates authentication headers and session management

## Usage

### Quick Start

```bash
# Run with default settings
python scripts/smoke-test.py

# Run with PowerShell wrapper
.\scripts\run-smoke-test.ps1
```

### Advanced Usage

```bash
# Run with custom configuration
python scripts/smoke-test.py \
  --base-url http://localhost \
  --username admin \
  --password admin123 \
  --project-id proj-1 \
  --verbose

# Run against remote server
python scripts/smoke-test.py \
  --base-url http://production-server \
  --operator-token your-production-token
```

### PowerShell Options

```powershell
# Run with verbose output
.\scripts\run-smoke-test.ps1 -Verbose

# Run against different server
.\scripts\run-smoke-test.ps1 -BaseUrl "http://staging-server"

# Custom authentication
.\scripts\run-smoke-test.ps1 -Username "testuser" -Password "testpass"

# Show help
.\scripts\run-smoke-test.ps1 -Help
```

## Prerequisites

### System Requirements
- Python 3.7 or higher
- Network access to target services
- Required Python packages (automatically installed):
  - `requests>=2.25.0,<3.0.0`

### Service Requirements
- **Minimum**: Control Plane and Java Sandbox must be running
- **Recommended**: Full platform stack for complete validation

### Environment Setup

1. **Install dependencies**:
   ```bash
   pip install -r scripts/requirements.txt
   ```

2. **Start services**:
   ```bash
   # Full platform stack (recommended)
   docker compose --profile platform up -d
   
   # Or minimum fullstack
   docker compose --profile fullstack up -d
   ```

3. **Verify services are healthy**:
   ```bash
   docker compose ps
   ```

## Test Results

### Success Criteria
- **Core Services**: Control Plane and Java Sandbox must be healthy
- **Authentication**: Must successfully authenticate with the system
- **Performance**: Total test duration must be ≤ 30 seconds
- **Optional Services**: Gateway and observability stack failures are non-critical

### Sample Output

```
AutoCode Backend Upgrade 2.0 - Smoke Test Suite
============================================================

1. Testing service accessibility and health...
✓ Service Health: Control Plane - Control Plane: Healthy (1.23s)
✓ Service Health: Java Sandbox - Java Sandbox: Healthy (0.89s)
✓ Service Health: Spring Cloud Gateway - Spring Cloud Gateway: Healthy (0.67s)

2. Testing authentication...
✓ Control Plane Authentication - JWT authentication successful (0.45s)

3. Testing end-to-end task flow...
✓ End-to-End Task Flow - E2E test completed - Task: task_abc123, Status: RUNNING (2.34s)

============================================================
SMOKE TEST RESULTS SUMMARY
============================================================
Total Duration: 8.45s
Total Tests: 8
Passed: 8
Failed: 0
Success Rate: 100.0%

✓ Test duration (8.45s) meets 30-second requirement
🎉 SMOKE TEST SUITE: PASSED
```

## Troubleshooting

### Common Issues

#### Services Not Running
```
✗ Service Health: Control Plane - Port 8058 is not accessible
```
**Solution**: Start the services with `docker compose --profile platform up -d`

#### Authentication Failures
```
✗ Control Plane Authentication - JWT login failed
```
**Solution**: 
- Check username/password in `.env` file
- Verify `MVP_JWT_SECRET` is properly configured
- Ensure Control Plane is healthy

#### Task Creation Failures
```
✗ End-to-End Task Flow - Task creation failed: HTTP 401
```
**Solution**:
- Verify authentication is working
- Check `MVP_AGENT_TOKEN` configuration
- Ensure project ID exists

#### Timeout Issues
```
⚠️ WARNING: Total test duration (35.2s) exceeds 30-second requirement!
```
**Solution**:
- Check system performance and resource availability
- Verify network connectivity
- Review service startup times

### Debug Mode

Run with verbose logging for detailed troubleshooting:

```bash
python scripts/smoke-test.py --verbose
```

This provides:
- Detailed HTTP request/response information
- Service health check details
- Task creation and monitoring logs
- Authentication flow details

### Manual Verification

If smoke tests fail, manually verify services:

```bash
# Check Control Plane health
curl http://localhost:8058/actuator/health

# Check Java Sandbox health  
curl http://localhost:18080/sandbox/health

# Check Gateway health (if running)
curl http://localhost:8080/healthz

# Check service status
docker compose ps
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run Smoke Tests
  run: |
    python scripts/smoke-test.py --verbose
  timeout-minutes: 2
```

### Docker Compose Integration

```yaml
# Add to docker-compose.yml for automated testing
smoke-test:
  build:
    context: .
    dockerfile: scripts/Dockerfile.smoke-test
  depends_on:
    control-plane:
      condition: service_healthy
  command: python smoke-test.py --base-url http://control-plane
```

## Performance Benchmarks

### Expected Timing
- **Service Health Checks**: 2-5 seconds total
- **Authentication**: 0.5-2 seconds
- **Task Creation**: 0.5-1 second
- **Event Monitoring**: 1-5 seconds
- **Total Duration**: 5-15 seconds (well under 30-second requirement)

### Performance Optimization
- Tests run in parallel where possible
- Configurable timeouts for different environments
- Efficient port accessibility checking
- Minimal test data to reduce processing time

## Extending the Test Suite

### Adding New Service Checks

```python
# Add to service_endpoints list in SmokeTestSuite.__init__
ServiceEndpoint(
    name="New Service",
    port=8090,
    health_path="/health",
    description="Description of the service",
    required=True  # or False for optional services
)
```

### Adding Custom Tests

```python
def custom_test(self) -> Tuple[bool, str, Optional[Dict]]:
    """Custom test implementation"""
    # Test logic here
    return True, "Test passed", {"details": "test_data"}

# Add to run_all_tests method
self.run_test("Custom Test Name", self.custom_test)
```

## Requirements Validation

This smoke test suite validates the following requirements:

- **Requirement 1.1**: Control Plane accessible at port 8058 with health endpoint responding within 2 seconds
- **Requirement 1.2**: Java Sandbox accessible at port 18080 with security policies active  
- **Requirement 1.3**: Spring Cloud Gateway accessible at port 8080 with routing configuration loaded
- **Requirement 1.4**: Observability stack initialization (Prometheus 9090, Grafana 3000, Alertmanager 9093)
- **Requirement 1.5**: End-to-end smoke tests complete within 30 seconds
- **Requirement 1.6**: System restoration after restart (when used in CI/CD pipelines)

## Support

For issues with the smoke test suite:

1. **Check Prerequisites**: Ensure Python 3.7+ and required services are running
2. **Review Logs**: Run with `--verbose` flag for detailed output
3. **Verify Configuration**: Check `.env` file and service configuration
4. **Manual Testing**: Use curl commands to verify service accessibility
5. **System Resources**: Ensure adequate CPU/memory for all services

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-02  
**Compatibility**: AutoCode Backend Upgrade 2.0