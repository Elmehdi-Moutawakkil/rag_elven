# Tolkien / Elvish Corpus Summary

Status: legacy runtime corpus.

This corpus keeps the existing Tolkien/Elvish runtime sources while the project
migrates toward manifest-backed universes.

## Runtime Sources

- Quenya course PDF: `data/quenya_course/Quenya-Elvish-Language-Course-Tolkien.pdf`
- Dictionary SQLite: `vector_db/dictionary.sqlite`
- Legacy FAISS index: `vector_db/faiss.index`
- Legacy KG: `vector_db/knowledge_graph.sqlite`

## Migrated Review-Needed Lore Notes

- `corpus/universes/tolkien/canon/first_age_wars.txt`
- `corpus/universes/tolkien/canon/languages_overview.txt`
- `corpus/universes/tolkien/canon/maiar_sauron.txt`
- `corpus/universes/tolkien/canon/valar_morgoth.txt`

These notes are preserved but should not be treated as active indexed evidence
until a Tolkien ingestion rebuild explicitly includes them.
