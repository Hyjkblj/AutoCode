from __future__ import annotations

import threading

from orchestrator.dag_scheduler import DagNode, DagScheduler


def test_dag_scheduler_runs_ready_nodes_in_parallel() -> None:
    barrier = threading.Barrier(2, timeout=1.0)
    completed: list[str] = []
    lock = threading.Lock()

    def run_a() -> str:
        barrier.wait(timeout=1.0)
        with lock:
            completed.append("a")
        return "A"

    def run_b() -> str:
        barrier.wait(timeout=1.0)
        with lock:
            completed.append("b")
        return "B"

    scheduler = DagScheduler(max_workers=2)
    result = scheduler.run([DagNode("a", run_a), DagNode("b", run_b)])

    assert set(completed) == {"a", "b"}
    assert result["a"] == "A"
    assert result["b"] == "B"


def test_dag_scheduler_respects_dependencies() -> None:
    execution_order: list[str] = []

    def run_a() -> str:
        execution_order.append("a")
        return "A"

    def run_b() -> str:
        execution_order.append("b")
        return "B"

    def run_c() -> str:
        execution_order.append("c")
        return "C"

    scheduler = DagScheduler(max_workers=3)
    result = scheduler.run(
        [
            DagNode("a", run_a),
            DagNode("b", run_b),
            DagNode("c", run_c, depends_on=("a", "b")),
        ]
    )

    assert result["c"] == "C"
    assert execution_order[-1] == "c"

