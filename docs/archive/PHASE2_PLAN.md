# Phase 2 — Elven Sentence Translation: Planning Document

> Session date: 2026-05-30 (revised from 2026-05-29)
> Status: **ARCHIVED / partially implemented** — historical translation design.
> The Semantic IR, deterministic morphology, syntax, and optional LLM polish
> ideas are now implemented in `src/ir.py`, `src/morphology.py`,
> `src/syntax.py`, and `src/translator.py`. Keep this file as rationale, not
> as the active roadmap.

---

## Context: What Phase 1 Built

Phase 1 is a working RAG system for **Quenya language learning**. It answers questions — vocabulary lookups, grammar explanations, lore queries — using a hybrid retrieval pipeline:

- **SQLite** for exact vocabulary lookups (1,512+ dictionary entries, 4-pass parser for variants, sub-entries, and cross-references)
- **FAISS** for semantic search over grammar courses and lore texts (1,518 chunks)
- **Query Rewriter** (LLM agent) that normalizes the user's question into a keyword + intent before retrieval
- **Groq / LM Studio LLM** that synthesizes the retrieved context into a natural answer
- **Streamlit UI** with multilingual support (French + English)

Phase 1 proves the concept: RAG works for language Q&A. It does **not** attempt to construct sentences.

---

## The Problem Phase 2 Solves

Phase 1 answers "What does *mellon* mean?" It cannot answer "How do I say *The warrior walks through the forest* in Quenya?"

That gap is structural:

| Task | Phase 1 | Phase 2 |
|---|---|---|
| Word lookup | ✅ | ✅ |
| Grammar Q&A | ✅ | ✅ |
| English → Quenya sentence construction | ❌ | ✅ |
| Quenya → English sentence parsing | ❌ | ✅ |
| Authentic Elven register/style | ❌ | Partial (Phase 3 completes this) |

---

## Why RAG + LLM Alone Cannot Build Sentences

Two structural problems prevent a naive approach from working:

**Problem 1 — Morphological correctness**

Quenya words change form depending on grammatical role (subject, object, locative, etc.), number (singular/plural), tense, and agreement. An LLM that retrieves grammar rules and then applies them will eventually:
- apply incorrect suffixes,
- generate impossible forms,
- mismatch number agreement,
- invent morphology that does not exist.

Even state-of-the-art models do this. It is not fixable by better prompting — it is a structural property of probabilistic systems.

The key insight (confirmed by architectural review):

> **Rules need to be enforced, not just retrieved.**

Retrieval surfaces the rules. A deterministic engine applies them. These are two different jobs and they must be held by two different components.

**Problem 2 — Style and register**

Elves do not speak elevated English mapped to Quenya words. Their voice is poetic, indirect, metaphor-heavy, rhythmically specific, and nominally dense. RAG can retrieve facts about this style but cannot embody it. That requires a separate style layer built from curated examples — not grammar rules.

---

## Phase 2 Architecture: 4 Layers

> Revised from the initial 3-layer design based on architectural review.
> The critical addition is **Layer 2.5: Deterministic Morphological Engine**.

```
English sentence input
         │
         ▼
┌──────────────────────────────────────────────┐
│  Layer 1 — NLP Parsing                       │
│                                              │
│  Tool: spaCy (en_core_web_sm)                │
│  Output: Semantic Intermediate Representation│
│  (IR) — structured, language-agnostic JSON   │
└──────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Layer 2 — Grammar Rule Retrieval            │
│                                              │
│  Tool: FAISS / structured rule store         │
│  Input: IR features (tense, case, number...) │
│  Output: precise grammar rules + confidence  │
└──────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Layer 2.5 — Deterministic Morphology Engine │  ← THE CRITICAL ADDITION
│                                              │
│  Input: IR + retrieved rules                 │
│  Output: computed Quenya word forms          │
│  e.g. warrior→ohtar→ohtari (plural nom.)     │
│        city→osto→ostonna   (allative)        │
│        walk→vanta→vantar   (present pl.)     │
│                                              │
│  NO LLM INVOLVEMENT HERE.                   │
└──────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│  Layer 3 — LLM: Style & Arrangement Only     │
│                                              │
│  Input: pre-computed word forms (from 2.5)   │
│  Job: arrange into a sentence that sounds    │
│       like an Elf wrote it                   │
│  NOT: compute morphology (already done)      │
└──────────────────────────────────────────────┘
         │
         ▼
Quenya sentence output
(with grammatical explanation + source provenance)
```

