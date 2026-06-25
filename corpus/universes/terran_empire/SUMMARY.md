# Terran Empire Summary

Pilot universe for the target corpus architecture.

This universe covers the Star Trek Mirror Universe Terran Empire and related
Klingon-Cardassian Alliance material. The current corpus is intentionally small
and useful as a stress test for retrieval, generation, and Knowledge Graph
validation under sparse lore conditions.

Current source folders:

- `data/universes/terran_empire/lore/`

Current runtime artifacts:

- `vector_db/terran_empire/faiss.index`
- `vector_db/terran_empire/metadata.json`
- `vector_db/terran_empire/knowledge_graph.sqlite`

Migration status:

- The current app still uses `data/` and `vector_db/` directly.
- This summary and manifest define the future corpus contract without moving
  runtime files yet.
