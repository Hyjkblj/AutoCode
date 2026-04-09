from __future__ import annotations

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

