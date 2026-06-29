"""Controlled agent planner and runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from src.llm_provider import LLMProvider, LLMRequest, generate_with_trace
from src.output_validation import validate_generated_output
from src.retrieval_adapter import retrieve_evidence


RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class AgentTool:
    name: str
    purpose: str
    risk_level: RiskLevel
    requires_confirmation: bool = False
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentStep:
    tool: str
    reason: str
    risk_level: RiskLevel = "low"
    required: bool = True
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentRun:
    user_input: str
    universe_id: str
    plan: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    final_output: str
    validation: dict[str, Any]
    sources: list[dict[str, Any]] = field(default_factory=list)
    risk_level: RiskLevel = "low"
    requires_human_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TOOL_REGISTRY: dict[str, AgentTool] = {
    "retrieve": AgentTool(
        name="retrieve",
        purpose="Find source chunks before answering.",
        risk_level="low",
        read_only=True,
    ),
    "kg_validate": AgentTool(
        name="kg_validate",
        purpose="Check claims against the Knowledge Graph.",
        risk_level="low",
        read_only=True,
    ),
    "generate": AgentTool(
        name="generate",
        purpose="Draft an answer from retrieved context.",
        risk_level="medium",
        read_only=True,
    ),
    "validate_output": AgentTool(
        name="validate_output",
        purpose="Validate generated output against sources, KG, and memory.",
        risk_level="low",
        read_only=True,
    ),
    "request_confirmation": AgentTool(
        name="request_confirmation",
        purpose="Stop before risky write, canonization, publishing, or budget-sensitive action.",
        risk_level="high",
        requires_confirmation=True,
        read_only=True,
    ),
    "expose_trace": AgentTool(
        name="expose_trace",
        purpose="Expose intermediate plan and tool trace for Lab Mode.",
        risk_level="low",
        read_only=True,
    ),
}


RISKY_TERMS = {
    "accept",
    "archive",
    "canonize",
    "commit",
    "delete",
    "overwrite",
    "publish",
    "push",
    "remove",
    "save",
    "validate memory",
    "write",
}


def available_tools() -> list[dict[str, Any]]:
    """Return the controlled tool surface exposed to the agent."""
    return [tool.to_dict() for tool in TOOL_REGISTRY.values()]


def _tool_step(tool_name: str, reason: str, *, required: bool = True) -> AgentStep:
    tool = TOOL_REGISTRY[tool_name]
    return AgentStep(
        tool=tool.name,
        reason=reason,
        risk_level=tool.risk_level,
        required=required,
        requires_confirmation=tool.requires_confirmation,
    )


def assess_request_risk(user_input: str, *, provider: LLMProvider | None = None) -> dict[str, Any]:
    """Classify user intent risk before tool execution."""
    lowered = user_input.lower()
    triggers = sorted(term for term in RISKY_TERMS if term in lowered)
    if triggers:
        return {
            "risk_level": "high",
            "requires_human_confirmation": True,
            "triggers": triggers,
            "reason": "Request appears to involve writes, publishing, canonization, or irreversible actions.",
        }
    if provider is not None:
        return {
            "risk_level": "medium",
            "requires_human_confirmation": False,
            "triggers": ["provider_generation"],
            "reason": "Generation uses an external or configured provider and must be validated.",
        }
    return {
        "risk_level": "low",
        "requires_human_confirmation": False,
        "triggers": [],
        "reason": "Read-only retrieval and validation path.",
    }


def plan_request(user_input: str, *, mode: str = "normal") -> list[AgentStep]:
    """Create a conservative fixed plan for a request."""
    lowered = user_input.lower()
    steps = [
        _tool_step("retrieve", "Find source chunks before answering."),
    ]
    if any(word in lowered for word in ("validate", "contradiction", "canon", "coherent")):
        steps.append(_tool_step("kg_validate", "Check request or draft against the Knowledge Graph."))
    if any(term in lowered for term in RISKY_TERMS):
        steps.append(_tool_step("request_confirmation", "Ask for human approval before risky action."))
    steps.append(_tool_step("generate", "Produce an answer from retrieved context."))
    steps.append(_tool_step("validate_output", "Validate output before returning it."))
    if mode == "lab":
        steps.append(_tool_step("expose_trace", "Expose all intermediate inputs and outputs."))
    return steps


def build_generation_prompt(user_input: str, sources: list[dict[str, Any]]) -> str:
    excerpts = "\n\n".join(
        f"[{index + 1}] {source.get('source_path')}:\n{source.get('text', '')[:900]}"
        for index, source in enumerate(sources[:4])
    )
    return (
        "Answer using the provided sources. Cite every factual claim with source ids like [1]. "
        "Distinguish canon-supported facts from extrapolation and say when evidence is weak.\n\n"
        f"Sources:\n{excerpts}\n\n"
        f"User request: {user_input}\n"
        "Answer:"
    )


def run_controlled_agent(
    user_input: str,
    *,
    universe_id: str = "terran_empire",
    mode: str = "normal",
    provider: LLMProvider | None = None,
    k: int = 4,
) -> AgentRun:
    """Run a transparent agent plan with a small allowed toolset."""
    risk = assess_request_risk(user_input, provider=provider)
    plan = plan_request(user_input, mode=mode)
    trace: list[dict[str, Any]] = [
        {
            "tool": "assess_risk",
            "status": "ok",
            "risk_level": risk["risk_level"],
            "requires_human_confirmation": risk["requires_human_confirmation"],
            "triggers": risk["triggers"],
        }
    ]

    if risk["requires_human_confirmation"]:
        validation = {
            "schema_version": 1,
            "universe_id": universe_id,
            "status": "blocked_pending_confirmation",
            "warnings": [risk["reason"]],
            "human_review_required": True,
        }
        trace.append({
            "tool": "request_confirmation",
            "status": "blocked",
            "reason": risk["reason"],
        })
        return AgentRun(
            user_input=user_input,
            universe_id=universe_id,
            plan=[step.to_dict() for step in plan],
            trace=trace,
            final_output="Validation humaine requise avant execution.",
            validation=validation,
            sources=[],
            risk_level=risk["risk_level"],
            requires_human_confirmation=True,
        )

    sources = retrieve_evidence(user_input, universe_id=universe_id, k=k)
    trace.append({
        "tool": "retrieve",
        "status": "ok",
        "risk_level": TOOL_REGISTRY["retrieve"].risk_level,
        "result_count": len(sources),
    })

    if provider:
        prompt = build_generation_prompt(user_input, sources)
        generation = generate_with_trace(provider, LLMRequest(prompt=prompt))
        if generation.ok and generation.response:
            final_output = generation.response.text
            trace.append({
                "tool": "generate",
                "status": "ok",
                "risk_level": TOOL_REGISTRY["generate"].risk_level,
                "provider": generation.provider,
                "model": generation.model,
                "duration_ms": generation.duration_ms,
                "usage": generation.usage,
                "cost_estimate_usd": generation.cost_estimate_usd,
            })
        else:
            final_output = sources[0]["text"] if sources else "Aucune source pertinente trouvee."
            trace.append({
                "tool": "generate",
                "status": "error",
                "risk_level": TOOL_REGISTRY["generate"].risk_level,
                "provider": generation.provider,
                "model": generation.model,
                "duration_ms": generation.duration_ms,
                "error": generation.error,
            })
    else:
        final_output = sources[0]["text"] if sources else "Aucune source pertinente trouvee."
        trace.append({
            "tool": "generate",
            "status": "skipped",
            "risk_level": TOOL_REGISTRY["generate"].risk_level,
            "reason": "no provider configured",
        })

    validation = validate_generated_output(
        final_output,
        universe_id=universe_id,
        retrieval_hits=sources,
    )
    trace.append({
        "tool": "validate_output",
        "status": validation["status"],
        "risk_level": TOOL_REGISTRY["validate_output"].risk_level,
    })
    if mode == "lab":
        trace.append({"tool": "expose_trace", "status": "ok", "risk_level": TOOL_REGISTRY["expose_trace"].risk_level})

    return AgentRun(
        user_input=user_input,
        universe_id=universe_id,
        plan=[step.to_dict() for step in plan],
        trace=trace,
        final_output=final_output,
        validation=validation,
        sources=sources,
        risk_level=risk["risk_level"],
        requires_human_confirmation=risk["requires_human_confirmation"],
    )