The LLM is now a **stylistic arranger**, not a grammatical compiler.

---

## Layer 1 — NLP Parsing + Semantic IR

**Tool:** spaCy (`en_core_web_sm`)

### What spaCy extracts

| Feature | Example input | Extracted |
|---|---|---|
| Part of speech | "walks" | VERB |
| Grammatical role | "the warrior" | agent (nominative) |
| Tense | "walks" | present simple |
| Number | "warriors" | plural |
| Preposition + object | "into the city" | goal (allative) |
| Named entities | proper nouns | kept / transliterated |

### Semantic Intermediate Representation (IR)

Rather than passing loose parsed features through the pipeline, every layer shares a common **IR schema**. This is the backbone of the system.

```json
{
  "predicate": {
    "lemma": "walk",
    "tense": "present",
    "number": "plural",
    "mood": "declarative"
  },
  "arguments": [
    {
      "role": "agent",
      "lemma": "warrior",
      "number": "plural",
      "case": "nominative"
    },
    {
      "role": "goal",
      "lemma": "city",
      "case": "allative"
    }
  ]
}
```

**Why IR matters:**
- Shared contract between all layers — each layer reads and writes the same structure
- Makes each layer independently testable
- Enables reverse translation (Quenya → IR → English) with the same schema
- Compatible with future fine-tuning (IR pairs become training data)
- Eliminates ambiguity before retrieval: the RAG query is constructed from IR fields, not raw text

---

## Layer 2 — Grammar Rule Retrieval (Upgraded)

Phase 1 RAG is **text-driven**: user query → semantic search → top-k chunks of text.

Phase 2 RAG is **IR-driven**: IR features → targeted rule lookup → specific grammar rules with provenance.

### Evolution: from chunk retrieval to structured rules

Current (Phase 1):
```
retrieves text like: "locative endings are often -sse or -nna depending on..."
```

Phase 2 target:
```json
{
  "rule_type": "case_suffix",
  "case": "allative",
  "suffix": "-nna",
  "conditions": ["consonant-final stem", "singular"],
  "source": "Quenya Course Chapter 3",
  "confidence": 0.91,
  "status": "attested"
}
```

This is the beginning of a **linguistic knowledge graph** — where facts about grammar are stored as structured data, not prose.

### Grammar Confidence System

Quenya has a critical problem: **it is not fully standardized**. Sources contradict each other. Tolkien revised the grammar across decades. Much of what is used today is reconstructed neo-Quenya.

Without provenance tracking, the system produces "false certainty" — a Quenya sentence with no indication that one of its rules is disputed.

Every retrieved grammar rule carries:

```json
{
  "rule": "allative plural suffix",
  "suffix": "-nnar",
  "source": "Parma Eldalamberon XX",
  "confidence": 0.72,
  "status": "attested",
  "notes": "Plural allative is less well-attested than singular"
}
```

The final output shows the user the confidence level of the translation — not just the result.

---

## Layer 2.5 — Deterministic Morphological Engine (New)

This is the most important addition to the architecture.

### The problem it solves

```
Input: "The warriors walk into the city"

WITHOUT Layer 2.5:
  LLM must infer plurality, conjugate the verb,
  apply allative case, produce correct phonology.
  → Hallucination risk on every transformation.

WITH Layer 2.5:
  Morphology engine computes:
    warrior (plural nominative) → ohtar → ohtari
    city (allative)             → osto  → ostonna
    walk (present plural)       → vanta → vantar

  LLM receives: [ohtari] [vantar] [ostonna]
  LLM job: arrange these into Elven-style sentence.
```

### What the engine does

Given an IR argument + retrieved grammar rules, it deterministically applies:
- Noun declensions (nominative, accusative, dative, genitive, locative, allative, ablative, instrumental)
- Verb conjugations (tense, aspect, number, person)
- Plural forms
- Phonological adjustments (vowel harmony, consonant mutation at word boundaries)

### Implementation approach

For Phase 2, the morphology engine starts as a **rule-based Python module** — a set of functions that apply transformations given a lemma + grammatical features. It does not use ML.

Long-term, this could evolve into a proper **Finite State Transducer (FST)** using tools like HFST (Helsinki Finite-State Toolkit) — the standard approach in computational linguistics for morphological analysis.

### What the LLM receives (post-Layer 2.5)

