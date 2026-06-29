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
    payload: dict[str, Any] = field(default_factory=dict)

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
    version: int = 1
    content_hash: str = ""
    validated_at: str | None = None
    reviewer: str | None = None
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


def content_hash(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _snapshot_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return a compact rollback snapshot without recursive event history."""
    return {
        "status": item.get("status"),
        "content": item.get("content", ""),
        "summary": item.get("summary", ""),
        "sources": list(item.get("sources", [])),
        "kg_validation": dict(item.get("kg_validation", {})),
        "model": item.get("model"),
        "metadata": dict(item.get("metadata", {})),
        "validated_at": item.get("validated_at"),
        "reviewer": item.get("reviewer"),
        "version": item.get("version", 1),
        "content_hash": item.get("content_hash", ""),
    }


def _assert_status_requirements(item: dict[str, Any], status: MemoryStatus):
    """Prevent ungrounded or contradicted content from becoming reusable memory."""
    if status in {"pending", "validated"} and not item.get("sources"):
        raise ValueError(f"Memory status {status!r} requires at least one source")

    kg_validation = item.get("kg_validation") or {}
    if status == "validated" and kg_validation.get("status") == "hard_contradiction":
        raise ValueError("Cannot validate memory with KG hard contradiction")


def is_reusable_memory_item(item: dict[str, Any]) -> bool:
    """True only when an item may be reused as generated-memory knowledge."""
    try:
        _assert_status_requirements(item, "validated")
    except ValueError:
        return False
    return item.get("status") == "validated"


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
        version=1,
        content_hash=content_hash(content),
        validated_at=now if status == "validated" else None,
        reviewer=actor if status == "validated" else None,
        events=[event.to_dict()],
        metadata=metadata or {},
    ).to_dict()
    _assert_status_requirements(item, status)

    path = memory_path(universe_id, root)
    items = [existing for existing in read_memory_items(path) if existing.get("memory_id") != memory_id]
    items.append(item)
    write_memory_items(path, sorted(items, key=lambda entry: entry["memory_id"]))
    return item


def create_memory_candidate_from_validation(
    *,
    universe_id: str,
    content: str,
    summary: str,
    validation: dict[str, Any],
    sources: list[str] | None = None,
    model: str | None = None,
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Create a pending candidate only when validation supports human review.

    This does not auto-validate generated content. It only moves outputs that
    passed automated checks into `pending` so a human can approve or reject them.
    """
    if validation.get("status") == "hard_contradiction":
        raise ValueError("Cannot create memory candidate from KG hard contradiction")

    source_values = sources or [
        str(hit.get("citation") or hit.get("source_path"))
        for hit in validation.get("retrieval_hits", [])
        if hit.get("citation") or hit.get("source_path")
    ]
    if not source_values:
        source_values = [
            str(item.get("sentence"))
            for item in validation.get("source_coverage", [])
            if item.get("supported")
        ]

    return create_memory_item(
        universe_id=universe_id,
        content=content,
        summary=summary,
        sources=source_values,
        kg_validation=validation.get("kg", {}),
        model=model,
        status="pending",
        actor=actor,
        metadata={
            **(metadata or {}),
            "validation_status": validation.get("status"),
            "source_count": validation.get("source_count", 0),
        },
        root=root,
    )


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
        candidate = dict(item)
        candidate["status"] = new_status
        _assert_status_requirements(candidate, new_status)
        now = utc_now()
        event = MemoryEvent("status_changed", new_status, actor, note, now).to_dict()
        updated = dict(item)
        updated["status"] = new_status
        updated["updated_at"] = now
        if new_status == "validated":
            updated["validated_at"] = now
            updated["reviewer"] = actor
        updated["events"] = [*item.get("events", []), event]
        items[index] = updated
        write_memory_items(path, items)
        return updated
    raise KeyError(f"Memory item not found: {memory_id}")


def edit_memory_item(
    memory_id: str,
    *,
    universe_id: str,
    actor: str,
    content: str | None = None,
    summary: str | None = None,
    sources: list[str] | None = None,
    kg_validation: dict[str, Any] | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
    note: str = "",
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Edit a memory item and reset it to draft for review."""
    path = memory_path(universe_id, root)
    items = read_memory_items(path)
    for index, item in enumerate(items):
        if item.get("memory_id") != memory_id:
            continue
        now = utc_now()
        previous = _snapshot_item(item)
        updated = dict(item)
        if content is not None:
            updated["content"] = content
            updated["content_hash"] = content_hash(content)
        if summary is not None:
            updated["summary"] = summary
        if sources is not None:
            updated["sources"] = sources
        if kg_validation is not None:
            updated["kg_validation"] = kg_validation
        if model is not None:
            updated["model"] = model
        if metadata is not None:
            updated["metadata"] = metadata
        updated["status"] = "draft"
        updated["validated_at"] = None
        updated["reviewer"] = None
        updated["updated_at"] = now
        updated["version"] = int(item.get("version", 1)) + 1
        event = MemoryEvent(
            "edited",
            "draft",
            actor,
            note or "memory edited; review required",
            now,
            payload={"previous_item": previous},
        ).to_dict()
        updated["events"] = [*item.get("events", []), event]
        items[index] = updated
        write_memory_items(path, items)
        return updated
    raise KeyError(f"Memory item not found: {memory_id}")


def rollback_memory_item(
    memory_id: str,
    *,
    universe_id: str,
    actor: str,
    note: str = "",
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Rollback content fields to the latest stored pre-edit snapshot."""
    path = memory_path(universe_id, root)
    items = read_memory_items(path)
    for index, item in enumerate(items):
        if item.get("memory_id") != memory_id:
            continue
        previous = None
        for event in reversed(item.get("events", [])):
            payload = event.get("payload", {})
            if "previous_item" in payload:
                previous = payload["previous_item"]
                break
        if previous is None:
            raise ValueError(f"No rollback snapshot available for memory item: {memory_id}")

        now = utc_now()
        updated = dict(item)
        for key in ("content", "summary", "sources", "kg_validation", "model", "metadata", "content_hash"):
            updated[key] = previous.get(key)
        updated["status"] = "draft"
        updated["validated_at"] = None
        updated["reviewer"] = None
        updated["updated_at"] = now
        updated["version"] = int(item.get("version", 1)) + 1
        event = MemoryEvent(
            "rolled_back",
            "draft",
            actor,
            note or f"rolled back to version {previous.get('version')}",
            now,
            payload={"rolled_back_to_version": previous.get("version")},
        ).to_dict()
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
        items = [item for item in items if is_reusable_memory_item(item)]
    elif status:
        items = [item for item in items if item.get("status") == status]
    return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)


def memory_history(
    memory_id: str,
    *,
    universe_id: str,
    root: Path = PROJECT_ROOT,
) -> list[dict[str, Any]]:
    """Return the event history for a memory item."""
    for item in read_memory_items(memory_path(universe_id, root)):
        if item.get("memory_id") == memory_id:
            return list(item.get("events", []))
    raise KeyError(f"Memory item not found: {memory_id}")
