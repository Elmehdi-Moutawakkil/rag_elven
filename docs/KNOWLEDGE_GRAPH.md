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
- `age` or `era`
- `source_file`

`relations`:

- `id`
- `entity1_id`
- `relation_type`
- `entity2_id`
- `confidence`
- `note`

`canon_facts`:

- `id`
- `description`
- `violation_pattern`
- `severity`

## Provenance Status

Current provenance is useful but incomplete.

- Entities have `source_file`.
- Relations have endpoint entities and `note`, but no dedicated source field.
- Canon facts have descriptions and regex rules, but no dedicated source field.
- Tolkien stores period-like data as `age`.
- Terran stores period-like data as `era`.

The export normalizes `age` and `era` to `period`, but the source databases are
not yet schema-identical.

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
- relation source spans;
- canon-fact source spans;
- multi-hop contradictions.

## Next Hardening

1. Add `source_file` or `source_id` to relations.
2. Add `source_file` or `source_id` to canon facts.
3. Standardize `age` and `era` into one `period` field.
4. Add JSON import/export for reviewable graph diffs.
5. Add more contradiction tests for relation logic and false positives.
