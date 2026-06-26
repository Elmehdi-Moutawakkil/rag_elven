# Indexes

Future retrieval indexes will live here.

The current runtime still uses `vector_db/`. New code should migrate gradually
through universe manifests before moving live paths.

Current text retrieval outputs:

- `indexes/<universe_id>/text/chunks.jsonl`: chunks derived from normalized
  `storage/processed/<universe_id>/documents.jsonl` records.
- `indexes/<universe_id>/text/manifest.json`: deterministic build summary used
  by sanity checks and reviews.
