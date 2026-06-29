# Open Source Readiness

Status: Step 18 foundation. Not ready for public release yet.

## Historian Note

Step 18 is intentionally deferred as a release milestone.

Future agents should treat this document as the handoff point for open-source
publication. The current work prepares governance and audit checks only. It
does not mean the project is ready to publish.

## Current State

Already present:

- README;
- `.env.example`;
- technical architecture doc;
- pipeline status doc;
- tests;
- sanity check;
- governance policies;
- MCP/read-only boundary docs;
- fine-tuning deferral strategy.

Added for Step 18:

- contribution guide;
- security policy;
- open-source audit script;
- this release checklist.

## Release Blockers

- License not chosen.
- Tracked PDFs and corpus/index assets need redistribution review.
- GitHub Actions CI should be added with a token that has `workflow` scope,
  then tested on GitHub.
- Public security contact/process not finalized.
- Private/public corpus split must be explicit.

## Publication Checklist

- [ ] Choose and add a `LICENSE`.
- [ ] Run `python scripts/open_source_audit.py --strict`.
- [ ] Review all tracked files under `data/`.
- [ ] Review all tracked files under `vector_db/`.
- [ ] Replace unclear-license data with minimal example corpus if needed.
- [ ] Confirm `.env` is not tracked.
- [ ] Confirm README setup works from a clean clone.
- [ ] Confirm CI passes on GitHub.
- [ ] Add public issue/PR policy.
- [ ] Add public security reporting contact.

## Architecture Note

The architecture does not need a major rewrite for open source.

The important boundary is packaging:

- app code stays public;
- private or unclear-license corpora stay out of public release;
- generated memory stays reviewed and versioned;
- model/provider keys stay local;
- MCP write tools stay disabled until auth and rollback exist.
