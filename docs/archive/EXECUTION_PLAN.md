# RAG Elven — Execution Plan

**Version:** 1.0  
**Date:** 2026-05-26  
**Timeline:** 2 weeks (10 working days)  
**Scope:** MVP (Quenya dictionary search + Streamlit UI + Groq integration)  
**Status:** ARCHIVED — historical execution plan

> Maintenance note, 2026-06-25:
> This plan is no longer an active task tracker. Several tasks reference old
> module names or commands (`src/data_loader.py`, `src/dictionary_parser.py`,
> `main.py`, `metadata.pickle`) that are not the current implementation path.
> Keep this file as context for the first MVP only.

---

## Milestone 1: MVP (Weeks 1–2) — CURRENT

### Phase 1: Data Preparation (Days 1–2)

#### TASK-001: Source Quenya Dictionary PDFs
**Status:** ✅ DONE (existing)  
**Owner:** —  
**Acceptance Criteria:**
- [ ] 1+ authoritative Quenya dictionary PDF acquired (Parma Eldalamberon, etc.)
- [ ] PDF stored in `data/` directory
- [ ] File size <50MB
- [ ] Test: `python src/data_loader.py` extracts ≥100 entries

**Effort:** 1h  
**Notes:** Using existing corpus from project setup

---

#### TASK-002: Parse Dictionary into SQLite
**Status:** ⏳ IN_PROGRESS  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `src/dictionary_parser.py` written and tested
- [ ] Extracts word, definition, part-of-speech, examples from PDF
- [ ] SQLite database created with schema (entries table)
- [ ] Test: `python main.py --build-db` populates 2000+ entries
- [ ] Verify: `sqlite3 data/quenya.db "SELECT COUNT(*) FROM entries;"` → ≥2000

**Effort:** 3–4h  
**Dependencies:** TASK-001  
**Subtasks:**
- [ ] Implement PDF text extraction (PyPDF)
- [ ] Parse entries into DictEntry objects
- [ ] Create SQLite schema
- [ ] Bulk insert entries
- [ ] Log: "Inserted 2145 entries into data/quenya.db"

---

### Phase 2: Vector Search Pipeline (Days 3–5)

#### TASK-003: Build Embeddings Module
**Status:** ⏳ IN_PROGRESS  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `src/embeddings.py` loads sentence-transformers model
- [ ] `embed_query()` returns 384-dim numpy array
- [ ] `embed_documents()` batch-embeds chunks
- [ ] Test: embedding generation <500ms per query
- [ ] Cache works (@st.cache_resource)

**Effort:** 2h  
**Dependencies:** —  
**Subtasks:**
- [ ] Load all-MiniLM-L6-v2 model
- [ ] Write embed_query() + embed_documents()
- [ ] Add Streamlit caching decorator
- [ ] Test latency (benchmark.py)

---

#### TASK-004: Build Text Splitter
**Status:** ⏳ IN_PROGRESS  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `src/text_splitter.py` chunks documents with overlap
- [ ] Chunk size: 500 chars, overlap: 50 chars
- [ ] Test: `python main.py --build-chunks` generates 4000–5000 chunks
- [ ] Metadata preserved (source filename, page)

**Effort:** 1.5h  
**Dependencies:** TASK-002  
**Subtasks:**
- [ ] Implement RecursiveCharacterTextSplitter
- [ ] Configure chunk_size=500, overlap=50
- [ ] Test chunk generation
- [ ] Log: "Generated 4523 chunks from 2 documents"

---

#### TASK-005: Build FAISS Index
**Status:** ⏳ IN_PROGRESS  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `src/retrieval.py` builds and saves FAISS index
- [ ] Index pickled to `vector_db/faiss.index`
- [ ] Metadata pickled to `vector_db/metadata.pickle`
- [ ] Test: `load_faiss()` <5 seconds (with caching)
- [ ] Test: `search(query_vector, k=5)` <500ms latency

**Effort:** 2h  
**Dependencies:** TASK-003, TASK-004  
**Subtasks:**
- [ ] Embed all chunks using sentence-transformers
- [ ] Create IndexFlatL2
- [ ] Pickle index + metadata
- [ ] Test retrieval accuracy (top-5 contains correct answers)
- [ ] Benchmark: `python -m cProfile main.py --benchmark`

---

#### TASK-006: Query Rewriting
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `src/query_rewriter.py` optimizes user queries
- [ ] Rules: remove punctuation, expand abbreviations, capitalize Quenya words
- [ ] Test: "what's mellon" → "What does mellon mean in Quenya?"
- [ ] Improves retrieval by 5%+ (measure on test set)

**Effort:** 1h  
**Dependencies:** —  
**Subtasks:**
- [ ] Write rewrite_query() function
- [ ] Add punctuation removal
- [ ] Add abbreviation expansion (Q. → Quenya)
- [ ] Test on 10 sample queries

---

### Phase 3: LLM Integration (Days 6–8)

#### TASK-007: Groq API Integration
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `src/llm.py` calls Groq API
- [ ] Model: llama-3.1-8b-instant
- [ ] Environment variable: GROQ_API_KEY in .env
- [ ] Test: Single query <2 seconds (including retrieval)
- [ ] Error handling: Timeout (10s), invalid key, rate limit

