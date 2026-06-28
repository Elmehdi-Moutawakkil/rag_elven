# Knowledge Graphs

Per-universe Knowledge Graph exports live here.

The current runtime still uses:

- `vector_db/knowledge_graph.sqlite`
- `vector_db/terran_empire/knowledge_graph.sqlite`

Generate reviewable exports with:

```bash
.venv/bin/python scripts/export_kg.py
```

See `docs/KNOWLEDGE_GRAPH.md` for schema and provenance notes.
