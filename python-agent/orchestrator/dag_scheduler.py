from __future__ import annotations

from concurrent.futures import FIRST_EXCEPTION
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from dataclasses import dataclass
from typing import Any
from typing import Callable


@dataclass(frozen=True)
class DagNode:
    name: str
    run: Callable[[], Any]
    depends_on: tuple[str, ...] = ()


class DagScheduler:
    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max(1, max_workers)

    def run(self, nodes: list[DagNode]) -> dict[str, Any]:
        if not nodes:
            return {}

        by_name: dict[str, DagNode] = {}
        for node in nodes:
            if node.name in by_name:
                raise ValueError(f"duplicate DAG node name: {node.name}")
            by_name[node.name] = node

        for node in nodes:
            for dep in node.depends_on:
                if dep not in by_name:
                    raise ValueError(f"DAG node {node.name} depends on missing node: {dep}")

        remaining = set(by_name.keys())
        completed: set[str] = set()
        results: dict[str, Any] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            while remaining:
                ready = [
                    name
                    for name in sorted(remaining)
                    if all(dep in completed for dep in by_name[name].depends_on)
                ]
                if not ready:
                    unresolved = ",".join(sorted(remaining))
                    raise ValueError(f"DAG has cycle or unresolved dependency among: {unresolved}")

                futures: dict[Future[Any], str] = {}
                for name in ready:
                    futures[pool.submit(by_name[name].run)] = name

                done, _ = wait(futures.keys(), return_when=FIRST_EXCEPTION)
                first_error: tuple[str, BaseException] | None = None

                for future in done:
                    name = futures[future]
                    try:
                        results[name] = future.result()
                    except BaseException as exc:  # noqa: BLE001
                        first_error = (name, exc)

                if first_error is not None:
                    name, exc = first_error
                    raise RuntimeError(f"DAG node failed: {name}") from exc

                for pending in futures.keys():
                    if pending in done:
                        continue
                    name = futures[pending]
                    try:
                        results[name] = pending.result()
                    except BaseException as exc:  # noqa: BLE001
                        raise RuntimeError(f"DAG node failed: {name}") from exc

                for name in ready:
                    remaining.remove(name)
                    completed.add(name)

        return results