```json
{
  "computed_forms": [
    {"original": "warrior", "quenya_lemma": "ohtar", "final_form": "ohtari", "rule": "plural nominative"},
    {"original": "walk",    "quenya_lemma": "vanta",  "final_form": "vantar", "rule": "present plural"},
    {"original": "city",    "quenya_lemma": "osto",   "final_form": "ostonna","rule": "allative"}
  ],
  "confidence_floor": 0.72
}
```

The LLM's only job now: arrange `ohtari vantar ostonna` into a sentence that sounds like Tolkien wrote it.

---

## Layer 3 — LLM: Style & Arrangement Only

**Input:** pre-computed word forms (from Layer 2.5), grammatical explanation, style corpus examples (Phase 3)

**Job:** produce a Quenya sentence with authentic register — word order, rhythm, preferred constructions.

**Not its job:** compute morphology, decide case endings, conjugate verbs. All of that arrives pre-computed.

### Phase 3 preview — Authentic Elven Style

The style layer is more complex than "make it poetic." Tolkienian Elven style includes:

| Dimension | Description |
|---|---|
| **Syntactic structure** | SOV-leaning word order, nominal density |
| **Register** | Elevated, unhurried — rarely imperative |
| **Emotional expression** | Indirect — emotions expressed through imagery |
| **Rhythm** | Specific prosodic patterns (Tolkien was a poet) |
| **Metaphor** | Nature-grounded, cosmic in scale |

The Phase 3 style corpus will need annotation for register, emotional tone, narrative context, and formality — not just vocabulary. Otherwise the output risks becoming "fantasy-flavored English in Quenya" rather than genuinely Tolkienian expression.

---

## The Long-Term Architecture (Linguistic Compiler)

The architecture increasingly resembles a **compiler** rather than a chatbot:

```
English AST  →  Semantic IR  →  Quenya AST  →  Surface Quenya sentence
```

Full ideal pipeline:

```
Input sentence
    ↓
Dependency parser (spaCy)         [Layer 1]
    ↓
Semantic IR
    ↓
Grammar rule resolver              [Layer 2]
    ↓
Deterministic morphology engine    [Layer 2.5]
    ↓
Surface realization engine
    ↓
LLM stylistic polishing            [Layer 3]
    ↓
Final Quenya sentence + provenance
```

---

## Phased Roadmap

| Phase | Goal | Key capability |
|---|---|---|
| **1** ✅ | RAG Q&A baseline | Vocabulary lookup, grammar Q&A, query rewriter agent |
| **2** 🚧 | Sentence translation | NLP parsing → IR → deterministic morphology → LLM arrangement |
| **3** 📋 | Style & register | Annotated style corpus, few-shot Elven register |
| **4** 📋 | Knowledge graph | Structured rule store replacing prose RAG chunks |
| **5** 📋 | Fine-tuning | Small seq2seq model on growing IR-paired corpus |

---

## Phase 2 Milestones

1. **IR schema** — Define and document the Semantic IR format (foundation for all layers)
2. **spaCy integration** — Parse any English sentence into an IR instance
3. **Morphology engine v1** — Deterministic Python module: lemma + features → Quenya form
4. **Grammar-targeted retrieval** — Rewrite RAG query construction to use IR fields
5. **Translation prompt** — LLM receives pre-computed forms, produces styled sentence
6. **Confidence display** — Show provenance and confidence score alongside output
7. **CLI interface** — `en→qu` and `qu→en` modes, one sentence at a time
8. **Validation** — Test 15–20 known English/Quenya sentence pairs from Tolkien's own translations

---

## Open Questions for Phase 2

- **Reverse direction (Quenya → English):** requires a Quenya morphological *analyzer* (not generator). May need a hand-crafted rule set or a Quenya FST. Likely Phase 2b.
- **Corpus gaps:** Grammar rules needed for the morphology engine may be absent from current data sources. Grammar coverage audit is a Day 1 task.
- **Source conflicts:** When two attested sources give different forms, the engine must pick one and flag it. Conflict resolution policy needed.
- **Phonological rules:** Some Quenya transformations happen at word boundaries (e.g., final consonant + initial vowel). These interact with morphology and may need a post-processing step.

---

## Architectural Sources

- Initial architecture: planning session 2026-05-29
- Architectural review: instructor feedback 2026-05-30 (`quenya_architecture_feedback.md`)

*The deterministic morphology engine (Layer 2.5), Semantic IR, and Grammar Confidence System were all recommended in the architectural review. These are not optional enhancements — they are load-bearing components that prevent fundamental failure modes.*
