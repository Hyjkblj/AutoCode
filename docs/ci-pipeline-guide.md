# CI Pipeline Guide

## Overview

The CI pipeline enforces quality gates to prevent regressions and ensure code quality standards are maintained. This document describes the enhanced CI pipeline configuration and quality gates.

## Pipeline Structure

The CI pipeline runs on:
- Pull requests to any branch
- Pushes to `master`, `main`, or `upgrade/**` branches

## Quality Gates

### 1. Java Test Coverage Gate

**Threshold:** ≥70% line and branch coverage

The pipeline enforces JaCoCo coverage thresholds configured in `control-plane-spring/pom.xml`:

```xml
<limit>
    <counter>LINE</counter>
    <value>COVEREDRATIO</value>
    <minimum>0.70</minimum>
</limit>
<limit>
    <counter>BRANCH</counter>
    <value>COVEREDRATIO</value>
    <minimum>0.70</minimum>
</limit>
```

**Enforcement:** The `mvn verify` command runs the JaCoCo check goal, which fails the build if coverage is below 70%.

### 2. Python Test Coverage Gate

**Threshold:** ≥70% coverage

The pipeline enforces pytest-cov coverage thresholds configured in `python-agent/pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = [
    "--cov-fail-under=70",
]

[tool.coverage.report]
fail_under = 70
```

**Enforcement:** The `pytest` command fails if coverage is below 70%.

### 3. Test Execution Gate

**Requirement:** All tests must pass

Both Java and Python tests must pass for the pipeline to succeed. Test failures block PR merges.

## Pipeline Steps

### 1. Setup
- Checkout code
- Setup Java 21 with Maven cache
- Setup Python 3.11 with pip cache
- Install Python dependencies

### 2. Test Execution
- **Run Maven tests** (`mvn test`)
  - Executes all Java unit tests
  - Generates JaCoCo coverage data
  
- **Enforce JaCoCo coverage** (`mvn verify`)
  - Validates coverage thresholds
  - Fails if coverage < 70%
  
- **Generate JaCoCo report** (`mvn jacoco:report`)
  - Creates HTML coverage report
  - Always runs (even on failure)
  
- **Run Python tests** (`pytest`)
  - Executes all Python tests
  - Generates coverage reports (HTML, XML, terminal)
  - Fails if coverage < 70%

### 3. Reporting
- **Upload coverage artifacts**
  - Java: `control-plane-spring/target/site/jacoco/`
  - Python: `python-agent/htmlcov/` and `coverage.xml`
  - Retained for 30 days
  
- **Generate test summary**
  - Creates GitHub Actions summary with test results
  - Shows pass/fail status for each component
  - Links to coverage reports
  
- **Comment on PR** (PRs only)
  - Posts test results as PR comment
  - Shows status table with ✅/❌ indicators
  - Links to coverage reports
  - Warns if merge is blocked

### 4. Merge Blocking
- **Final gate check**
  - Validates all test steps succeeded
  - Exits with error code 1 if any step failed
  - Prevents PR merge until all gates pass

## Test Result Reporting

### GitHub Actions Summary

The pipeline generates a summary visible in the Actions UI:

```
## Test Results Summary

✅ **Java Tests**: PASSED
✅ **Java Coverage**: PASSED (≥70%)
✅ **Python Tests**: PASSED

### Coverage Reports
- Java: [JaCoCo Report](../artifacts/jacoco-coverage-report)
- Python: [Coverage Report](../artifacts/python-coverage-report)
```

### PR Comments

For pull requests, the pipeline posts a comment with test results:

```markdown
## 🧪 Test Results

| Component | Status |
|-----------|--------|
| Java Tests | ✅ PASSED |
| Java Coverage | ✅ PASSED (≥70%) |
| Python Tests | ✅ PASSED |

### 📊 Coverage Reports
- [Java Coverage Report](https://github.com/...)
- [Python Coverage Report](https://github.com/...)

✅ All tests passed! This PR is ready for review.
```

If any gate fails:

```markdown
⚠️ **This PR cannot be merged until all tests pass and coverage thresholds are met.**
```

## Failure Notifications

When tests fail or coverage thresholds are not met, the pipeline:

1. **Marks the check as failed** - Shows red ❌ in GitHub UI
2. **Blocks PR merge** - GitHub prevents merging until checks pass
3. **Posts PR comment** - Notifies reviewers of failures
4. **Logs failure details** - Shows which specific gates failed:
   ```
   ❌ Tests failed or coverage thresholds not met. Blocking merge.
   
   Failure details:
     - Java coverage below 70% threshold
   ```

## Coverage Reports

### Java Coverage (JaCoCo)

**Location:** `control-plane-spring/target/site/jacoco/index.html`

**Metrics:**
- Line coverage
- Branch coverage
- Method coverage
- Class coverage

**Access:**
- Download from GitHub Actions artifacts
- View locally after running `mvn jacoco:report`

### Python Coverage

**Location:** `python-agent/htmlcov/index.html`

**Metrics:**
- Statement coverage
- Branch coverage
- Missing lines highlighted

**Access:**
- Download from GitHub Actions artifacts
- View locally after running `pytest`

## Local Testing

### Run Java tests with coverage
```bash
cd control-plane-spring
mvn clean test
mvn jacoco:report
mvn verify  # Check coverage thresholds
```

### Run Python tests with coverage
```bash
cd python-agent
pytest  # Runs tests with coverage
# View report: open htmlcov/index.html
```

## Troubleshooting

### Coverage Below Threshold

**Java:**
1. Run `mvn jacoco:report`
2. Open `control-plane-spring/target/site/jacoco/index.html`
3. Identify uncovered code
4. Add tests to cover missing lines/branches

**Python:**
1. Run `pytest`
2. Check terminal output for missing lines
3. Open `python-agent/htmlcov/index.html`
4. Add tests to cover missing code

### Test Failures

**Java:**
```bash
mvn test  # Run tests
# Check logs for failure details
```

**Python:**
```bash
pytest -v  # Verbose output
pytest -k test_name  # Run specific test
```

### Pipeline Failures

1. Check GitHub Actions logs
2. Look for the failing step
3. Review error messages
4. Run tests locally to reproduce
5. Fix issues and push changes

## Best Practices

1. **Run tests locally** before pushing
2. **Check coverage** before creating PR
3. **Add tests** for new code
4. **Fix failing tests** immediately
5. **Review coverage reports** regularly
6. **Don't skip tests** to meet coverage targets
7. **Write meaningful tests** that validate behavior

## Configuration Files

- **CI Pipeline:** `.github/workflows/ci.yml`
- **Java Coverage:** `control-plane-spring/pom.xml` (JaCoCo plugin)
- **Python Coverage:** `python-agent/pyproject.toml` (pytest-cov config)

## Requirements Validation

This CI pipeline implementation validates:

- **Requirement 6.3:** CI system runs all tests and blocks merge on failures
- **Requirement 6.6:** Test coverage thresholds enforced (70% minimum)
- **Requirement 6.1:** JaCoCo configured for Control Plane coverage reporting
- **Requirement 6.2:** pytest-cov configured for Python Agent coverage

## Related Documentation

- [Testing Guide](../README.md#testing)
- [Backend Upgrade 2.0 Spec](.kiro/specs/backend-upgrade-2.0/)
- [JaCoCo Documentation](https://www.jacoco.org/jacoco/trunk/doc/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
