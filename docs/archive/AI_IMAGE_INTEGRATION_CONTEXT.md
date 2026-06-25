# RAG Elfique — AI Image Integration Discussion

**Date**: 2026-06-04  
**Project**: RAG Elfique (English → Quenya translation + Q&A system)  
**Repo**: https://github.com/Elmehdi-Moutawakkil/rag_elven  
**Developer**: Elmehdi Moutawakkil (elmehdi@moutawakkil.com)

> Maintenance note, 2026-06-25:
> This is a historical discussion note. It treats image support as an add-on to
> the Tolkien app. The current strategy is broader: multimodal storage,
> ingestion, indexing, retrieval, validation, and generation should be designed
> as first-class layers in the next technical spec.

---

## 1. Current Project State

### Architecture: 4-Layer Translation Pipeline

```
English sentence
    ↓
Layer 1  — src/ir.py          : spaCy parsing → SemanticIR
    ↓
Layer 2  — src/morphology.py  : deterministic morphology (word forms)
    ↓
Layer 3  — src/syntax.py      : deterministic syntax (SOV word order, particles)
    ↓
Layer 4  — translator.py      : LLM stylistic polish (optional)
    ↓
Quenya sentence
```

### Key Design Principles

- **Morphology is deterministic**, not LLM-driven
- **High confidence in forms**: confidence levels (HIGH/MEDIUM/LOW) replace percentages
- **Full traceability**: every form has a rule_id (RULE_NOUN_A_NOM_SG, etc.)
- **LLM does NOT recompute grammar** — only adjusts register/style
- **Graceful degradation**: Q&A works without FAISS, translation works without LLM

### Data Resources

| Resource | Size | Format | Purpose |
|----------|------|--------|---------|
| FAISS index | 1490 chunks | binary | Semantic search for Q&A |
| SQLite DB | 8022 words | SQL | Vocabulary (Quenya + Sindarin) |
| Quenya course PDF | ~80 pages | PDF text | Training data for FAISS |
| Grammar rules | 80+ rules | Python dict | Declension/conjugation tables |

### Test Coverage

- **116 tests passing** (morphology, syntax, validation)
- **0 external dependencies** beyond standard ML stack (spaCy, FAISS, sentence-transformers)
- **Confidence system**: HIGH/MEDIUM/LOW per form

### Deployment

- **Streamlit Cloud** (active)
- **UI**: 2 tabs (Q&A + Translate)
- **Status**: Phase 1 & 2 fully operational

---

## 2. Possible AI Image Integration Points

### 2.1 Visual Aids for Translation

**Idea**: Generate or retrieve images to illustrate Quenya words/concepts

- **Use case**: Show user a picture when translating "warrior" → "mahtar"
- **Implementation**: Could use DALL-E, Stable Diffusion, or image search API
- **Data source**: Could cache images alongside vocabulary DB
- **UX impact**: Visual confirmation of word meaning; educational value

### 2.2 Glyph/Script Rendering

**Idea**: Render Quenya output in Tengwar (elvish script) or other writing systems

- **Use case**: Display "i mahtar vanta málosessë" in visual Tengwar form
- **Implementation**: 
  - Could use pre-computed glyph mappings (rule-based)
  - Could train small image generation model on elvish script
  - Could call Tengwar font library + render as image
- **Data source**: Tolkien's script documentation, font libraries

### 2.3 Semantic Image Search in Q&A

**Idea**: Enhance Q&A by retrieving and displaying related images

- **Use case**: User asks "What does a warrior look like?" → retrieve + display image
- **Implementation**:
  - Extend FAISS to include image embeddings (CLIP, BLIP)
  - Multi-modal search: text query → combined text+image results
  - Cache images alongside text chunks
- **Data source**: Could scrape/curate Tolkien art, or generate via diffusion model

### 2.4 Illustrated Grammar Lessons

**Idea**: Create mini visual explanations for complex grammar rules

- **Use case**: When user asks about noun declension, show animated breakdown
- **Implementation**:
  - Generate diagrams showing case endings (e.g., cirya → ciryanna)
  - Use image synthesis to create educational charts
  - Could animate transformations (word → inflected form)
- **Data source**: Generated on-demand via Graphviz, Matplotlib, or diffusion model

### 2.5 Handwriting / Calligraphy Generation

**Idea**: Render Quenya output as beautiful handwritten/calligraphic text

- **Use case**: Make output visually appealing, feel "elvish"
- **Implementation**:
  - Fine-tune handwriting synthesis model (e.g., RNN-based)
  - Or use calligraphy fonts + render as high-quality image
  - Could cache rendered forms for fast delivery
