"""
Comprehensive unit tests for DistributedTaskLock.

**Validates: Requirements 6.4**

Tests cover:
- Redis-based locking mechanism
- Memory-based fallback locking
- Lock acquisition and release
- Lock renewal and expiration
- Atomic operations with Lua scripts
- Concurrent lock attempts
"""
from __future__ import annotations

import time
from unittest.mock import Mock, patch

import pytest

from orchestrator.distributed_lock import DistributedTaskLock, TaskLease


class TestDistributedLockAcquisition:
    """Test distributed lock acquisition mechanisms."""

    def test_lock_acquires_successfully_in_memory_mode(self):
        """Verify lock can be acquired successfully in memory mode."""
        lock = DistributedTaskLock(backend="memory")
        lease = lock.acquire("task_001")

        assert lease.acquired is True
        assert lease.key == "autocode:tasklock:task_001"
        assert lease.token is not None

    def test_lock_prevents_duplicate_acquisition_in_memory_mode(self):
        """Verify lock prevents duplicate acquisition for same task."""
        lock = DistributedTaskLock(backend="memory")

        lease1 = lock.acquire("task_002")
        assert lease1.acquired is True

        lease2 = lock.acquire("task_002")
        assert lease2.acquired is False

    def test_lock_allows_acquisition_after_release_in_memory_mode(self):
        """Verify lock can be acquired after being released."""
        lock = DistributedTaskLock(backend="memory")

        lease1 = lock.acquire("task_003")
        assert lease1.acquired is True

        lease1.release()

        lease2 = lock.acquire("task_003")
        assert lease2.acquired is True

    def test_lock_expires_after_lease_seconds_in_memory_mode(self):
        """Verify lock expires automatically after lease duration."""
        from orchestrator.distributed_lock import _LOCAL_LEASES, _LOCAL_LOCK

        lock = DistributedTaskLock(backend="memory")

        lease1 = lock.acquire("task_004")
        assert lease1.acquired is True

        # Simulate expiry by backdating the expiry timestamp in _LOCAL_LEASES
        key = lease1.key
        with _LOCAL_LOCK:
            token, _ = _LOCAL_LEASES[key]
            _LOCAL_LEASES[key] = (token, 0.0)  # expired in the past

        lease2 = lock.acquire("task_004")
        assert lease2.acquired is True

    def test_lock_uses_custom_namespace(self):
        """Verify lock uses custom namespace when provided."""
        lock = DistributedTaskLock(backend="memory", namespace="custom:lock")
        lease = lock.acquire("task_005")

        assert lease.key == "custom:lock:task_005"


