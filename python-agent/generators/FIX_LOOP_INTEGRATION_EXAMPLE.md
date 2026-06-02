# Fix Loop Integration Example

This document shows how to integrate the intelligent Fix Loop into the orchestrator's code generation pipeline.

## Current Implementation (Simple Retry)

The current orchestrator uses a simple retry loop that regenerates code on validation failure:

```python
# In agent_orchestrator.py
max_fix_attempts = 3
fix_attempt = 0
last_test_error = ""

while fix_attempt < max_fix_attempts:
    fix_attempt += 1
    
    # Generate code
    with observe_task_span(task, "code_generation", stage="CoderAgent"):
        coded = self.coder_agent.execute(task, client, plan, publish_event=publisher)
    
    # Validate
    with observe_task_span(task, "validation_gate", stage="ValidationGate"):
        validation = self.validation_gate.validate(task, _resolve_workspace(task))
    
    if not validation.ok:
        last_test_error = validation.summary
        if fix_attempt < max_fix_attempts:
            continue  # Retry generation
        
        # Max attempts reached - fail
        self.publish_event(task, client, "TASK_FAILED", payload)
        return failure_result
    
    # Validation passed - continue with review and test
    ...
```

**Limitations:**
- Regenerates entire codebase on each failure (slow)
- No intelligent error analysis
- No targeted fixes
- Wastes LLM tokens on full regeneration

## Enhanced Implementation (Intelligent Fix Loop)

The enhanced implementation uses the Fix Loop for targeted, intelligent repairs:

```python
# In agent_orchestrator.py
from generators.fix_loop import FixLoop
from llm.llm_client import LLMClient

class AgentOrchestrator(BaseAgent):
    def __init__(self, ...):
        super().__init__()
        # ... existing initialization ...
        
        # Add fix loop with LLM support
        self.llm_client = LLMClient()
        self.fix_loop = FixLoop(llm_client=self.llm_client)
    
    def _execute_code_change_with_fix_loop(
        self,
        task: dict[str, Any],
        client: ControlPlaneClient,
        plan: PlanResult,
        publisher: Callable,
    ) -> dict[str, Any]:
        """Execute code change with intelligent fix loop."""
        
        # Generate code once
        with observe_task_span(task, "code_generation", stage="CoderAgent"):
            coded = self.coder_agent.execute(task, client, plan, publish_event=publisher)
        
        if not coded:
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": "coder_failed",
                "errorCode": _error_code_from_reason("coder_failed"),
            }
        
        # Apply intelligent fix loop
        workspace = _resolve_workspace(task)
        
        with observe_task_span(task, "fix_loop", stage="FixLoop"):
            fix_result = self.fix_loop.fix_and_validate(
                task=task,
                workspace=workspace,
                max_iterations=3,
            )
        
        # Publish fix loop events
        for attempt in fix_result.attempts:
            self.publish_event(
                task,
                client,
                "ASSISTANT_OUTPUT",
                {
                    "stage": "FixLoop",
                    "message": f"Fix attempt {attempt.iteration}",
                    "category": attempt.category.value,
                    "strategy": attempt.strategy,
                    "success": attempt.success,
                    "fixedFiles": attempt.fixed_files,
                },
            )
        
        if not fix_result.success:
            # Fix loop exhausted - fail with detailed info
            base_payload = _failure_payload(
                "fix_loop_exhausted",
                plan_name=plan.plan_name,
                iterations=fix_result.iterations_used,
                finalErrors=fix_result.final_errors,
                attempts=[
                    {
                        "iteration": a.iteration,
                        "category": a.category.value,
                        "strategy": a.strategy,
                        "success": a.success,
                    }
                    for a in fix_result.attempts
                ],
            )
            payload = self._terminal_payload(
                task,
                base_payload,
                task_status="failed",
                intent="code_change",
                reason=str(base_payload.get("reason", "")).strip(),
                fix_loop_attempts=fix_result.iterations_used,
                fix_loop_success=False,
            )
            self.publish_event(task, client, "TASK_FAILED", payload)
            return {
                "intent": "code_change",
                "planName": plan.plan_name,
                "status": "failed",
                "reason": payload["reason"],
                "errorCode": payload["errorCode"],
                "detail": fix_result.summary,
            }
        
        # Validation passed - publish success
        self.publish_event(
            task,
            client,
            "ASSISTANT_OUTPUT",
            {
                "stage": "FixLoop",
                "message": f"Validation passed after {fix_result.iterations_used} iteration(s)",
                "iterations": fix_result.iterations_used,
                "success": True,
            },
        )
        
        # Continue with review and test
        with observe_task_span(task, "review_and_test", stage="Orchestrator"):
            dag_results = self._run_review_and_test(task, client, plan, publisher)
        
        # ... rest of the pipeline ...
```

