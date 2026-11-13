"""Tool backend abstractions used by the security proxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolBackend(Protocol):
    def list_tools(self) -> list[ToolSpec]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class MappingBackend:
    """Simple dict-of-callables backend for tests and local mocks."""

    def __init__(
        self,
        tools: dict[str, Any],
        specs: list[ToolSpec] | None = None,
    ) -> None:
        self._tools = tools
        self._specs = specs or [
            ToolSpec(name=name, description=name, input_schema={"type": "object"})
            for name in tools
        ]

    def list_tools(self) -> list[ToolSpec]:
        return list(self._specs)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name](arguments)
