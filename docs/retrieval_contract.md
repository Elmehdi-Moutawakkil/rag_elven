# Retrieval contract v2

`src.universe_registry` is the single authority for universe resources. It
reads `corpus/universes/*/manifest.json`; callers must not substitute paths or
raw FAISS metadata.

## Universe resolution

- Omitted or blank selection: `UNIVERSE_REQUIRED`.
- Unknown IDs, including traversal-like IDs: `UNIVERSE_UNKNOWN`.
- `Auto` succeeds only when detection has one certain candidate. Generic and
  mixed-universe requests return `SELECTION_REQUIRED`.
- A UI or caller passes the resolved universe explicitly to retrieval.
- Translation is Tolkien-only. An explicit Terran translation returns
  `CAPABILITY_UNSUPPORTED`; it never switches universes.

## Retrieval result

`retrieve_evidence_result()` returns `RetrievalResult` schema version 2:

`status`, `universe_id`, `hits`, `engines`, `degraded`, `warnings`, and
`error`.

- `SUCCESS` always has one or more hits.
- `NO_RESULTS` means an engine ran but returned none.
- `INDEX_MISSING` means a required engine was unavailable.
- `ERROR` means an artifact, binding, provenance, or runtime failure.
- `lexical`, `semantic`, and `hybrid` require their named engines. `auto` can
  continue with one engine and marks the missing engine in `degraded` and
  `warnings`.

`retrieve_evidence()` remains a list wrapper only for compatibility: it
returns `[]` solely for `NO_RESULTS` and raises `RetrievalContractError` for
every other non-success status.

## Semantic resources

Use `load_semantic_handle(universe_id)`. A `SemanticIndexHandle` binds the
manifested FAISS index and metadata files to their hashes, serialized index
snapshot, loaded metadata snapshot, and index object identity. It detects
replaced files, a swapped index object, metadata mutation, and index mutation
before a search. Raw `model/index/metadata` triplets are rejected.

## Citations

Hits carry `citation_source_id`, `citation_version_id`, and
`citation_excerpt_id`, plus a `citation:v1:...` value. IDs use source identity,
full document hash where available, excerpt content, and span/page; they never
use rank or FAISS position. Existing JSONL chunks are normalized only in
memory. `resolve_citation_identity` and the read-only MCP `resolve_citation`
tool return the exact current excerpt, or `CITATION_UNAVAILABLE`. Legacy
`source#chunk` values are never aliased to changed text.

## Generation boundary

L02 stores the typed retrieval outcome. Any status other than `SUCCESS`,
including `NO_RESULTS`, terminates the pipeline before L08, L13, planner
generation, or a provider client. Dictionary-only Tolkien QA remains allowed
when L03 supplies evidence.
