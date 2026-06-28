"""Official Normal Mode pipelines.

Normal Mode hides module composition from the user, but it should still run on
the same module executor as Lab Mode.
"""

from __future__ import annotations

import re


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


def detect_universe_for_input(user_input: str) -> str:
    """Detect the target universe for Normal Mode."""
    lowered = user_input.lower()
    if any(keyword in lowered for keyword in TERRAN_KEYWORDS):
        return "terran_empire"
    return "tolkien"


def resolve_normal_universe(route: str, user_input: str, selection: str = "Auto") -> str:
    """Resolve the effective Normal Mode universe from UI selection and input."""
    if route == "translate":
        return "tolkien"
    if selection == "Empire Terran":
        return "terran_empire"
    if selection == "Tolkien / Elfique":
        return "tolkien"
    return detect_universe_for_input(user_input)


def pipeline_for_route(route: str, *, universe_id: str = "tolkien") -> list[str]:
    """Return the official module sequence for a Normal Mode route."""
    try:
        modules = NORMAL_PIPELINES[route]
    except KeyError as exc:
        raise ValueError(f"Unknown Normal Mode route: {route}") from exc
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
