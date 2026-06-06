"""Interface Streamlit pour le RAG Elfique.

Trois onglets :
  💬 Q&A           — Phase 1 : questions sur Quenya/Sindarin
  🧝 Translate      — Phase 2 : traduction anglais → Quenya (pipeline déterministe)
  📖 Generate Lore  — Phase 3 : génération de lore (Claude) + validation déterministe (KG)

Lance avec :
    streamlit run app.py
"""

import os
import sys

# Guarantee the repo root is in sys.path so "from src.xxx import ..." always
# resolves correctly, regardless of how Streamlit Cloud sets up the environment.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from src.embeddings import load_model
from src.retrieval  import load_faiss, retrieve
from src.llm        import answer
from src.lore_generator_p4 import generate_lore_p4

# ---------------------------------------------------------------------------
# Chargement des ressources avec cache
# ---------------------------------------------------------------------------

@st.cache_resource
def load_resources():
    """Charge le modèle, l'index FAISS et les metadata une seule fois.

    Returns (None, None, None) if the vector index hasn't been built yet —
    the app degrades gracefully: Translate tab still works, Q&A tab shows
    a clear message instead of crashing the whole app.
    """
    try:
        model           = load_model()
        index, metadata = load_faiss()
        return model, index, metadata
    except Exception as e:
        # Index not built yet — not a fatal error for the app as a whole
        return None, None, str(e)


# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RAG Elfique",
    page_icon="🧝",
    layout="centered",
)

st.title("🧝 RAG Elfique")
st.caption("Quenya & Sindarin — questions et traductions")

with st.spinner("Chargement des ressources…"):
    model, index, metadata = load_resources()

# Detect whether Q&A resources are available
_qa_available = model is not None and index is not None

# ---------------------------------------------------------------------------
# Tabs : Q&A (Phase 1) | Translate (Phase 2) | Generate Lore (Phase 3)
# ---------------------------------------------------------------------------

tab_qa, tab_translate, tab_lore = st.tabs([
    "💬 Q&A (Phase 1)",
    "🧝 Translate (Phase 2)",
    "📖 Generate Lore (Phase 3)",
])

# ============================= TAB 1 — Q&A ==================================

with tab_qa:
    st.markdown("**Phase 1 — Q&A** · Posez une question sur les langues elfiques de Tolkien.")

    if not _qa_available:
        st.warning(
            "⚠️ **Index de recherche non disponible**  \n"
            "La base vectorielle (FAISS) n'a pas encore été construite sur ce déploiement.  \n"
            "Le tab **🧝 Translate** fonctionne normalement — utilisez-le pour les traductions."
        )
    else:
        question = st.text_input(
            label="Votre question",
            placeholder="Ex: What does elda mean? / How does the plural work in Quenya?",
            key="qa_input",
        )

        if question:
            with st.spinner("Analyse de la question..."):
                results = retrieve(question, model, index, metadata, k=3)

            with st.spinner("Génération de la réponse..."):
                response = answer(question, results["faiss"], results["dictionary"])

            st.markdown("### Réponse")
            st.write(response)

            rewriter = results.get("rewriter", {})
            if rewriter:
                query_type = rewriter.get("type", "?")
                keyword    = rewriter.get("keyword", "?")
                badge = "🟢 vocabulaire" if query_type == "vocabulary" else "🔵 lore / grammaire"
                st.caption(f"Agent → {badge} · mot-clé recherché : **{keyword}**")

            with st.expander("Voir les sources utilisées"):
                if results["dictionary"]:
                    st.markdown("**Dictionnaire (SQLite)**")
                    for entry in results["dictionary"][:5]:
                        st.markdown(
                            f"- **{entry.get('word')}** ({entry.get('language')}) "
                            f"→ {entry.get('translation')}"
                        )
                if results["faiss"]:
                    st.markdown("**Passages (FAISS)**")
                    for r in results["faiss"]:
                        source = r.get("source", "").split("/")[-1]
                        st.markdown(f"*{source}* — score {r['score']:.3f}")
                        st.caption(r["text"][:300])


# ========================= TAB 2 — TRANSLATE ================================

