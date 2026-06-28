# Knowledge Graph

Status: Step 9 hardening document.

The project already has runtime Knowledge Graphs. Step 9 is therefore not about
creating the KG from zero. It is about making the existing KG inspectable,
source-aware, and testable.

## Runtime Databases

| Universe | Runtime DB | Entities | Relations | Canon rules |
|---|---|---:|---:|---:|
| Tolkien / Elvish | `vector_db/knowledge_graph.sqlite` | 126 | 131 | 12 |
| Terran Empire | `vector_db/terran_empire/knowledge_graph.sqlite` | 42 | 33 | 12 |

## Current Schema

Both databases use three core tables.

`entities`:

- `id`
- `name`
- `aliases`
- `entity_type`
- `description`
- `period`
- `source_file`

`relations`:

- `id`
- `entity1_id`
- `relation_type`
- `entity2_id`
- `confidence`
- `note`
- `source_file`

`canon_facts`:

- `id`
- `description`
- `violation_pattern`
- `severity`
- `source_file`

## Provenance Status

Current provenance is structured but not equally granular everywhere.

- Entities have `source_file`.
- Relations have `source_file`.
- Canon facts have `source_file`.
- Period-like data is standardized as `period`.

For Tolkien, some graph records still point to the manual seed script rather
than a precise text excerpt. For Terran, entities and relations generally point
to source lore files, while canon rules point to the build script until rule
source spans are curated.

## Export

Reviewable exports are generated with:

```bash
.venv/bin/python scripts/export_kg.py
```

Outputs:

- `kg/tolkien/export.json`
- `kg/terran_empire/export.json`

The export includes:

- normalized entities;
- normalized relations with endpoint source files;
- canon rules;
- counts;
- explicit provenance limitations.

## Validation Behavior

KG validation is deterministic.

It currently checks:

- entity mentions and aliases;
- role assertions such as ruler/creator claims;
- regex-backed HARD/SOFT canon facts;
- source evidence through retrieval tools.

It does not yet check:

- full timeline consistency;
- all relation contradictions;
- precise relation source spans;
- precise canon-fact source spans;
- multi-hop contradictions.

## Next Hardening

1. Add precise source spans to relations and canon facts.
2. Add JSON import for reviewable graph diffs.
3. Add more contradiction tests for relation logic and false positives.