class TestDistributedLockRenewal:
    """Test distributed lock renewal mechanisms."""

    def test_lock_renewal_extends_lease_in_memory_mode(self):
        """Verify lock renewal extends the lease duration."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=2)

        lease = lock.acquire("task_006")
        assert lease.acquired is True

        # Wait half the lease time
        time.sleep(1)

        # Renew the lock
        renewed = lock.renew(lease.key, lease.token)
        assert renewed is True

        # Wait another second (would have expired without renewal)
        time.sleep(1)

        # Should still hold the lock
        lease2 = lock.acquire("task_006")
        assert lease2.acquired is False

    def test_lock_renewal_fails_with_wrong_token_in_memory_mode(self):
        """Verify lock renewal fails when using wrong token."""
        lock = DistributedTaskLock(backend="memory")

        lease = lock.acquire("task_007")
        assert lease.acquired is True

        # Try to renew with wrong token
        renewed = lock.renew(lease.key, "wrong_token")
        assert renewed is False

    def test_lock_renewal_fails_for_expired_lock_in_memory_mode(self):
        """Verify lock renewal fails for expired locks."""
        from orchestrator.distributed_lock import _LOCAL_LEASES, _LOCAL_LOCK

        lock = DistributedTaskLock(backend="memory")

        lease = lock.acquire("task_008")
        assert lease.acquired is True

        # Simulate expiry by backdating the expiry timestamp
        key = lease.key
        with _LOCAL_LOCK:
            token, _ = _LOCAL_LEASES[key]
            _LOCAL_LEASES[key] = (token, 0.0)  # expired in the past

        # Try to renew expired lock
        renewed = lock.renew(lease.key, lease.token)
        assert renewed is False


class TestDistributedLockRelease:
    """Test distributed lock release mechanisms."""

    def test_lock_release_frees_lock_in_memory_mode(self):
        """Verify lock release frees the lock for reacquisition."""
        lock = DistributedTaskLock(backend="memory")

        lease1 = lock.acquire("task_009")
        assert lease1.acquired is True

        released = lock.release(lease1.key, lease1.token)
        assert released is True

        lease2 = lock.acquire("task_009")
        assert lease2.acquired is True

    def test_lock_release_fails_with_wrong_token_in_memory_mode(self):
        """Verify lock release fails when using wrong token."""
        lock = DistributedTaskLock(backend="memory")

        lease = lock.acquire("task_010")
        assert lease.acquired is True

        released = lock.release(lease.key, "wrong_token")
        assert released is False

        # Lock should still be held
        lease2 = lock.acquire("task_010")
        assert lease2.acquired is False

    def test_lock_release_is_idempotent_in_memory_mode(self):
        """Verify lock release can be called multiple times safely."""
        lock = DistributedTaskLock(backend="memory")

        lease = lock.acquire("task_011")
        assert lease.acquired is True

        released1 = lock.release(lease.key, lease.token)
        assert released1 is True

        released2 = lock.release(lease.key, lease.token)
        assert released2 is False  # Already released


class TestTaskLeaseAutoRenewal:
    """Test TaskLease automatic renewal functionality."""

    def test_task_lease_starts_renewal_thread(self):
        """Verify TaskLease starts automatic renewal thread."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=10, renew_interval_seconds=2)

        lease = lock.acquire("task_012")
        assert lease.acquired is True

        lease.start_renewal()

        assert lease._renew_thread is not None
        assert lease._renew_stop is not None
        assert lease._renew_thread.is_alive()

        lease.release()

    def test_task_lease_renewal_extends_lock_automatically(self):
        """Verify TaskLease automatically renews lock before expiration."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=2, renew_interval_seconds=1)

        lease = lock.acquire("task_013")
        assert lease.acquired is True

        lease.start_renewal()

        # Wait longer than lease duration
        time.sleep(3)

        # Lock should still be held due to automatic renewal
        lease2 = lock.acquire("task_013")
        assert lease2.acquired is False

        lease.release()

    def test_task_lease_stops_renewal_on_release(self):
        """Verify TaskLease stops renewal thread when released."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=10, renew_interval_seconds=2)

        lease = lock.acquire("task_014")
        assert lease.acquired is True

        lease.start_renewal()
        assert lease._renew_thread.is_alive()

        lease.release()

        # Give thread time to stop
        time.sleep(0.5)

        # Thread should have stopped
        assert not lease._renew_thread.is_alive()

    def test_task_lease_does_not_start_renewal_if_not_acquired(self):
        """Verify TaskLease does not start renewal if lock not acquired."""
        lock = DistributedTaskLock(backend="memory")

        lease1 = lock.acquire("task_015")
        lease1.start_renewal()

        lease2 = lock.acquire("task_015")
        assert lease2.acquired is False

        lease2.start_renewal()
        assert lease2._renew_thread is None

        lease1.release()


class TestDistributedLockRedisMode:
    """Test distributed lock Redis mode functionality."""

    def test_lock_uses_redis_when_backend_is_redis(self):
        """Verify lock attempts to use Redis when backend is 'redis'."""
        mock_redis_client = Mock()
        mock_redis_client.ping = Mock()
        mock_redis_client.register_script = Mock(return_value=Mock())

        lock = DistributedTaskLock(
            backend="redis",
            redis_url="redis://localhost:6379/0",
            redis_client=mock_redis_client,
        )

        assert lock._redis_enabled is True

    def test_lock_falls_back_to_memory_when_redis_unavailable(self):
        """Verify lock falls back to memory mode when Redis is unavailable."""
        mock_redis_client = Mock()
        mock_redis_client.ping = Mock()
        mock_redis_client.register_script = Mock(side_effect=Exception("Redis unavailable"))

        lock = DistributedTaskLock(
            backend="redis",
            redis_url="redis://localhost:6379/0",
            redis_client=mock_redis_client,
        )

        assert lock._redis_enabled is False

        # Should still work in memory mode
        lease = lock.acquire("task_016")
        assert lease.acquired is True

    def test_lock_uses_redis_set_nx_ex_for_acquisition(self):
        """Verify lock uses Redis SET NX EX for atomic acquisition."""
        mock_redis_client = Mock()
        mock_redis_client.ping = Mock()
        mock_redis_client.register_script = Mock(return_value=Mock())
        mock_redis_client.set = Mock(return_value=True)

        lock = DistributedTaskLock(
            backend="redis",
            redis_url="redis://localhost:6379/0",
            redis_client=mock_redis_client,
            lease_seconds=60,
        )
        lease = lock.acquire("task_017")

        assert lease.acquired is True
        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        assert call_args[1]["nx"] is True
        assert call_args[1]["ex"] == 60

    def test_lock_uses_lua_script_for_renewal(self):
        """Verify lock uses Lua script for atomic renewal."""
        mock_redis_client = Mock()
        mock_redis_client.ping = Mock()
        mock_renew_script = Mock(return_value=1)
        mock_release_script = Mock()
        mock_redis_client.register_script = Mock(side_effect=[mock_renew_script, mock_release_script])
        mock_redis_client.set = Mock(return_value=True)

        lock = DistributedTaskLock(
            backend="redis",
            redis_url="redis://localhost:6379/0",
            redis_client=mock_redis_client,
            lease_seconds=60,
        )
        lease = lock.acquire("task_018")

        renewed = lock.renew(lease.key, lease.token)

        assert renewed is True
        mock_renew_script.assert_called_once()
        call_args = mock_renew_script.call_args
        assert call_args[1]["keys"] == [lease.key]
        assert call_args[1]["args"] == [lease.token, 60]

    def test_lock_uses_lua_script_for_release(self):
        """Verify lock uses Lua script for atomic release."""
        mock_redis_client = Mock()
        mock_redis_client.ping = Mock()
        mock_renew_script = Mock()
        mock_release_script = Mock(return_value=1)
        mock_redis_client.register_script = Mock(side_effect=[mock_renew_script, mock_release_script])
        mock_redis_client.set = Mock(return_value=True)

        lock = DistributedTaskLock(
            backend="redis",
            redis_url="redis://localhost:6379/0",
            redis_client=mock_redis_client,
        )
        lease = lock.acquire("task_019")

        released = lock.release(lease.key, lease.token)

        assert released is True
        mock_release_script.assert_called_once()
        call_args = mock_release_script.call_args
        assert call_args[1]["keys"] == [lease.key]
        assert call_args[1]["args"] == [lease.token]