with tab_translate:
    st.markdown(
        "**Phase 2 — Sentence translation**  \n"
        "Layer 2 computes Quenya word forms deterministically before Layer 3 "
        "assembles them. The LLM (Layer 4) does NOT compute morphology here — it only styles "
        "the pre-computed forms."
    )

    # Check if spaCy is installed (the model downloads automatically on first use)
    try:
        import spacy as _spacy_check
        _spacy_ok = True
    except ImportError:
        _spacy_ok = False

    if not _spacy_ok:
        st.error(
            "spaCy is not installed. Run:  \n"
            "`pip install spacy`  \n"
            "Then restart the app."
        )
    else:
        sentence = st.text_input(
            label="English sentence",
            placeholder="Ex: The warrior walks into the forest.",
            key="translate_input",
        )
        st.caption("Use grammatically correct English — subject + conjugated verb + optional objects.")

        if sentence:
            from src.translator import translate

            with st.spinner("Parsing + computing morphological forms…"):
                try:
                    result = translate(sentence)
                except Exception as e:
                    st.error(f"Translation error: {e}")
                    result = None

            if result:
                # --- Parse failure: show error + suggestion, no hallucinated output ---
                if not result.quenya_sentence:
                    st.error("❌ Translation failed — the sentence could not be parsed.")
                    if result.warning:
                        for line in result.warning.split("\n"):
                            st.markdown(line)
                    st.info(
                        "**Tips for best results:**\n"
                        "- Use correct English grammar (subjects and verbs must agree)\n"
                        "- Keep one clear subject + verb + optional objects\n"
                        "- Example: *The warrior walks into the forest.*"
                    )
                    result = None

            if result:
                # --- Main output ---
                st.markdown("### Quenya")
                st.markdown(f"**{result.quenya_sentence}**")

                if result.warning:
                    st.warning(f"⚠️ {result.warning}")

                # Map confidence level to emoji badge
                from src.morphology import ConfidenceLevel
                conf_badge = {
                    ConfidenceLevel.HIGH: "🟢 HIGH",
                    ConfidenceLevel.MEDIUM: "🟡 MEDIUM",
                    ConfidenceLevel.LOW: "🔴 LOW",
                }.get(result.confidence_floor, "⚪ UNKNOWN")

                st.caption(
                    f"Confidence floor: **{conf_badge}** · "
                    f"LLM used: {'yes' if result.llm_used else 'no (fallback assembly)'}"
                )

                if result.explanation:
                    st.markdown(f"*{result.explanation}*")

                # --- Layer 2 detail (expandable) ---
                with st.expander("🔬 Layer 2 — computed word forms"):
                    st.markdown(
                        "These forms were computed **deterministically** by the "
                        "morphological engine — no LLM involved."
                    )
                    for f in result.morphed_forms:
                        reliable = f.is_reliable()
                        icon = "✅" if reliable else "⚠️"

                        from src.morphology import ConfidenceLevel
                        conf_emoji = {
                            ConfidenceLevel.HIGH: "🟢",
                            ConfidenceLevel.MEDIUM: "🟡",
                            ConfidenceLevel.LOW: "🔴",
                        }.get(f.confidence_level, "⚪")

                        attestation_badge = {
                            "attested": "📜 attested",
                            "reconstructed": "🔄 reconstructed",
                            "neo-quenya": "✨ neo-quenya",
                        }.get(f.attestation, "❓ unknown")

                        st.markdown(
                            f"{icon} **{f.english_lemma}** → `{f.quenya_form}`  \n"
                            f"&nbsp;&nbsp;&nbsp;&nbsp;"
                            f"*{f.feature}* · {attestation_badge} · {conf_emoji} {f.confidence_level.value} · {f.source_note}"
                        )
                        if f.rule_id:
                            st.caption(f"    rule: {f.rule_id}")
                        if f.warning:
                            st.caption(f"    ⚠️ {f.warning}")

                # --- Layer 3 detail (expandable) ---
                with st.expander("🧩 Layer 3 — Syntax assembly"):
                    st.markdown("Word order, particles, and oblique argument placement.")
                    st.caption(
                        "Deterministic rules: SOV word order (subject-object-verb) with optional particles."
                    )

                # --- Semantic IR (expandable) ---
                with st.expander("🔤 Layer 1 — Semantic IR (parsed structure)"):
                    from src.ir import parse_english
                    ir = parse_english(sentence)
                    st.markdown(f"**Predicate:** {ir.predicate.lemma} [{ir.predicate.tense} {ir.predicate.mood}]")
                    st.markdown("**Arguments:**")
                    for arg in ir.arguments:
                        st.markdown(
                            f"- {arg.role.upper()}: {arg.lemma} [{arg.case} {arg.number}]"
                        )


