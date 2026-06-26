"""Validated lore memory store.

Generated content is never canon by default. This module stores generated or
human-authored memory candidates with explicit review status transitions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from src.settings import PROJECT_ROOT


MemoryStatus = Literal["draft", "pending", "validated", "rejected", "superseded"]
MEMORY_SCHEMA_VERSION = 1
ALLOWED_TRANSITIONS: dict[MemoryStatus, set[MemoryStatus]] = {
    "draft": {"pending", "rejected"},
    "pending": {"validated", "rejected", "draft"},
    "validated": {"superseded", "rejected"},
    "rejected": {"draft"},
    "superseded": set(),
}


@dataclass(frozen=True)
class MemoryEvent:
    event_type: str
    status: MemoryStatus
    actor: str
    note: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryItem:
    schema_version: int
    memory_id: str
    universe_id: str
    status: MemoryStatus
    content: str
    summary: str
    sources: list[str]
    kg_validation: dict[str, Any]
    model: str | None
    created_at: str
    updated_at: str
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def memory_path(universe_id: str, root: Path = PROJECT_ROOT) -> Path:
    return root / "memory" / universe_id / "memory.jsonl"


def stable_memory_id(universe_id: str, content: str, sources: list[str]) -> str:
    payload = json.dumps({"universe_id": universe_id, "content": content, "sources": sources}, sort_keys=True)
    return f"mem_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def read_memory_items(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def write_memory_items(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def create_memory_item(
    *,
    universe_id: str,
    content: str,
    summary: str,
    sources: list[str],
    kg_validation: dict[str, Any] | None = None,
    model: str | None = None,
    status: MemoryStatus = "draft",
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Create or replace a deterministic memory item."""
    now = utc_now()
    memory_id = stable_memory_id(universe_id, content, sources)
    event = MemoryEvent("created", status, actor, "memory candidate created", now)
    item = MemoryItem(
        schema_version=MEMORY_SCHEMA_VERSION,
        memory_id=memory_id,
        universe_id=universe_id,
        status=status,
        content=content,
        summary=summary,
        sources=sources,
        kg_validation=kg_validation or {},
        model=model,
        created_at=now,
        updated_at=now,
        events=[event.to_dict()],
        metadata=metadata or {},
    ).to_dict()

    path = memory_path(universe_id, root)
    items = [existing for existing in read_memory_items(path) if existing.get("memory_id") != memory_id]
    items.append(item)
    write_memory_items(path, sorted(items, key=lambda entry: entry["memory_id"]))
    return item


def transition_memory_item(
    memory_id: str,
    *,
    universe_id: str,
    new_status: MemoryStatus,
    actor: str,
    note: str = "",
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Move a memory item through an allowed review transition."""
    path = memory_path(universe_id, root)
    items = read_memory_items(path)
    for index, item in enumerate(items):
        if item.get("memory_id") != memory_id:
            continue
        old_status = item.get("status")
        allowed = ALLOWED_TRANSITIONS.get(old_status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid memory transition: {old_status} -> {new_status}")
        now = utc_now()
        event = MemoryEvent("status_changed", new_status, actor, note, now).to_dict()
        updated = dict(item)
        updated["status"] = new_status
        updated["updated_at"] = now
        updated["events"] = [*item.get("events", []), event]
        items[index] = updated
        write_memory_items(path, items)
        return updated
    raise KeyError(f"Memory item not found: {memory_id}")


def list_memory_items(
    *,
    universe_id: str,
    status: MemoryStatus | None = None,
    reusable_only: bool = False,
    root: Path = PROJECT_ROOT,
) -> list[dict[str, Any]]:
    """List memory items, optionally filtered to validated reusable knowledge."""
    items = read_memory_items(memory_path(universe_id, root))
    if reusable_only:
        items = [item for item in items if item.get("status") == "validated"]
    elif status:
        items = [item for item in items if item.get("status") == status]
    return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)
