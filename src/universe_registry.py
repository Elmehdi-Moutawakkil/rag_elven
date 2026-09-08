"""Manifest-backed universe and semantic-index resolution.

The registry is the only runtime authority for universe resources. Callers
cannot select a path, metadata list, or FAISS index independently of its
manifested universe.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from src.settings import PROJECT_ROOT


UNIVERSE_REQUIRED = "UNIVERSE_REQUIRED"
UNIVERSE_UNKNOWN = "UNIVERSE_UNKNOWN"
SELECTION_REQUIRED = "SELECTION_REQUIRED"

ResolutionStatus = Literal["SUCCESS", "UNIVERSE_REQUIRED", "UNIVERSE_UNKNOWN", "SELECTION_REQUIRED"]


class UniverseRegistryError(ValueError):
    """Raised when a universe or a declared resource cannot be resolved."""


@dataclass(frozen=True)
class UniverseConfig:
    universe_id: str
    display_name: str
    status: str
    manifest_path: Path
    source_files: tuple[str, ...]
    collection_paths: tuple[str, ...]
    collection_canon_status: tuple[tuple[str, str | None], ...]
    text_chunks_path: Path | None
    semantic_index_path: Path | None
    semantic_metadata_path: Path | None
    dictionary_path: Path | None
    knowledge_graph_path: Path | None


@dataclass(frozen=True)
class UniverseResolution:
    status: ResolutionStatus
    universe_id: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "SUCCESS"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata_snapshot(metadata: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _index_snapshot(index: Any) -> str:
    """Fingerprint serialized FAISS contents; fail closed for unknown objects."""
    try:
        import faiss

        return hashlib.sha256(faiss.serialize_index(index).tobytes()).hexdigest()
    except Exception as exc:
        raise UniverseRegistryError("FAISS index cannot be serialized for binding") from exc


def _metadata_file_snapshot(path: Path) -> str:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise UniverseRegistryError("FAISS metadata must be a JSON array")
    return _metadata_snapshot(loaded)


@dataclass(frozen=True)
class SemanticIndexHandle:
    """A semantic index bound to one universe and its declared artifacts."""

    universe_id: str
    index_path: Path
    metadata_path: Path
    index: Any
    metadata: list[dict[str, Any]]
    artifact_index_sha256: str
    artifact_metadata_sha256: str
    loaded_index_snapshot: str
    loaded_metadata_snapshot: str
    index_object_id: int

    def validate(self, config: UniverseConfig) -> None:
        """Reject swapped files, metadata, or in-memory index mutation."""
        if self.universe_id != config.universe_id:
            raise UniverseRegistryError("SemanticIndexHandle universe does not match requested universe")
        if self.index_path != config.semantic_index_path or self.metadata_path != config.semantic_metadata_path:
            raise UniverseRegistryError("SemanticIndexHandle paths do not match manifest")
        if id(self.index) != self.index_object_id:
            raise UniverseRegistryError("SemanticIndexHandle index object was replaced")
        if _file_sha256(self.index_path) != self.artifact_index_sha256:
            raise UniverseRegistryError("Declared FAISS artifact changed after handle load")
        if _file_sha256(self.metadata_path) != self.artifact_metadata_sha256:
            raise UniverseRegistryError("Declared FAISS metadata changed after handle load")
        if self.loaded_index_snapshot != self.artifact_index_sha256:
            raise UniverseRegistryError("Loaded FAISS index does not match declared artifact")
        if self.loaded_metadata_snapshot != _metadata_file_snapshot(self.metadata_path):
            raise UniverseRegistryError("Loaded FAISS metadata does not match declared artifact")
        if _index_snapshot(self.index) != self.loaded_index_snapshot:
            raise UniverseRegistryError("FAISS index changed after handle load")
        if _metadata_snapshot(self.metadata) != self.loaded_metadata_snapshot:
            raise UniverseRegistryError("FAISS metadata changed after handle load")
        if getattr(self.index, "ntotal", len(self.metadata)) != len(self.metadata):
            raise UniverseRegistryError("FAISS index and metadata cardinality differ")
        _validate_metadata_sources(config, self.metadata)


class UniverseRegistry:
    """Read-only registry built directly from ``corpus/universes/*/manifest.json``."""

    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root.resolve()
        self._configs = self._load_configs()

    def _path(self, value: Any) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            return None
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise UniverseRegistryError(f"Manifest resource escapes project root: {value}") from exc
        return candidate

    def _load_configs(self) -> dict[str, UniverseConfig]:
        configs: dict[str, UniverseConfig] = {}
        for manifest_path in sorted((self.root / "corpus" / "universes").glob("*/manifest.json")):
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            universe_id = raw.get("universe_id")
            if not isinstance(universe_id, str) or not universe_id.strip() or universe_id in configs:
                raise UniverseRegistryError(f"Invalid or duplicate universe id in {manifest_path}")
            indexes = raw.get("indexes", {})
            text_index = indexes.get("text", {}) if isinstance(indexes, dict) else {}
            dictionary_index = indexes.get("dictionary", {}) if isinstance(indexes, dict) else {}
            collections = raw.get("collections", [])
            configs[universe_id] = UniverseConfig(
                universe_id=universe_id,
                display_name=str(raw.get("display_name", universe_id)),
                status=str(raw.get("status", "unknown")),
                manifest_path=manifest_path.resolve(),
                source_files=tuple(str(value) for value in raw.get("source_files", []) if isinstance(value, str)),
                collection_paths=tuple(
                    str(value.get("source_path"))
                    for value in collections
                    if isinstance(value, dict) and isinstance(value.get("source_path"), str)
                ),
                collection_canon_status=tuple(
                    (str(value.get("source_path")), value.get("canon_status"))
                    for value in collections
                    if isinstance(value, dict) and isinstance(value.get("source_path"), str)
                ),
                text_chunks_path=self._path(text_index.get("chunks_path")),
                semantic_index_path=self._path(text_index.get("index_path")),
                semantic_metadata_path=self._path(text_index.get("metadata_path")),
                dictionary_path=self._path(dictionary_index.get("path")),
                knowledge_graph_path=self._path((raw.get("knowledge_graph") or {}).get("path")),
            )
        return configs

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._configs))

    def list(self) -> tuple[UniverseConfig, ...]:
        return tuple(self._configs[key] for key in self.ids())

    def get(self, universe_id: str | None) -> UniverseConfig | None:
        if not isinstance(universe_id, str) or not universe_id.strip():
            return None
        return self._configs.get(universe_id.strip())

    def require(self, universe_id: str) -> UniverseConfig:
        config = self.get(universe_id)
        if config is None:
            raise UniverseRegistryError(f"Unknown universe: {universe_id}")
        return config


