from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - import fallback is covered by runtime behavior tests
    END = "__end__"
    START = "__start__"
    StateGraph = None


@dataclass(frozen=True)
class LangGraphExecutionResult:
    handled: bool
    terminal_event_type: str
    terminal_payload: dict[str, Any]
    memory_record: dict[str, Any]
    task_status: str
    reason: str = ""


class _RuntimeState(TypedDict, total=False):
    intent: str
    result: LangGraphExecutionResult


class LangGraphRuntime:
    def supports(self, intent: str) -> bool:
        return (intent or "").strip().lower() in {"analyze", "test"}

    def execute(
        self,
        *,
        intent: str,
        publish_event: Callable[[dict[str, Any], str], None],
        analyze_handler: Callable[[], LangGraphExecutionResult],
        test_handler: Callable[[], LangGraphExecutionResult],
    ) -> LangGraphExecutionResult:
        normalized_intent = (intent or "").strip().lower()
        backend = "langgraph" if StateGraph is not None else "internal_fallback"
        publish_event(
            {
                "stage": "LangGraphRuntime",
                "message": "Executing task via staged runtime.",
                "intent": normalized_intent,
                "graphBackend": backend,
            }
        )

        if not self.supports(normalized_intent):
            return LangGraphExecutionResult(
                handled=False,
                terminal_event_type="",
                terminal_payload={},
                memory_record={},
                task_status="skipped",
                reason="unsupported_intent",
            )

        if StateGraph is None:
            return self._dispatch(normalized_intent, analyze_handler=analyze_handler, test_handler=test_handler)

        try:
            return self._invoke_langgraph(
                normalized_intent,
                analyze_handler=analyze_handler,
                test_handler=test_handler,
            )
        except Exception as exc:  # noqa: BLE001
            publish_event(
                {
                    "stage": "LangGraphRuntime",
                    "message": "LangGraph execution failed, falling back to internal dispatcher.",
                    "intent": normalized_intent,
                    "error": str(exc),
                }
            )
            return self._dispatch(normalized_intent, analyze_handler=analyze_handler, test_handler=test_handler)

    @staticmethod
    def _dispatch(
        intent: str,
        *,
        analyze_handler: Callable[[], LangGraphExecutionResult],
        test_handler: Callable[[], LangGraphExecutionResult],
    ) -> LangGraphExecutionResult:
        if intent == "analyze":
            return analyze_handler()
        if intent == "test":
            return test_handler()
        return LangGraphExecutionResult(
            handled=False,
            terminal_event_type="",
            terminal_payload={},
            memory_record={},
            task_status="skipped",
            reason="unsupported_intent",
        )

    @staticmethod
    def _invoke_langgraph(
        intent: str,
        *,
        analyze_handler: Callable[[], LangGraphExecutionResult],
        test_handler: Callable[[], LangGraphExecutionResult],
    ) -> LangGraphExecutionResult:
        if StateGraph is None:
            raise RuntimeError("langgraph package is not available")

        builder = StateGraph(_RuntimeState)
        builder.add_node("route", lambda state: state)
        builder.add_node("analyze", lambda _state: {"result": analyze_handler()})
        builder.add_node("test", lambda _state: {"result": test_handler()})
        builder.add_node(
            "unsupported",
            lambda _state: {
                "result": LangGraphExecutionResult(
                    handled=False,
                    terminal_event_type="",
                    terminal_payload={},
                    memory_record={},
                    task_status="skipped",
                    reason="unsupported_intent",
                )
            },
        )
        builder.add_edge(START, "route")
        builder.add_conditional_edges(
            "route",
            lambda state: state.get("intent", "unsupported"),
            {
                "analyze": "analyze",
                "test": "test",
                "unsupported": "unsupported",
            },
        )
        builder.add_edge("analyze", END)
        builder.add_edge("test", END)
        builder.add_edge("unsupported", END)
        graph = builder.compile()
        result = graph.invoke({"intent": intent})
        execution_result = result.get("result")
        if not isinstance(execution_result, LangGraphExecutionResult):
            raise RuntimeError("langgraph runtime returned invalid result")
        return execution_result