- **Data source**: Training on historical elvish manuscript styles

---

## 3. Recommended Starting Points

### Quick Win (1-2 days)
- **Image search integration**: Add image retrieval to Q&A tab using CLIP embeddings
- **Effort**: Extend FAISS schema to include image vectors, cache images
- **Impact**: Q&A becomes multi-modal without touching translation pipeline

### Medium Effort (3-5 days)
- **Tengwar rendering**: Use existing font library to render Quenya in script form
- **Effort**: Mapping + font library integration + caching
- **Impact**: High visual polish, educational value

### Higher Effort (1-2 weeks)
- **Fine-tuned image generation**: Train small diffusion model on elvish-themed art
- **Effort**: Curate training data, fine-tune, integrate into app
- **Impact**: Unique visual experience, could differentiate product

---

## 4. Technical Considerations

### Storage & Caching
- **FAISS**: Currently ~2.2MB (text chunks only)
- **With images**: Could grow to 50-200MB depending on image density
- **Strategy**: Cache popular forms/chunks; lazy-load on demand

### Latency
- **Current translation**: ~1-2s (spaCy + morphology + optional LLM)
- **With image generation**: Could add 2-5s if generating new images
- **Strategy**: Pre-cache common words; show placeholder while generating

### Licensing & Attribution
- **If using generative models**: Clarify usage rights (DALL-E commercial, Stable Diffusion open)
- **If scraping images**: Ensure fair use / attribution
- **Recommendation**: Start with open-source models or public domain data

### Model Selection
- **Image embedding**: CLIP (multimodal), BLIP (vision-language)
- **Image generation**: Stable Diffusion (open), DALL-E (closed)
- **Text-to-calligraphy**: HWR (Handwriting Recognition) models, or rule-based fonts
- **Tengwar rendering**: No ML needed; use existing font libraries

---

## 5. Data Architecture Questions for Discussion

1. **Image embedding model**: Which one?
   - CLIP (proven, general-purpose)
   - BLIP (vision-language, newer)
   - Custom-fine-tuned on elvish art?

2. **Image caching strategy**:
   - Pre-compute + store all 8K vocabulary images? (expensive)
   - On-demand generation + cache popular queries?
   - Hybrid: pre-cache nouns, generate verbs on demand?

3. **Tengwar encoding**:
   - Use existing font libraries (Eldar, Cirth fonts)?
   - Train a neural font rendering model?
   - Rule-based mapping (simple but less flexible)?

4. **Integration scope**:
   - Only enhance Q&A (lower risk)?
   - Also enhance translation output (higher impact but more dev)?
   - Both?

5. **User experience**:
   - Show images inline with results?
   - Separate "Image gallery" tab?
   - Toggle to hide images if user prefers text-only?

---

## 6. Code Pointers for Next Session

**Files to extend**:
- `app.py`: Add image display UI
- `src/embeddings.py`: Add image embedding pipeline
- `src/retrieval.py`: Extend hybrid search to include images
- New: `src/image_utils.py` or `src/image_synthesis.py`

**Existing patterns to leverage**:
- `load_resources()` caching pattern (good for image cache)
- `SyntaxResult` dataclass (could add `image_url` field)
- Streamlit expanders for showing/hiding images

**Dependencies to add**:
```
torch>=2.0
transformers>=4.30  (for CLIP/BLIP)
diffusers>=0.20     (for Stable Diffusion if generating)
pillow>=9.0         (image processing)
```

---

## 7. Current Implementation Status

**What's Done** ✅
- 4-layer translation pipeline (fully functional)
- Confidence system (HIGH/MEDIUM/LOW with Rule IDs)
- FAISS + SQLite retrieval
- 116 tests passing
- Streamlit deployment

**What's NOT Yet Done** ❌
- Image integration
- Multi-modal search
- Script rendering
- Image caching/serving

---

## 8. Questions to Answer in Next Session

- [ ] Should we start with image search (Q&A tab) or visual translation output?
- [ ] Which embedding model minimizes latency?
- [ ] How do we handle image licensing/attribution?
- [ ] Should Tengwar be rule-based or ML-based?
- [ ] What's the target scope: nice-to-have or core feature?
- [ ] Budget for compute (image generation/caching)?
- [ ] Mobile-friendly image serving strategy?

---

**Next Steps**: Load this context into a fresh Claude session and discuss implementation strategy for AI image integration.