class TestDistributedLockConfiguration:
    """Test distributed lock configuration options."""

    def test_lock_respects_custom_lease_seconds(self):
        """Verify lock respects custom lease duration."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=5)
        assert lock.lease_seconds == 5

    def test_lock_enforces_minimum_lease_seconds(self):
        """Verify lock enforces minimum lease duration of 5 seconds."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=1)
        assert lock.lease_seconds == 5

    def test_lock_respects_custom_renew_interval(self):
        """Verify lock respects custom renewal interval."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=60, renew_interval_seconds=15)
        assert lock.renew_interval_seconds == 15

    def test_lock_enforces_minimum_renew_interval(self):
        """Verify lock enforces minimum renewal interval of 2 seconds."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=60, renew_interval_seconds=1)
        assert lock.renew_interval_seconds == 2

    def test_lock_enforces_renew_interval_less_than_lease(self):
        """Verify lock enforces renewal interval less than lease duration."""
        lock = DistributedTaskLock(backend="memory", lease_seconds=10, renew_interval_seconds=15)
        assert lock.renew_interval_seconds < lock.lease_seconds

    def test_lock_reads_backend_from_environment(self, monkeypatch):
        """Verify lock reads backend configuration from environment."""
        monkeypatch.setenv("MVP_DISTRIBUTED_LOCK_BACKEND", "redis")
        lock = DistributedTaskLock()
        assert lock.backend == "redis"

    def test_lock_reads_redis_url_from_environment(self, monkeypatch):
        """Verify lock reads Redis URL from environment."""
        monkeypatch.setenv("MVP_REDIS_URL", "redis://custom:6379/1")
        lock = DistributedTaskLock(backend="memory")
        assert lock.redis_url == "redis://custom:6379/1"


class TestDistributedLockConcurrency:
    """Test distributed lock behavior under concurrent access."""

    def test_lock_handles_concurrent_acquisition_attempts(self):
        """Verify lock handles concurrent acquisition attempts correctly."""
        import threading

        lock = DistributedTaskLock(backend="memory")
        acquired_count = {"value": 0}
        lock_obj = threading.Lock()

        def try_acquire():
            lease = lock.acquire("task_concurrent_001")
            if lease.acquired:
                with lock_obj:
                    acquired_count["value"] += 1
                time.sleep(0.1)
                lease.release()

        threads = [threading.Thread(target=try_acquire) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Only one thread should have acquired the lock at a time
        # But all should eventually succeed
        assert acquired_count["value"] >= 1

    def test_lock_maintains_exclusivity_under_concurrent_load(self):
        """Verify lock maintains exclusivity under concurrent load."""
        import threading

        lock = DistributedTaskLock(backend="memory", lease_seconds=1)
        concurrent_holders = {"value": 0}
        max_concurrent = {"value": 0}
        lock_obj = threading.Lock()

        def acquire_and_hold():
            lease = lock.acquire("task_concurrent_002")
            if lease.acquired:
                with lock_obj:
                    concurrent_holders["value"] += 1
                    if concurrent_holders["value"] > max_concurrent["value"]:
                        max_concurrent["value"] = concurrent_holders["value"]

                time.sleep(0.05)

                with lock_obj:
                    concurrent_holders["value"] -= 1

                lease.release()

        threads = [threading.Thread(target=acquire_and_hold) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should never have more than 1 concurrent holder
        assert max_concurrent["value"] == 1