## Benefits of Enhanced Implementation

### 1. Faster Fixes
- **Before**: Regenerate entire codebase (10-30 seconds per attempt)
- **After**: Targeted fixes (1-5 seconds per attempt)

### 2. Lower Cost
- **Before**: Full LLM generation on each retry (~4000 tokens)
- **After**: Targeted fixes (~500-1000 tokens)

### 3. Better Success Rate
- **Before**: Random regeneration may not fix the issue
- **After**: Intelligent error analysis and targeted repairs

### 4. Detailed Diagnostics
- **Before**: Generic "validation failed" message
- **After**: Detailed error categorization and fix history

### 5. Preserves Good Code
- **Before**: Discards entire codebase on retry
- **After**: Only modifies files with errors

## Migration Path

### Phase 1: Parallel Testing (Recommended)

Run both implementations in parallel and compare results:

```python
def _execute_code_change(self, task, client, plan, publisher):
    # Try new fix loop first
    result_new = self._execute_code_change_with_fix_loop(task, client, plan, publisher)
    
    if result_new["status"] == "success":
        return result_new
    
    # Fallback to old retry loop
    logger.warning("Fix loop failed, falling back to retry loop")
    result_old = self._execute_code_change_with_retry(task, client, plan, publisher)
    
    return result_old
```

### Phase 2: Feature Flag

Use a feature flag to control which implementation is used:

```python
def _execute_code_change(self, task, client, plan, publisher):
    use_fix_loop = os.getenv("USE_FIX_LOOP", "true").lower() == "true"
    
    if use_fix_loop:
        return self._execute_code_change_with_fix_loop(task, client, plan, publisher)
    else:
        return self._execute_code_change_with_retry(task, client, plan, publisher)
```

### Phase 3: Full Migration

Replace the old retry loop with the fix loop:

```python
def _execute_code_change(self, task, client, plan, publisher):
    return self._execute_code_change_with_fix_loop(task, client, plan, publisher)
```

## Configuration

### Environment Variables

```bash
# Enable/disable fix loop
USE_FIX_LOOP=true

# Maximum fix iterations
FIX_LOOP_MAX_ITERATIONS=3

# LLM configuration for fix loop
LLM_BACKEND=openai
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.2
```

### Code Configuration

```python
class AgentOrchestrator(BaseAgent):
    def __init__(self, ...):
        # ... existing initialization ...
        
        # Configure fix loop
        max_iterations = int(os.getenv("FIX_LOOP_MAX_ITERATIONS", "3"))
        
        self.llm_client = LLMClient(
            backend=os.getenv("LLM_BACKEND", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        )
        
        self.fix_loop = FixLoop(llm_client=self.llm_client)
        self.fix_loop_max_iterations = max_iterations
```

## Monitoring and Metrics

### Key Metrics to Track

```python
# In observability.py or metrics collection

# Fix loop success rate
observation.record_metric(
    "fix_loop_success_rate",
    1 if fix_result.success else 0,
    unit="count",
    stage="FixLoop",
)

# Fix loop iterations
observation.record_metric(
    "fix_loop_iterations",
    fix_result.iterations_used,
    unit="count",
    stage="FixLoop",
)

# Fix loop duration
observation.record_metric(
    "fix_loop_duration_seconds",
    duration,
    unit="seconds",
    stage="FixLoop",
)

# Error categories
for attempt in fix_result.attempts:
    observation.record_metric(
        "fix_loop_error_category",
        1,
        unit="count",
        stage="FixLoop",
        category=attempt.category.value,
    )

# Fix strategies used
for attempt in fix_result.attempts:
    observation.record_metric(
        "fix_loop_strategy",
        1,
        unit="count",
        stage="FixLoop",
        strategy=attempt.strategy,
    )
```

### Grafana Dashboard Queries

```promql
# Fix loop success rate
sum(rate(fix_loop_success_rate_total[5m])) by (stage)

# Average iterations per fix
avg(fix_loop_iterations) by (stage)

# Error category distribution
sum(rate(fix_loop_error_category_total[5m])) by (category)

# Strategy effectiveness
sum(rate(fix_loop_strategy_total[5m])) by (strategy)
```

## Testing

### Unit Tests

