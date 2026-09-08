"""Official Normal Mode pipelines.

Normal Mode hides module composition from the user, but it should still run on
the same module executor as Lab Mode.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.universe_registry import get_universe_registry, resolve_universe


NORMAL_PIPELINES: dict[str, list[str]] = {
    "qa": ["L01", "L02", "L03", "L13"],
    "translate": ["L04", "L05", "L06"],
    "lore": ["L01", "L02", "L07", "L08", "L09"],
}

UNIVERSE_LABELS: dict[str, str] = {
    "tolkien": "Tolkien / Elvish",
    "terran_empire": "Terran Empire",
}

TERRAN_KEYWORDS = [
    "star trek",
    "terran empire",
    "terran",
    "mirror universe",
    "mirror spock",
    "spock",
    "kirk",
    "terok nor",
    "cardassian",
    "klingon-cardassian",
    "alliance",
    "agony booth",
    "iss enterprise",
    "intendant",
]


@dataclass(frozen=True)
class NormalModeResolution:
    status: str
    universe_id: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"


def detect_universe_for_input(user_input: str) -> str | None:
    """Return a certain detected universe, never a silent Tolkien fallback."""
    resolution = resolve_universe("Auto", query=user_input)
    return resolution.universe_id if resolution.ok else None


def resolve_normal_universe(route: str, user_input: str, selection: str | None = None) -> NormalModeResolution:
    """Resolve Normal Mode selection before any route executes."""
    resolution = resolve_universe(selection, query=user_input, registry=get_universe_registry())
    if not resolution.ok:
        return NormalModeResolution(resolution.status, error=resolution.error)
    if route == "translate" and resolution.universe_id != "tolkien":
        return NormalModeResolution(
            "CAPABILITY_UNSUPPORTED",
            universe_id=resolution.universe_id,
            error="Translation is available only for the Tolkien / Elvish universe",
        )
    return NormalModeResolution("SUCCESS", universe_id=resolution.universe_id)


def pipeline_for_route(route: str, *, universe_id: str | None = None) -> list[str]:
    """Return the official module sequence for a Normal Mode route."""
    try:
        modules = NORMAL_PIPELINES[route]
    except KeyError as exc:
        raise ValueError(f"Unknown Normal Mode route: {route}") from exc
    if universe_id is None:
        raise ValueError("UNIVERSE_REQUIRED")
    if route == "translate" and universe_id != "tolkien":
        raise ValueError("CAPABILITY_UNSUPPORTED")
    if universe_id != "tolkien":
        return [module_id for module_id in modules if module_id not in {"L03", "L04", "L05", "L06"}]
    return modules


def normalize_input_for_route(route: str, user_input: str) -> str:
    """Prepare user input before passing it to a route pipeline."""
    text = user_input.strip()
    if route != "translate":
        return text

    return re.sub(
        r"^(translate[:\s]+|traduis[:\s]+|traduction[:\s]+|how do you say[:\s]+|comment dit-on[:\s]+)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip().strip('"').strip("'")
