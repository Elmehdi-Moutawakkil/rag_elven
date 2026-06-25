"""Shared module contracts for Normal Mode and Lab Mode.

This file defines the stable module abstraction. Existing Lab Mode layers can
be adapted into this contract without rewriting their runtime logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal


ModuleStatus = Literal["stable", "experimental", "future", "disabled"]
ModuleCost = Literal["free", "groq", "claude", "gpu", "local", "unknown"]
ModuleConfidence = Literal["high", "medium", "low", "unknown"]
ModuleRunner = Callable[[Any, dict[str, Any]], Any]


@dataclass(frozen=True)
class ModuleDefinition:
    """Contract declared by every composable module."""

    id: str
    name: str
    description: str
    status: ModuleStatus
    input_types: list[str]
    output_type: str
    dependencies: list[str]
    run: ModuleRunner | None
    cost: ModuleCost = "unknown"
    deterministic: bool = False
    confidence: ModuleConfidence = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.status in {"stable", "experimental"} and self.run is not None


@dataclass
class ModuleResult:
    """Standard execution result returned by modules."""

    output: Any
    output_type: str
    label: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
