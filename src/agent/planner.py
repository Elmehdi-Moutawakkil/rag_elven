"""Controlled agent planner and runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.llm_provider import LLMProvider, LLMRequest, generate_with_trace
from src.output_validation import validate_generated_output
from src.retrieval_adapter import retrieve_evidence


@dataclass(frozen=True)
class AgentStep:
    tool: str
    reason: str
    required: bool = True

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_request(user_input: str, *, mode: str = "normal") -> list[AgentStep]:
    """Create a conservative fixed plan for a request."""
    lowered = user_input.lower()
    steps = [
        AgentStep("retrieve", "Find source chunks before answering."),
    ]
    if any(word in lowered for word in ("validate", "contradiction", "canon", "coherent")):
        steps.append(AgentStep("kg_validate", "Check request or draft against the Knowledge Graph."))
    steps.append(AgentStep("generate", "Produce an answer from retrieved context."))
    steps.append(AgentStep("validate_output", "Validate output before returning it."))
    if mode == "lab":
        steps.append(AgentStep("expose_trace", "Expose all intermediate inputs and outputs."))
    return steps


def build_generation_prompt(user_input: str, sources: list[dict[str, Any]]) -> str:
    excerpts = "\n\n".join(
        f"[{index + 1}] {source.get('source_path')}:\n{source.get('text', '')[:900]}"
        for index, source in enumerate(sources[:4])
    )
    return (
        "Answer using the provided sources. Cite uncertainty when sources are weak.\n\n"
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
    plan = plan_request(user_input, mode=mode)
    trace: list[dict[str, Any]] = []

    sources = retrieve_evidence(user_input, universe_id=universe_id, k=k)
    trace.append({"tool": "retrieve", "status": "ok", "result_count": len(sources)})

    if provider:
        prompt = build_generation_prompt(user_input, sources)
        generation = generate_with_trace(provider, LLMRequest(prompt=prompt))
        if generation.ok and generation.response:
            final_output = generation.response.text
            trace.append({
                "tool": "generate",
                "status": "ok",
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
                "provider": generation.provider,
                "model": generation.model,
                "duration_ms": generation.duration_ms,
                "error": generation.error,
            })
    else:
        final_output = sources[0]["text"] if sources else "Aucune source pertinente trouvee."
        trace.append({"tool": "generate", "status": "skipped", "reason": "no provider configured"})

    validation = validate_generated_output(
        final_output,
        universe_id=universe_id,
        retrieval_hits=sources,
    )
    trace.append({"tool": "validate_output", "status": validation["status"]})
    if mode == "lab":
        trace.append({"tool": "expose_trace", "status": "ok"})

    return AgentRun(
        user_input=user_input,
        universe_id=universe_id,
        plan=[step.to_dict() for step in plan],
        trace=trace,
        final_output=final_output,
        validation=validation,
        sources=sources,
    )