# ========================= TAB 3 — GENERATE LORE (Phase 3 — KG) ==============

with tab_lore:
    st.markdown("""**Phase 3 — Lore Generation**
Generate creative stories and lore compatible with Tolkien canon.
The model retrieves FAISS context, generates with Claude, then validates
**deterministically** against the Knowledge Graph — no second LLM call.

**What the KG checks:**
- Role assertions — *"X is king of Doriath"* → is X actually Thingol?
- Creation claims — *"X forged the Silmarils"* → were they created by Feanor?
- Canon fact patterns — Beleriand in 2nd Age, Morgoth post-War of Wrath, etc.

**Examples:**
- *"Invent an elf tribe in Beleriand during the First Age"*
- *"Create a Sindarin culture in Mirkwood during the Second Age"*
- *"What if there was a dwarf kingdom in the Grey Mountains?"*
""")

    # KG status banner
    from src.knowledge_graph import KG_DB_PATH, KnowledgeGraph
    _kg_ready = KG_DB_PATH.exists()
    if not _kg_ready:
        st.warning(
            "⚠️ **Knowledge Graph not built yet.**  \n"
            "Run `python scripts/build_kg.py` from the project root to populate it."
        )
    else:
        with KnowledgeGraph() as _kg:
            _kg_stats = _kg.get_stats()
        st.caption(
            f"🗂️ KG: **{_kg_stats['entities']} entities** · "
            f"**{_kg_stats['relations']} relations** · "
            f"**{_kg_stats['canon_facts']} canon rules** · "
            f"validation: deterministic (no extra API call)"
        )

    lore_request = st.text_area(
        label="Lore Generation Request",
        placeholder="Invent a tribe of elves in Beleriand...",
        height=100,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        generate_button = st.button("📖 Generate Lore", type="primary")
    with col2:
        show_kg_details = st.checkbox("Show KG validation details", value=True)

    if generate_button and lore_request:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("❌ ANTHROPIC_API_KEY not found. Add it to your Streamlit Cloud secrets.")
        elif not _qa_available:
            st.error("❌ FAISS index not available. Cannot retrieve context for generation.")
        elif not _kg_ready:
            st.error("❌ Knowledge Graph not built. Run `python scripts/build_kg.py` first.")
        else:
            with st.spinner("🔍 Retrieving FAISS context + generating story…"):
                result = generate_lore_p4(
                    user_request=lore_request,
                    api_key=api_key,
                    model=model,
                    index=index,
                    metadata=metadata,
                )

            if result["success"]:
                st.markdown("### 📖 Generated Lore")
                st.write(result["story"])

                st.markdown("---")
                validation = result["validation"]

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("Location", result["context"]["location"])
                with col_b:
                    st.metric("Species", result["context"]["species"])
                with col_c:
                    st.metric("KG Score", f"{validation.get('score', 0)}/100")
                with col_d:
                    is_valid = validation.get("is_valid", False)
                    st.metric("Canon", "✅ Valid" if is_valid else "❌ Violations")

                entities_found = validation.get("entities_found", [])
                if entities_found:
                    st.info(f"🗺️ Canon entities detected: **{', '.join(entities_found)}**")

                if show_kg_details:
                    violations = validation.get("violations", [])
                    st.markdown("### 🔍 KG Validation")

                    if not violations:
                        st.success("✅ **No canon violations detected.**")
                    else:
                        st.warning(f"⚠️ {len(violations)} violation(s) found:")
                        for v in violations:
                            severity = v.get("severity", "SOFT")
                            icon = "🔴" if severity == "HARD" else "🟡"
                            st.markdown(
                                f"{icon} **{severity}** · _{v.get('text', '')}_  \n"
                                f"→ {v.get('canon', '')}"
                            )

                    with st.expander("ℹ️ How validation works"):
                        st.markdown(
                            "Validation is **deterministic** — no LLM involved.  \n"
                            "- Role assertions: regex match → KG lookup  \n"
                            "- Canon facts: pattern match against 12 hard rules  \n"
                            "- Score: 100 − 25×HARD − 10×SOFT  \n\n"
                            f"Method: `{validation.get('method', 'knowledge_graph')}`"
                        )
            else:
                st.error(f"❌ {result['error']}")