**Effort:** 1.5h  
**Dependencies:** —  
**Subtasks:**
- [ ] Install groq SDK (`pip install groq`)
- [ ] Implement answer() function
- [ ] Load GROQ_API_KEY from .env
- [ ] Add prompt template (system + context + query)
- [ ] Test with 5 sample queries

---

#### TASK-008: Prompt Engineering
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] Prompt template written and tested
- [ ] Template: system message + context + user query
- [ ] Example responses reviewed for accuracy
- [ ] Answers cite sources (e.g., "Source: Quenya Dictionary, p. 42")
- [ ] Test: LLM does NOT hallucinate (90%+ accuracy on test set)

**Effort:** 2h  
**Dependencies:** TASK-007  
**Subtasks:**
- [ ] Draft prompt template in `src/llm.py`
- [ ] Test with 20 sample queries
- [ ] Measure accuracy (manual review)
- [ ] Refine template to minimize hallucinations
- [ ] Add citation requirement to system message

---

#### TASK-009: Response Formatting
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `src/llm.py` formats final response
- [ ] Response includes: answer + sources + latency
- [ ] Sources are accurate (match FAISS retrieval)
- [ ] Test: Response is readable and professional

**Effort:** 1h  
**Dependencies:** TASK-007  
**Subtasks:**
- [ ] Write format_response() function
- [ ] Include latency measurement
- [ ] Extract sources from retrieved chunks
- [ ] Test formatting on 5 responses

---

### Phase 4: Streamlit UI & Integration (Days 9–10)

#### TASK-010: Streamlit App
**Status:** ✅ DONE (existing)  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `app.py` is functional and deployed locally
- [ ] UI includes: text input, submit button, response display
- [ ] Dark theme with purple accents (elfic ambiance)
- [ ] Caching works (@st.cache_resource for models)
- [ ] Test: Full query flow <2 seconds

**Effort:** Already complete  
**Dependencies:** TASK-001 through TASK-009  

---

#### TASK-011: End-to-End Testing
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] Run 20 sample queries through full pipeline
- [ ] Measure latency for each (target: <2s)
- [ ] Manual accuracy review (target: 90%+)
- [ ] No crashes or exceptions
- [ ] Log results in `log_RAGElven.md`

**Effort:** 2h  
**Dependencies:** TASK-010  
**Subtasks:**
- [ ] Create test query set (20 diverse queries)
- [ ] Run each through app, record latency + answer
- [ ] Rate each answer (correct/incorrect/partial)
- [ ] Document results in markdown table
- [ ] File: `log_RAGElven.md` (append test results)

---

#### TASK-012: Documentation & Handoff
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] README.md updated with setup + usage instructions
- [ ] TECHNICAL_SPEC.md is accurate and complete
- [ ] EXECUTION_PLAN.md marks all MVP tasks done
- [ ] User can run `streamlit run app.py` without errors
- [ ] .env template created (.env.example)

**Effort:** 1.5h  
**Dependencies:** All tasks  
**Subtasks:**
- [ ] Write comprehensive README
- [ ] Add setup instructions (venv, pip install, .env)
- [ ] Add usage examples (screenshot or GIF)
- [ ] Create .env.example with placeholders
- [ ] Review all docs for clarity

---

## Milestone 2: Quality & Performance (Post-MVP, 2–3 weeks)

### TASK-101: Unit Tests
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] `tests/` directory created
- [ ] Unit tests for each module (embeddings, retrieval, llm, etc.)
- [ ] Coverage: ≥80% of codebase
- [ ] All tests pass: `pytest tests/`

**Effort:** 3–4h  
**Dependencies:** MVP complete  
**Subtasks:**
- [ ] Write test_embeddings.py
- [ ] Write test_retrieval.py
- [ ] Write test_llm.py
- [ ] Write test_database.py

---

### TASK-102: Integration Tests
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] End-to-end pipeline tests
- [ ] Test: query → retrieve → LLM → response
- [ ] All tests pass: `pytest tests/integration/`

**Effort:** 2h  
**Dependencies:** MVP complete  

---

### TASK-103: Performance Benchmarking
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] Benchmark script measures latency at each stage
- [ ] Results logged: `benchmarks/results.md`
- [ ] Identify bottlenecks (embedding? retrieval? LLM?)
- [ ] Optimize top-3 bottlenecks

**Effort:** 2h  
**Dependencies:** MVP complete  

---

### TASK-104: Reranking (Optional, if time)
**Status:** 🔴 PENDING  
**Owner:** —  
**Acceptance Criteria:**
- [ ] Cross-encoder model added (e.g., cross-encoder/mmarco-miniLMv2-L12-H384-v1)
- [ ] Rerank top-5 FAISS results
- [ ] Improves accuracy by ≥5%
- [ ] Latency <2s maintained

**Effort:** 2–3h  
**Dependencies:** MVP complete  

---

## Milestone 3: Advanced Features (M3, 4+ weeks)

