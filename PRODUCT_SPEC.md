# RAG Elven — Product Specification

**Version:** 1.0  
**Date:** 2026-05-26  
**Status:** ACTIVE  
**Audience:** Fans/Researchers learning Elvish; NLP/RAG researchers  

---

## 1. Vision & Problem Statement

### Elevator Pitch
Create a **working proof-of-concept** that demonstrates Retrieval-Augmented Generation can help people learn a constructed language (Quenya, Sindish Elvish) by enabling natural conversation with authoritative sources.

### The Problem
- Learning Tolkien's Quenya is hard: sources are scattered, grammar is complex, no single QA tool exists
- RAG is powerful for knowledge domains, but mostly demonstrated on standard English corpus
- **Hypothesis:** RAG + specialized LLM can bridge the gap between scattered Elvish resources and learner needs

### What This Project Proves
✅ **RAG works for niche/constructed languages**  
✅ **You can build this in 2 weeks** (MVP scope)  
✅ **Real users will find it useful** (fans, researchers, language students)

---

## 2. Target Users (Personas)

### Persona 1: Tolkien Fan / Enthusiast
- **Who:** Fans of LOTR/Silmarillion wanting to learn "real" Quenya
- **Pain:** Scattered resources (books, wikis, essays); can't easily ask "what does X mean?"
- **Need:** Quick, reliable answers from authoritative sources
- **Success:** "I can ask 'how do I say hello?' and get a real answer"

### Persona 2: Academic / Linguist Student
- **Who:** Students studying constructed languages or applied linguistics
- **Pain:** Need to cite sources, understand grammar patterns, compare with other languages
- **Need:** Explainable answers with links back to dictionaries/grammar
- **Success:** "I can learn Quenya grammar + etymology in a structured way"

### Persona 3: NLP/RAG Researcher
- **Who:** Developers/researchers exploring RAG + embeddings
- **Pain:** Most examples use boring domains (Wikipedia, customer support)
- **Need:** A cool, real-world niche example to learn from
- **Success:** "This is a working RAG system; I can fork it and experiment"

---

## 3. Core Features (MVP Scope)

### Feature 1: Dictionary Search ⭐ (MUST HAVE)
**User Story:** As a learner, I want to ask "what does X mean in Quenya?" and get definitions instantly.

**Implementation:**
- User types question in Streamlit interface
- System retrieves matching Quenya words + definitions
- LLM enriches answer with context + examples
- **Success Criteria:**
  - Answers appear in < 2 seconds
  - Definitions match dictionary 90%+ accuracy
  - User sees source (which dictionary entry matched)

**Example:**
```
User: "What does 'mellon' mean in Quenya?"
System: "mellon = friend (noun)
         Source: Quenya Dictionary v1.2
         Example: 'Mellon nîn' = my friend"
```

### Feature 2: Grammar Explanations ✨ (NICE TO HAVE)
**User Story:** As a learner, I want to understand *why* a word is used a certain way.

**Implementation:**
- User asks about grammar (e.g., "how do I pluralize a Quenya noun?")
- System retrieves grammar rules + examples
- LLM explains with comparative examples
- **Success Criteria:**
  - Answers reference grammar sources
  - Examples from LOTR or Tolkien texts when possible

**Example:**
```
User: "How do I pluralize Quenya nouns?"
System: "Quenya plurals typically add -in or -r
         Example: elen (star) → eleni (stars)
         Exception: Some nouns use -e (plural marker)"
```

### Feature 3: Source Attribution 📚 (MVP)
**User Story:** As a researcher, I want to know *which* source the answer came from.

**Implementation:**
- Every answer shows which dictionary/grammar was retrieved
- User can click to see full source entry
- Builds trust in accuracy
- **Success Criteria:**
  - Every answer cites at least one source
  - Sources are accurate (match FAISS retrieval)

---

## 4. Out of Scope (v2 or Later)

❌ Sindarin support (v1.1 or M2)  
❌ Multi-turn conversation (v2)  
❌ Voice input/output (v2)  
❌ User accounts/progress tracking (v2)  
❌ Community contributions (v3)  
❌ Mobile app (v3)  

---

## 5. Success Criteria

### What Makes This MVP a Success?

| Criterion | Target | Metric |
|-----------|--------|--------|
| **Accuracy** | 90%+ correct answers | Manual test: 100 Q&A pairs |
| **Speed** | <2s per query | Measure latency; log slow queries |
| **Coverage** | 2000+ Quenya words | Query SQLite count |
| **Usability** | "Non-tech person can use it" | Have 3 people try; collect feedback |
| **Robustness** | <1 error per 100 queries | 1-week production monitoring |
| **Code Quality** | Tests pass, no obvious bugs | CI/CD: tests + linting green |

---

## 6. Technical Constraints

### Must Have
- ✅ Local, no external API dependencies (except Groq for LLM)
- ✅ Works offline after initial model download
- ✅ Fast (<2s query time)
- ✅ Runs on commodity hardware (MacBook, 8GB RAM)

### Nice to Have
- ⭐ Docker-friendly for deployment
- ⭐ Analytics/logging for improvement
- ⭐ Graceful error handling

### Technical Debt (Acceptable for MVP)
- 🤷 No sophisticated error recovery (fail loudly, fix manually)
- 🤷 Minimal logging (good enough to debug)
- 🤷 Single-user only (no concurrency needed)

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Poor retrieval quality** | Medium | High | Add reranking in M2 (cross-encoder) |
| **Groq API downtime** | Low | High | Add fallback to local LLM (Ollama) in M2 |
| **Corpus is too small** | Low | Medium | Add Sindarin + supplementary texts in M2 |
| **LLM hallucinates** | Medium | Medium | Add confidence scoring + citation validation |

---

## 8. MVP Definition

**What ships in Week 1-2:**
- ✅ Quenya dictionary searchable
- ✅ Streamlit UI working
- ✅ Groq integration complete
- ✅ <2s response time
- ✅ Source attribution
- ✅ README + setup docs

**What does NOT ship in v1:**
- ❌ Sindarin
- ❌ Reranking
- ❌ Logging/analytics
- ❌ Tests (added in M2)
- ❌ Deployment (added in M3)

---

## 9. Why This Matters (The Why)

This project demonstrates:
1. **RAG is powerful for niche domains** (not just generic Wikipedia QA)
2. **You can build production-quality ML tools fast** (2 weeks MVP)
3. **Real people care about this** (Tolkien enthusiasts + researchers)
4. **RAG can be creative** (generating natural language in Quenya is cool!)

It's a **proof-of-concept** that lands in people's hands and says: *"RAG isn't just hype—it solves real problems."*

---

## Next Steps

→ Move to TECHNICAL_SPEC.md  
→ Move to EXECUTION_PLAN.md  
→ Start building!
