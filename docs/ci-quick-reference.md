# CI Pipeline Quick Reference

## Quality Gates

| Gate | Threshold | Enforcement |
|------|-----------|-------------|
| Java Tests | All pass | `mvn test` |
| Java Coverage | ≥70% | `mvn verify` (JaCoCo) |
| Python Tests | All pass | `pytest` |
| Python Coverage | ≥70% | `pytest --cov-fail-under=70` |

## Before Pushing

```bash
# Run Java tests locally
cd control-plane-spring
mvn clean test
mvn verify  # Check coverage

# Run Python tests locally
cd python-agent
pytest  # Runs with coverage check
```

## Understanding CI Results

### ✅ All Passed
```
✅ Java Tests: PASSED
✅ Java Coverage: PASSED (≥70%)
✅ Python Tests: PASSED
```
**Action:** PR is ready for review and merge

### ❌ Test Failed
```
❌ Java Tests: FAILED
✅ Java Coverage: PASSED (≥70%)
✅ Python Tests: PASSED
```
**Action:** Fix failing tests, push changes

### ❌ Coverage Failed
```
✅ Java Tests: PASSED
❌ Java Coverage: FAILED (<70%)
✅ Python Tests: PASSED
```
**Action:** Add tests to increase coverage, push changes

## Viewing Coverage Reports

### In GitHub Actions
1. Go to Actions tab
2. Click on your workflow run
3. Scroll to "Artifacts" section
4. Download coverage reports

### Locally

**Java:**
```bash
cd control-plane-spring
mvn jacoco:report
open target/site/jacoco/index.html
```

**Python:**
```bash
cd python-agent
pytest
open htmlcov/index.html
```

## Common Issues

### "Coverage below 70%"
1. View coverage report
2. Identify uncovered code
3. Add tests for uncovered lines
4. Run tests locally to verify
5. Push changes

### "Tests failed"
1. Check CI logs for error details
2. Run failing test locally: `pytest -k test_name`
3. Fix the issue
4. Verify locally
5. Push changes

### "Merge blocked"
- All gates must pass before merge
- Check PR comment for specific failures
- Fix issues and push changes
- CI will re-run automatically

## Tips

- ✅ Run tests locally before pushing
- ✅ Check coverage before creating PR
- ✅ Add tests for new code
- ✅ Review coverage reports regularly
- ❌ Don't skip tests to meet coverage
- ❌ Don't commit commented-out tests
- ❌ Don't push without running tests

## Need Help?

- [Full CI Pipeline Guide](./ci-pipeline-guide.md)
- [CI Enhancements Summary](./ci-enhancements-summary.md)
- [Backend Upgrade 2.0 Spec](../.kiro/specs/backend-upgrade-2.0/)
