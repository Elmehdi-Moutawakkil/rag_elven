# Validated Memory

Validated AI outputs live here as controlled generated-memory records.

Generated content is never canon by default. It becomes reusable only when it
has:

- at least one source citation;
- no KG hard contradiction;
- explicit transition to `validated`;
- event history showing who reviewed or changed it.

## Runtime Format

Current store:

- `memory/<universe_id>/memory.jsonl`

Each item records:

- `memory_id`
- `status`
- `content`
- `summary`
- `sources`
- `kg_validation`
- `version`
- `content_hash`
- `validated_at`
- `reviewer`
- `events`

## Status Flow

Allowed status transitions:

- `draft -> pending`
- `draft -> rejected`
- `pending -> validated`
- `pending -> rejected`
- `pending -> draft`
- `validated -> superseded`
- `validated -> rejected`
- `rejected -> draft`

Only `validated` items with sources and no KG hard contradiction are reusable.

## Editing And Rollback

Editing a memory item resets it to `draft`.

Rollback restores the latest pre-edit snapshot as a new draft version. This
keeps the history append-only instead of erasing mistakes.