TERRAN_KEYWORDS = frozenset(
    {
        "star trek", "terran empire", "mirror universe", "mirror spock", "spock", "kirk",
        "terok nor", "cardassian", "klingon", "agony booth", "iss enterprise", "intendant",
    }
)
TOLKIEN_KEYWORDS = frozenset({"tolkien", "quenya", "sindarin", "galadriel", "middle-earth", "beleriand", "elda"})


@lru_cache(maxsize=1)
def get_universe_registry() -> UniverseRegistry:
    return UniverseRegistry()


def _candidate_universes(query: str) -> set[str]:
    lowered = query.lower()
    candidates: set[str] = set()
    if any(token in lowered for token in TERRAN_KEYWORDS):
        candidates.add("terran_empire")
    if any(token in lowered for token in TOLKIEN_KEYWORDS):
        candidates.add("tolkien")
    return candidates


def resolve_universe(
    selection: str | None,
    *,
    query: str | None = None,
    registry: UniverseRegistry | None = None,
) -> UniverseResolution:
    """Resolve an explicit selection or an unambiguous Auto candidate."""
    registry = registry or get_universe_registry()
    selected = selection.strip() if isinstance(selection, str) else ""
    if not selected:
        return UniverseResolution(UNIVERSE_REQUIRED, error="An explicit universe selection is required")
    if selected.lower() == "auto":
        candidates = _candidate_universes(query or "")
        if len(candidates) != 1:
            return UniverseResolution(SELECTION_REQUIRED, error="Auto detection is ambiguous; select a universe")
        selected = candidates.pop()
    aliases = {"Tolkien / Elfique": "tolkien", "Tolkien / Elvish": "tolkien", "Empire Terran": "terran_empire"}
    selected = aliases.get(selected, selected)
    if registry.get(selected) is None:
        return UniverseResolution(UNIVERSE_UNKNOWN, error=f"Unknown universe: {selected}")
    return UniverseResolution("SUCCESS", universe_id=selected)


def load_semantic_handle(universe_id: str, *, registry: UniverseRegistry | None = None) -> SemanticIndexHandle:
    """Load the manifested FAISS pair and bind it to immutable snapshots."""
    registry = registry or get_universe_registry()
    config = registry.require(universe_id)
    if not config.semantic_index_path or not config.semantic_metadata_path:
        raise UniverseRegistryError(f"Semantic index is not declared for universe: {universe_id}")
    if not config.semantic_index_path.exists() or not config.semantic_metadata_path.exists():
        raise UniverseRegistryError(f"Semantic index artifacts are missing for universe: {universe_id}")
    from src.retrieval import load_faiss

    index, metadata = load_faiss(str(config.semantic_index_path), str(config.semantic_metadata_path))
    handle = SemanticIndexHandle(
        universe_id=universe_id,
        index_path=config.semantic_index_path,
        metadata_path=config.semantic_metadata_path,
        index=index,
        metadata=metadata,
        artifact_index_sha256=_file_sha256(config.semantic_index_path),
        artifact_metadata_sha256=_file_sha256(config.semantic_metadata_path),
        loaded_index_snapshot=_index_snapshot(index),
        loaded_metadata_snapshot=_metadata_snapshot(metadata),
        index_object_id=id(index),
    )
    handle.validate(config)
    return handle


def _canonical_source(source: str, root: Path) -> str:
    candidate = Path(source)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _validate_metadata_sources(config: UniverseConfig, metadata: list[dict[str, Any]]) -> None:
    for item in metadata:
        source = item.get("source") or item.get("source_path")
        if not isinstance(source, str) or not source:
            raise UniverseRegistryError("Semantic metadata entry has no source")
        validate_source_path(config, source)


def validate_source_path(config: UniverseConfig, source: str) -> str:
    """Return a canonical declared source path or reject cross-universe data."""
    root = config.manifest_path.parents[3]
    canonical = _canonical_source(source, root)
    allowed_files = {_canonical_source(path, root) for path in config.source_files}
    allowed_dirs = tuple(_canonical_source(path, root).rstrip("/") + "/" for path in config.collection_paths)
    if canonical not in allowed_files and not canonical.startswith(allowed_dirs):
        raise UniverseRegistryError(f"Source is not declared by {config.universe_id}: {canonical}")
    return canonical
