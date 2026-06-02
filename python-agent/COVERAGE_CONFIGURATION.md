# Python Agent Coverage Configuration

## Overview

This document describes the pytest-cov configuration for the Python Agent component of the Backend Upgrade 2.0 project. The configuration enforces a minimum 70% code coverage threshold as specified in Requirement 6.2.

## Configuration Files

### 1. pyproject.toml

The main configuration file containing:

- **Build system configuration**: Uses setuptools for package management
- **Project metadata**: Version 2.0.0, Python 3.11+ requirement
- **Dependencies**: Runtime and development dependencies
- **Pytest configuration**: Test discovery and execution settings
- **Coverage configuration**: Coverage measurement and reporting settings

#### Key Coverage Settings

```toml
[tool.pytest.ini_options]
addopts = [
    "--cov=.",                     # Coverage for all code in python-agent
    "--cov-report=term-missing",   # Terminal report with missing lines
    "--cov-report=html:htmlcov",   # HTML report in htmlcov directory
    "--cov-report=xml:coverage.xml", # XML report for CI integration
    "--cov-fail-under=70",         # Fail if coverage below 70%
]

[tool.coverage.run]
branch = true                      # Measure branch coverage
parallel = true                    # Support parallel test execution

[tool.coverage.report]
fail_under = 70                    # Fail if coverage is below threshold
```

#### Coverage Exclusions

The following paths are excluded from coverage measurement:
- Test files (`*/tests/*`, `*/test_*.py`)
- Cache directories (`*/__pycache__/*`, `*/.pytest_cache/*`)
- Virtual environments (`*/venv/*`, `*/.venv/*`)
- Documentation and examples (`*/docs/*`, `/examples/*`)
- Hypothesis data (`*/.hypothesis/*`)

#### Code Patterns Excluded from Coverage

The following code patterns are excluded from coverage reporting:
- `pragma: no cover` comments
- `__repr__` and `__str__` methods
- Abstract methods and protocols
- Type checking blocks
- Main execution blocks (`if __name__ == "__main__":`)

### 2. requirements/dev.txt

Updated to include pytest-cov and related testing dependencies:

```
pytest>=8.0.0,<9
pytest-cov>=4.1.0,<5
pytest-asyncio>=0.23.0,<1
```

### 3. CI Configuration (.github/workflows/ci.yml)

Updated to:
- Run tests with coverage measurement
- Generate HTML and XML coverage reports
- Upload coverage artifacts for review
- Enforce 70% coverage threshold (build fails if not met)

## Usage

### Running Tests Locally

```bash
# Run tests with coverage (from python-agent directory)
pytest tests

# Run tests with verbose output
pytest tests -v

# Run specific test file
pytest tests/test_event_ack_protocol_properties.py

# Generate coverage report only
pytest tests --cov-report=html
```

### Viewing Coverage Reports

#### Terminal Report
The terminal report shows coverage percentages and missing lines immediately after test execution.

#### HTML Report
1. Run tests to generate the report
2. Open `python-agent/htmlcov/index.html` in a web browser
3. Navigate through files to see line-by-line coverage

#### XML Report
The XML report (`coverage.xml`) is generated for CI integration and can be consumed by coverage analysis tools.

## CI Integration

### Coverage Enforcement

The CI pipeline enforces the 70% coverage threshold:
- Tests run automatically on pull requests and pushes to main/master/upgrade branches
- Build fails if coverage drops below 70%
- Coverage reports are uploaded as artifacts for review

### Viewing CI Coverage Reports

1. Navigate to the GitHub Actions run
2. Download the `python-coverage-report` artifact
3. Extract and open `htmlcov/index.html`

## Coverage Thresholds

| Component | Minimum Coverage | Current Status |
|-----------|-----------------|----------------|
| Python Agent | 70% | Configured ✓ |
| Java Control Plane | 70% | Configured (JaCoCo) |

## Troubleshooting

### Coverage Below Threshold

If coverage drops below 70%:
1. Review the HTML coverage report to identify uncovered code
2. Add unit tests for uncovered functions and branches
3. Consider if uncovered code should be excluded (e.g., defensive error handling)
4. Add `# pragma: no cover` comments for code that cannot be tested

### Slow Test Execution

Property-based tests (using Hypothesis) may take longer to execute:
- Default: 100 examples per test
- Can be reduced for faster feedback: `@settings(max_examples=10)`
- CI runs full test suite with default settings

### Coverage Report Not Generated

Ensure pytest-cov is installed:
```bash
pip install pytest-cov>=4.1.0
```

## Related Requirements

This configuration validates:
- **Requirement 6.2**: Python components SHALL achieve at least 70% test coverage measured by pytest-cov
- **Requirement 6.3**: CI system SHALL run all tests and block merge on failures
- **Requirement 6.7**: CI system SHALL fail the build when test coverage drops below threshold

## Future Enhancements

Potential improvements to consider:
1. Increase coverage threshold to 80% after initial stabilization
2. Add coverage differential reporting (show coverage change per PR)
3. Integrate with code review tools for inline coverage feedback
4. Add mutation testing for quality assessment beyond coverage
