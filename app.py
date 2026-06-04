"""Interface Streamlit pour le RAG Elfique.

Deux onglets :
  💬 Q&A      — pipeline existante (Phase 1) : questions sur Quenya/Sindarin
  🧝 Translate — pipeline Phase 2 : traduction anglais → Quenya (Layer 2.5)

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

# ---------------------------------------------------------------------------
# Chargement des ressources avec cache
# ---------------------------------------------------------------------------

@st.cache_resource
def load_resources():
    """Charge le modèle, l'index FAISS et les metadata une seule fois."""
    model           = load_model()
    index, metadata = load_faiss()
    return model, index, metadata


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

with st.spinner("Chargement du modèle et de l'index..."):
    model, index, metadata = load_resources()

# ---------------------------------------------------------------------------
# Tabs : Q&A (Phase 1)  |  Translate (Phase 2)
# ---------------------------------------------------------------------------

tab_qa, tab_translate = st.tabs(["💬 Q&A", "🧝 Translate (Phase 2)"])

# ============================= TAB 1 — Q&A ==================================

with tab_qa:
    st.markdown("Posez une question sur les langues elfiques de Tolkien.")

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
        "Layer 2.5 computes Quenya word forms deterministically before the LLM "
        "arranges them. The LLM does NOT compute morphology here — it only styles "
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
                    # Stop here — don't show empty/broken sections below
                    result = None

            if result:
                # --- Main output ---
                st.markdown("### Quenya")
                st.markdown(f"**{result.quenya_sentence}**")

                if result.warning:
                    st.warning(f"⚠️ {result.warning}")

                st.caption(
                    f"Confidence floor: **{result.confidence_floor:.0%}** · "
                    f"LLM used: {'yes' if result.llm_used else 'no (fallback assembly)'}"
                )

                if result.explanation:
                    st.markdown(f"*{result.explanation}*")

                # --- Layer 2.5 detail (expandable) ---
                with st.expander("🔬 Layer 2.5 — computed word forms"):
                    st.markdown(
                        "These forms were computed **deterministically** by the "
                        "morphological engine — no LLM involved."
                    )
                    for f in result.morphed_forms:
                        reliable = f.is_reliable()
                        icon = "✅" if reliable else "⚠️"

                        # Attestation badge
                        attestation_badge = {
                            "attested": "📜 attested",
                            "reconstructed": "🔄 reconstructed",
                            "neo-quenya": "✨ neo-quenya",
                        }.get(f.attestation, "❓ unknown")

                        st.markdown(
                            f"{icon} **{f.english_lemma}** → `{f.quenya_form}`  \n"
                            f"&nbsp;&nbsp;&nbsp;&nbsp;"
                            f"*{f.feature}* · {attestation_badge} · conf {f.confidence:.0%} · {f.source_note}"
                        )
                        if f.warning:
                            st.caption(f"    {f.warning}")

                # --- Layer 2.8 detail (expandable) ---
                with st.expander("🧩 Layer 2.8 — Syntax assembly"):
                    st.markdown("Word order, particles, and oblique argument placement.")
                    st.caption(
                        f"Word order: **{result.morphed_forms[-1] if result.morphed_forms else 'N/A'}**"
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
