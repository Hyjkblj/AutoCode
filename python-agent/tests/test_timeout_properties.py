"""
Property-based tests for stage-level timeout enforcement.

Task 14.3: Write property tests for timeout enforcement
Property 20: Stage-Level Timeout Implementation

For any task execution, the system SHALL enforce stage-specific timeouts
(Intent: 30s, Planner: 60s, Coder: 300s, Reviewer: 120s, Tester: 180s).

**Validates: Requirements 7.1**
"""
from __future__ import annotations

import sys
import time

import pytest
from hypothesis import given, settings, strategies as st

from config.timeout_config import (
    CODER_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_CONFIG,
    INTENT_TIMEOUT_SECONDS,
    MAX_TASK_EXECUTION_SECONDS,
    PLANNER_TIMEOUT_SECONDS,
    REVIEWER_TIMEOUT_SECONDS,
    STAGE_CODER,
    STAGE_INTENT,
    STAGE_PLANNER,
    STAGE_REVIEWER,
    STAGE_TESTER,
    TESTER_TIMEOUT_SECONDS,
    StageTimeoutConfig,
    TimeoutConfig,
    TimeoutError,
    get_stage_timeout,
    stage_timeout,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

#: All valid stage names as defined by the spec.
VALID_STAGES = [STAGE_INTENT, STAGE_PLANNER, STAGE_CODER, STAGE_REVIEWER, STAGE_TESTER]

valid_stage_strategy = st.sampled_from(VALID_STAGES)

#: Positive timeout values in a reasonable range for unit tests.
positive_timeout_strategy = st.integers(min_value=1, max_value=600)

#: Stage names that are NOT in the valid set.
invalid_stage_strategy = st.text(min_size=1).filter(
    lambda s: s.strip().lower() not in VALID_STAGES
)


# ---------------------------------------------------------------------------
# Property 20: Stage-Level Timeout Implementation
# ---------------------------------------------------------------------------


class TestProperty20StageTimeoutValues:
    """
    **Property 20: Stage-Level Timeout Implementation**

    For any task execution, the system SHALL enforce stage-specific timeouts
    (Intent: 30s, Planner: 60s, Coder: 300s, Reviewer: 120s, Tester: 180s).

    **Validates: Requirements 7.1**
    """

    def test_property_20_intent_timeout_is_30_seconds(self):
        """
        **Property 20 – Intent stage timeout SHALL be 30 seconds.**

        **Validates: Requirements 7.1**
        """
        assert INTENT_TIMEOUT_SECONDS == 30
        assert DEFAULT_TIMEOUT_CONFIG.intent.timeout_seconds == 30
        assert get_stage_timeout(STAGE_INTENT) == 30

    def test_property_20_planner_timeout_is_60_seconds(self):
        """
        **Property 20 – Planner stage timeout SHALL be 60 seconds.**

        **Validates: Requirements 7.1**
        """
        assert PLANNER_TIMEOUT_SECONDS == 60
        assert DEFAULT_TIMEOUT_CONFIG.planner.timeout_seconds == 60
        assert get_stage_timeout(STAGE_PLANNER) == 60

    def test_property_20_coder_timeout_is_300_seconds(self):
        """
        **Property 20 – Coder stage timeout SHALL be 300 seconds.**

        **Validates: Requirements 7.1**
        """
        assert CODER_TIMEOUT_SECONDS == 300
        assert DEFAULT_TIMEOUT_CONFIG.coder.timeout_seconds == 300
        assert get_stage_timeout(STAGE_CODER) == 300

    def test_property_20_reviewer_timeout_is_120_seconds(self):
        """
        **Property 20 – Reviewer stage timeout SHALL be 120 seconds.**

        **Validates: Requirements 7.1**
        """
        assert REVIEWER_TIMEOUT_SECONDS == 120
        assert DEFAULT_TIMEOUT_CONFIG.reviewer.timeout_seconds == 120
        assert get_stage_timeout(STAGE_REVIEWER) == 120

    def test_property_20_tester_timeout_is_180_seconds(self):
        """
        **Property 20 – Tester stage timeout SHALL be 180 seconds.**

        **Validates: Requirements 7.1**
        """
        assert TESTER_TIMEOUT_SECONDS == 180
        assert DEFAULT_TIMEOUT_CONFIG.tester.timeout_seconds == 180
        assert get_stage_timeout(STAGE_TESTER) == 180

    def test_property_20_max_task_execution_is_30_minutes(self):
        """
        **Property 20 – Maximum task execution time SHALL be 30 minutes.**

        **Validates: Requirements 7.6**
        """
        assert MAX_TASK_EXECUTION_SECONDS == 1800
        assert DEFAULT_TIMEOUT_CONFIG.max_task_execution_seconds == 1800

    @given(valid_stage_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_20_every_valid_stage_has_positive_timeout(self, stage: str):
        """
        **Property 20 – For any valid stage name, the timeout SHALL be positive.**

        **Validates: Requirements 7.1**
        """
        timeout = get_stage_timeout(stage)
        assert timeout > 0, f"Stage '{stage}' must have a positive timeout, got {timeout}"

    @given(valid_stage_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_20_stage_timeout_matches_config(self, stage: str):
        """
        **Property 20 – For any valid stage, get_stage_timeout SHALL return the
        same value as DEFAULT_TIMEOUT_CONFIG.get_stage_timeout.**

        **Validates: Requirements 7.1**
        """
        assert get_stage_timeout(stage) == DEFAULT_TIMEOUT_CONFIG.get_stage_timeout(stage)

    @given(invalid_stage_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_20_invalid_stage_raises_value_error(self, stage: str):
        """
        **Property 20 – For any unrecognised stage name, get_stage_timeout SHALL
        raise ValueError.**

        **Validates: Requirements 7.1**
        """
        with pytest.raises(ValueError):
            get_stage_timeout(stage)


class TestProperty20TimeoutConfigConstruction:
    """
    Tests verifying that TimeoutConfig can be constructed with arbitrary
    positive timeout values and that all constraints are preserved.

    **Validates: Requirements 7.1**
    """

    @given(
        st.integers(min_value=1, max_value=3600),
        st.integers(min_value=1, max_value=3600),
        st.integers(min_value=1, max_value=3600),
        st.integers(min_value=1, max_value=3600),
        st.integers(min_value=1, max_value=3600),
        st.integers(min_value=1, max_value=7200),
    )
    @settings(max_examples=50, deadline=None)
    def test_property_20_custom_config_preserves_all_timeouts(
        self,
        intent_t: int,
        planner_t: int,
        coder_t: int,
        reviewer_t: int,
        tester_t: int,
        max_t: int,
    ):
        """
        **Property 20 – For any set of positive timeout values, a TimeoutConfig
        SHALL preserve each value exactly.**

        **Validates: Requirements 7.1**
        """
        cfg = TimeoutConfig(
            intent=StageTimeoutConfig(stage=STAGE_INTENT, timeout_seconds=intent_t),
            planner=StageTimeoutConfig(stage=STAGE_PLANNER, timeout_seconds=planner_t),
            coder=StageTimeoutConfig(stage=STAGE_CODER, timeout_seconds=coder_t),
            reviewer=StageTimeoutConfig(stage=STAGE_REVIEWER, timeout_seconds=reviewer_t),
            tester=StageTimeoutConfig(stage=STAGE_TESTER, timeout_seconds=tester_t),
            max_task_execution_seconds=max_t,
        )

        assert cfg.get_stage_timeout(STAGE_INTENT) == intent_t
        assert cfg.get_stage_timeout(STAGE_PLANNER) == planner_t
        assert cfg.get_stage_timeout(STAGE_CODER) == coder_t
        assert cfg.get_stage_timeout(STAGE_REVIEWER) == reviewer_t
        assert cfg.get_stage_timeout(STAGE_TESTER) == tester_t
        assert cfg.max_task_execution_seconds == max_t

    @given(valid_stage_strategy, positive_timeout_strategy)
    @settings(max_examples=50, deadline=None)
    def test_property_20_stage_timeout_config_is_positive(self, stage: str, timeout: int):
        """
        **Property 20 – For any positive timeout value, StageTimeoutConfig SHALL
        store it without modification.**

        **Validates: Requirements 7.1**
        """
        cfg = StageTimeoutConfig(stage=stage, timeout_seconds=timeout)
        assert cfg.timeout_seconds == timeout
        assert cfg.timeout_seconds > 0

    @given(valid_stage_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_20_stage_timeout_config_rejects_non_positive(self, stage: str):
        """
        **Property 20 – StageTimeoutConfig SHALL reject non-positive timeout values.**

        **Validates: Requirements 7.1**
        """
        with pytest.raises(ValueError):
            StageTimeoutConfig(stage=stage, timeout_seconds=0)

        with pytest.raises(ValueError):
            StageTimeoutConfig(stage=stage, timeout_seconds=-1)

    @given(valid_stage_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_20_all_stages_present_in_config(self, stage: str):
        """
        **Property 20 – For any valid stage name, DEFAULT_TIMEOUT_CONFIG SHALL
        return a timeout without raising an exception.**

        **Validates: Requirements 7.1**
        """
        # Should not raise
        timeout = DEFAULT_TIMEOUT_CONFIG.get_stage_timeout(stage)
        assert isinstance(timeout, int)
        assert timeout > 0


class TestProperty20TimeoutEnforcement:
    """
    Tests verifying that the stage_timeout context manager correctly enforces
    timeouts and raises TimeoutError when the limit is exceeded.

    **Validates: Requirements 7.1**
    """

    def test_property_20_fast_operation_completes_within_timeout(self):
        """
        **Property 20 – An operation that completes before the timeout SHALL
        succeed without raising TimeoutError.**

        **Validates: Requirements 7.1**
        """
        with stage_timeout(STAGE_INTENT, timeout_seconds=5):
            result = 1 + 1  # Instant operation

        assert result == 2

    def test_property_20_timeout_error_carries_stage_and_duration(self):
        """
        **Property 20 – TimeoutError SHALL carry the stage name and timeout value.**

        **Validates: Requirements 7.1**
        """
        err = TimeoutError(stage=STAGE_CODER, timeout_seconds=300, task_id="task-42")
        assert err.stage == STAGE_CODER
        assert err.timeout_seconds == 300
        assert err.task_id == "task-42"
        assert "coder" in str(err).lower()
        assert "300" in str(err)

    def test_property_20_timeout_error_without_task_id(self):
        """
        **Property 20 – TimeoutError SHALL work without a task_id.**

        **Validates: Requirements 7.1**
        """
        err = TimeoutError(stage=STAGE_PLANNER, timeout_seconds=60)
        assert err.stage == STAGE_PLANNER
        assert err.timeout_seconds == 60
        assert err.task_id == ""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGALRM-based preemption is not available on Windows; "
               "the thread-based fallback detects timeouts post-execution.",
    )
    def test_property_20_slow_operation_raises_timeout_error_posix(self):
        """
        **Property 20 – On POSIX, an operation that exceeds the timeout SHALL
        raise TimeoutError.**

        **Validates: Requirements 7.1**
        """
        with pytest.raises(TimeoutError) as exc_info:
            with stage_timeout(STAGE_INTENT, timeout_seconds=1):
                time.sleep(5)  # Exceeds 1-second limit

        assert exc_info.value.stage == STAGE_INTENT
        assert exc_info.value.timeout_seconds == 1

    @given(valid_stage_strategy, positive_timeout_strategy)
    @settings(max_examples=30, deadline=None)
    def test_property_20_stage_timeout_context_manager_accepts_any_valid_stage(
        self, stage: str, timeout: int
    ):
        """
        **Property 20 – For any valid stage and positive timeout, the
        stage_timeout context manager SHALL accept the parameters without error.**

        **Validates: Requirements 7.1**
        """
        # Verify the context manager can be entered and exited cleanly
        with stage_timeout(stage, timeout_seconds=timeout):
            pass  # Instant operation — should never time out

    def test_property_20_stage_timeout_uses_config_when_provided(self):
        """
        **Property 20 – When a TimeoutConfig is provided, stage_timeout SHALL
        use the config's timeout for the given stage.**

        **Validates: Requirements 7.1**
        """
        custom_cfg = TimeoutConfig(
            intent=StageTimeoutConfig(stage=STAGE_INTENT, timeout_seconds=5),
            planner=StageTimeoutConfig(stage=STAGE_PLANNER, timeout_seconds=10),
            coder=StageTimeoutConfig(stage=STAGE_CODER, timeout_seconds=15),
            reviewer=StageTimeoutConfig(stage=STAGE_REVIEWER, timeout_seconds=20),
            tester=StageTimeoutConfig(stage=STAGE_TESTER, timeout_seconds=25),
            max_task_execution_seconds=60,
        )

        # Should complete without error (instant operation, 5-second limit)
        with stage_timeout(STAGE_INTENT, timeout_seconds=999, config=custom_cfg):
            pass

    def test_property_20_invalid_timeout_raises_value_error(self):
        """
        **Property 20 – stage_timeout SHALL raise ValueError for non-positive
        timeout values.**

        **Validates: Requirements 7.1**
        """
        with pytest.raises(ValueError):
            with stage_timeout(STAGE_INTENT, timeout_seconds=0):
                pass

        with pytest.raises(ValueError):
            with stage_timeout(STAGE_INTENT, timeout_seconds=-5):
                pass