### TASK-201: Sindarin Support
**Status:** 🔴 PENDING (OUT OF SCOPE FOR MVP)  
**Acceptance Criteria:**
- [ ] 1500+ Sindarin dictionary entries ingested
- [ ] Separate FAISS index (sindarin.index)
- [ ] UI allows language selection dropdown

---

### TASK-202: Grammar Explanations
**Status:** 🔴 PENDING (OUT OF SCOPE FOR MVP)  
**Acceptance Criteria:**
- [ ] Dedicated grammar rule corpus
- [ ] Grammar query detection (e.g., "How do I pluralize?")
- [ ] Separate retrieval pipeline for grammar

---

### TASK-203: Etymology & Cultural Context
**Status:** 🔴 PENDING (OUT OF SCOPE FOR MVP)  
**Acceptance Criteria:**
- [ ] Etymology field parsed and indexed
- [ ] LLM enriches answers with etymology + cultural notes

---

## Milestone 4: Deployment (M4, 5+ weeks)

### TASK-301: Docker Containerization
**Status:** 🔴 PENDING  
**Acceptance Criteria:**
- [ ] Dockerfile written
- [ ] Image builds successfully
- [ ] Container runs: `docker run rag_elven` → Streamlit UI

---

### TASK-302: Cloud Deployment
**Status:** 🔴 PENDING  
**Acceptance Criteria:**
- [ ] Deploy to Hugging Face Spaces (or Replit)
- [ ] Public URL accessible
- [ ] All features work remotely

---

## Timeline Overview

```
Week 1:
┌─────────────────────────────────────────────────────────┐
│ Day 1-2: Data Prep (TASK-001/002)                       │
│ Day 3-5: Vector Pipeline (TASK-003/004/005/006)         │
└─────────────────────────────────────────────────────────┘

Week 2:
┌─────────────────────────────────────────────────────────┐
│ Day 6-8: LLM Integration (TASK-007/008/009)             │
│ Day 9-10: UI & Testing (TASK-010/011/012)              │
└─────────────────────────────────────────────────────────┘

✅ MVP SHIPPED
```

---

## Definition of Done (MVP)

### Code
- ✅ All 12 tasks completed and tested
- ✅ No obvious bugs (ran manual tests, saw no crashes)
- ✅ Type hints present (src/ files have `def foo(...) -> Type:`)
- ✅ Code is readable (variable names clear, functions <30 lines)

### Documentation
- ✅ README.md with setup + usage
- ✅ PRODUCT_SPEC.md (defines what)
- ✅ TECHNICAL_SPEC.md (defines how)
- ✅ .env.example template
- ✅ Inline comments for complex logic

### Performance
- ✅ Query latency <2 seconds (measured with `time` command)
- ✅ Startup time <5 seconds
- ✅ Memory footprint <2GB

### Accuracy
- ✅ 90%+ correct answers on 20-query test set (manual review)
- ✅ No hallucinations (LLM cites sources)

### Usability
- ✅ Non-technical user can run `streamlit run app.py` without errors
- ✅ UI is intuitive (text input → button → response)
- ✅ Error messages are helpful (not cryptic)

### Version Control
- ✅ All code committed with clear commit messages
- ✅ No secrets in repo (.env is in .gitignore)
- ✅ README.md references PRODUCT_SPEC.md and TECHNICAL_SPEC.md

---

## Success Metrics

By end of Week 2, this project succeeds if:

| Metric | Target | Pass? |
|--------|--------|-------|
| **Accuracy** | 90%+ on test set | TBD |
| **Latency** | <2s per query | TBD |
| **Uptime** | 0 crashes in 20 queries | TBD |
| **Coverage** | 2000+ entries searchable | TBD |
| **Usability** | 3 testers can use UI without help | TBD |
| **Code Quality** | No linting errors (future) | N/A (MVP) |

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| **Groq API downtime** | Low | Have fallback prompt; document offline limitations |
| **Poor retrieval accuracy** | Medium | Add query rewriting; benchmark early (Day 3) |
| **Embedding model too slow** | Low | Tested all-MiniLM-L6-v2; 6x faster than all-mpnet |
| **Hallucination by LLM** | Medium | Prompt engineering (TASK-008); measure accuracy early |
| **Chunking loses context** | Low | Overlap=50; test on edge cases (rare words) |

---

## Next Steps (Day 1)

1. **Confirm MVP scope:** Is 1-2 weeks realistic? Does Quenya-only satisfy the goal?
2. **Acquire dictionary:** Confirm PDF source (Parma Eldalamberon? Other?)
3. **Start TASK-001:** Load PDF into `data/`, log entries extracted
4. **Daily standup:** Review progress on TASK-001/002/003 by end of Day 2

---

## Post-MVP Backlog

- [ ] Add pytest + 20 unit tests (TASK-101)
- [ ] Benchmark latency + identify bottlenecks (TASK-103)
- [ ] Add confidence scoring + citation validation
- [ ] Reranking with cross-encoder (TASK-104)
- [ ] Sindarin support (TASK-201)
- [ ] Grammar explanations (TASK-202)
- [ ] Logging/analytics (TASK-303)
- [ ] Docker deployment (TASK-301)

---