```python
# test_orchestrator_fix_loop.py

def test_fix_loop_integration_success():
    """Test successful fix loop integration."""
    orchestrator = AgentOrchestrator()
    
    task = {
        "taskId": "test-123",
        "_generated_target": "backend",
        "prompt": "Create a todo app",
    }
    
    # Mock client
    client = MockControlPlaneClient()
    
    # Execute with fix loop
    result = orchestrator._execute_code_change_with_fix_loop(
        task, client, plan, publisher
    )
    
    assert result["status"] == "success"
    assert "fix_loop_attempts" in result

def test_fix_loop_integration_failure():
    """Test fix loop failure handling."""
    orchestrator = AgentOrchestrator()
    
    # Create unfixable scenario
    task = {
        "taskId": "test-456",
        "_generated_target": "backend",
        "prompt": "Invalid request",
    }
    
    client = MockControlPlaneClient()
    
    result = orchestrator._execute_code_change_with_fix_loop(
        task, client, plan, publisher
    )
    
    assert result["status"] == "failed"
    assert result["reason"] == "fix_loop_exhausted"
    assert "detail" in result
```

### Integration Tests

```python
# test_e2e_fix_loop.py

def test_end_to_end_with_fix_loop():
    """Test complete task execution with fix loop."""
    orchestrator = AgentOrchestrator()
    client = ControlPlaneClient()
    
    task = {
        "taskId": "e2e-test-789",
        "prompt": "Create a blog backend with posts and comments",
        "target": "backend",
    }
    
    # Execute task
    orchestrator.handle_task(task, client)
    
    # Verify events published
    events = client.get_published_events(task["taskId"])
    
    # Should have fix loop events
    fix_loop_events = [e for e in events if e["stage"] == "FixLoop"]
    assert len(fix_loop_events) > 0
    
    # Should have success event
    success_events = [e for e in events if e["eventType"] == "TASK_SUCCEEDED"]
    assert len(success_events) == 1
```

## Troubleshooting

### Issue: Fix Loop Not Triggered

**Symptom**: Validation fails but fix loop doesn't run

**Causes**:
- Fix loop not initialized in orchestrator
- Feature flag disabled
- Code path not using fix loop method

**Solutions**:
1. Verify fix loop initialization in `__init__`
2. Check `USE_FIX_LOOP` environment variable
3. Ensure `_execute_code_change_with_fix_loop` is called

### Issue: Fix Loop Always Fails

**Symptom**: Fix loop exhausts all iterations without success

**Causes**:
- LLM client not configured
- Errors too complex for rule-based fixes
- Validation too strict

**Solutions**:
1. Verify LLM client configuration and API keys
2. Review error categories and add more rule-based strategies
3. Adjust validation rules if too strict

### Issue: Performance Degradation

**Symptom**: Fix loop takes too long

**Causes**:
- Too many iterations
- LLM calls are slow
- Large files being processed

**Solutions**:
1. Reduce `FIX_LOOP_MAX_ITERATIONS`
2. Use faster LLM model
3. Optimize file identification logic

## Future Enhancements

### 1. Adaptive Iteration Limits

Adjust iteration limits based on error complexity:

```python
def _calculate_max_iterations(errors: list[str]) -> int:
    """Calculate max iterations based on error complexity."""
    if len(errors) <= 2:
        return 2  # Simple errors
    elif len(errors) <= 5:
        return 3  # Medium complexity
    else:
        return 5  # Complex errors
```

### 2. Fix Strategy Learning

Learn which strategies work best for different error types:

```python
class FixStrategyLearner:
    """Learn and optimize fix strategies over time."""
    
    def record_success(self, category: ErrorCategory, strategy: str):
        """Record successful fix strategy."""
        ...
    
    def recommend_strategy(self, category: ErrorCategory) -> str:
        """Recommend best strategy based on history."""
        ...
```

### 3. Parallel Fix Attempts

Try multiple fix strategies in parallel:

```python
async def _apply_parallel_fixes(self, errors, workspace):
    """Apply multiple fix strategies in parallel."""
    strategies = [
        self._fix_structure_errors,
        self._fix_dependency_errors,
        self._fix_with_llm,
    ]
    
    results = await asyncio.gather(*[
        strategy(task, workspace, errors)
        for strategy in strategies
    ])
    
    # Select best result
    return max(results, key=lambda r: r[0])  # Sort by success
```

## References

- **Fix Loop Implementation**: `python-agent/generators/fix_loop.py`
- **Fix Loop Documentation**: `python-agent/generators/FIX_LOOP_DOCUMENTATION.md`
- **Fix Loop Tests**: `python-agent/tests/test_fix_loop.py`
- **Orchestrator**: `python-agent/orchestrator/agent_orchestrator.py`
- **Validation Gate**: `python-agent/generators/validation_gate.py`
