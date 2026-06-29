# Security Policy

Status: pre-release policy.

## Secrets

Do not commit:

- `.env`;
- API keys;
- provider tokens;
- private corpus files;
- credentials;
- local database dumps containing private data.

Use `.env.example` for variable names only.

## Reporting

This project is not in public release yet.

For now, security issues should be handled privately by the maintainer before
open-source publication.

## Current Guardrails

- `.env` is gitignored.
- `scripts/open_source_audit.py` checks tracked files for obvious secret
  patterns.
- MCP tools are read-only or validation-only.
- Generated memory requires validation before reuse.

## Before Public Release

- Choose a license.
- Review tracked corpus and index licensing.
- Add public contact/security reporting instructions.
- Run `python scripts/open_source_audit.py --strict`.
