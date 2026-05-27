from __future__ import annotations

from unittest.mock import MagicMock

from memory.redis_memory import RedisMemory


def test_redis_memory_fallback_stores_and_reads_recent_records() -> None:
    memory = RedisMemory(backend="memory", namespace="test:memory:fallback", max_entries=3)
    key = "demo-project"

    memory.append(key, {"intent": "code_change", "testCommand": "echo test_1"})
    memory.append(key, {"intent": "deploy", "deployCommand": "echo deploy_1"})
    memory.append(key, {"intent": "test", "command": "echo test_2"})
    memory.append(key, {"intent": "analyze", "status": "done"})

    recent = memory.recent(key, limit=3)

    assert len(recent) == 3
    assert recent[0]["intent"] == "deploy"
    assert recent[1]["intent"] == "test"
    assert recent[2]["intent"] == "analyze"


def test_redis_memory_builds_project_key_from_task_fields() -> None:
    memory = RedisMemory(backend="memory", namespace="test:memory:key")

    key1 = memory.project_key_for_task({"projectId": "Project-A"})
    key2 = memory.project_key_for_task({"workspacePath": "D:\\Work\\Repo"})
    key3 = memory.project_key_for_task({"sessionKey": "sess_1"})
    key4 = memory.project_key_for_task({})

    assert key1 == "project-a"
    assert key2 == "d_/work/repo"
    assert key3 == "sess_1"
    assert key4 == "default"


def test_store_and_get_code_knowledge_with_mock_redis() -> None:
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    memory = RedisMemory(backend="memory", namespace="test:mem", redis_client=mock_redis)
    memory._redis = mock_redis

    knowledge = {"pattern": "MVC", "lang": "python"}
    memory.store_code_knowledge("proj1", knowledge)

    mock_redis.hset.assert_called_once()
    call_args = mock_redis.hset.call_args
    assert "proj1:knowledge" in call_args[0][0]


def test_get_code_knowledge_no_redis() -> None:
    memory = RedisMemory(backend="memory", namespace="test:mem")
    assert memory.get_code_knowledge("proj1") == {}


def test_store_and_get_file_summaries_with_mock_redis() -> None:
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    memory = RedisMemory(backend="memory", namespace="test:mem", redis_client=mock_redis)
    memory._redis = mock_redis

    memory.store_file_summary("proj1", "src/main.ts", "Main entry point")
    mock_redis.hset.assert_called_once_with("test:mem:proj1:file_summaries", "src/main.ts", "Main entry point")

    mock_redis.hgetall.return_value = {b"src/main.ts": b"Main entry point"}
    result = memory.get_file_summaries("proj1")
    assert result == {"src/main.ts": "Main entry point"}


def test_get_file_summaries_no_redis() -> None:
    memory = RedisMemory(backend="memory", namespace="test:mem")
    assert memory.get_file_summaries("proj1") == {}


def test_store_and_get_error_pattern_with_mock_redis() -> None:
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    memory = RedisMemory(backend="memory", namespace="test:mem", redis_client=mock_redis)
    memory._redis = mock_redis

    memory.store_error_pattern("proj1", "TypeError: x is undefined", "add null check")
    mock_redis.hset.assert_called_once()
    key_arg = mock_redis.hset.call_args[0][0]
    assert "error_fixes" in key_arg

    import hashlib
    error_hash = hashlib.md5(b"TypeError: x is undefined").hexdigest()[:12]
    mock_redis.hget.return_value = b"TypeError: x is undefined\n---\nadd null check"
    fixes = memory.get_error_fixes("proj1", "TypeError: x is undefined")
    assert fixes == ["add null check"]
    mock_redis.hget.assert_called_once_with(f"test:mem:proj1:error_fixes", error_hash)


def test_get_error_fixes_no_redis() -> None:
    memory = RedisMemory(backend="memory", namespace="test:mem")
    assert memory.get_error_fixes("proj1", "some error") == []


def test_get_error_fixes_miss() -> None:
    mock_redis = MagicMock()
    mock_redis.ping.return_value = True
    mock_redis.hget.return_value = None
    memory = RedisMemory(backend="memory", namespace="test:mem", redis_client=mock_redis)
    memory._redis = mock_redis
    assert memory.get_error_fixes("proj1", "nonexistent") == []

