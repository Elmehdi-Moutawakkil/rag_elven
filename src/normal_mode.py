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


def pipeline_for_route(route: str) -> list[str]:
    """Return the official module sequence for a Normal Mode route."""
    try:
        return NORMAL_PIPELINES[route]
    except KeyError as exc:
        raise ValueError(f"Unknown Normal Mode route: {route}") from exc


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
