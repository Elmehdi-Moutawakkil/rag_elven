# Corpus

Canonical, versioned universe corpora live here.

This folder is the Git-facing source layer. It should contain human-readable
manifests, summaries, canon notes, source pointers, and validated memory links.

The current runtime still reads from `data/` and `vector_db/`. During migration,
corpus manifests reference those existing paths instead of moving files at once.
