"""Interface Streamlit pour le RAG Elfique.

Interface unifiée : un seul champ de saisie.
L'agent routeur analyse la requête et dirige vers le bon pipeline :

  Phase 1 — Q&A        : questions sur Quenya/Sindarin/lore
  Phase 2 — Traduction  : anglais → Quenya (pipeline déterministe)
  Phase 3 — Lore        : génération de lore (Claude + KG validation)

Lance avec :
    streamlit run app.py
"""

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from src.embeddings import load_model
from src.retrieval   import load_faiss, retrieve
from src.llm         import answer
from src.lore_generator_p4 import generate_lore_p4
from src.router      import classify_request
from src.knowledge_graph import KG_DB_PATH, KnowledgeGraph


# ==============================================================================
# CACHE
# ==============================================================================

@st.cache_resource
def load_resources():
    try:
        model           = load_model()
        index, metadata = load_faiss()
        return model, index, metadata
    except Exception as e:
        return None, None, str(e)


# ==============================================================================
# PAGE CONFIG
# ==============================================================================

st.set_page_config(
    page_title="RAG Elfique",
    page_icon="🧝",
    layout="centered",
)

st.title("🧝 RAG Elfique")
st.caption("Quenya & Sindarin — posez une question, demandez une traduction, ou générez du lore.")

with st.spinner("Chargement des ressources…"):
    model, index, metadata = load_resources()

_qa_available  = model is not None and index is not None
_kg_ready      = KG_DB_PATH.exists()
_anthropic_key = os.getenv("ANTHROPIC_API_KEY")
_groq_key      = os.getenv("GROQ_API_KEY")


# ==============================================================================
# UNIFIED INPUT
# ==============================================================================

user_input = st.text_area(
    label="Votre requête",
    placeholder=(
        "Ex : What does 'elda' mean?\n"
        "Ex : Translate: the warrior walks into the forest\n"
        "Ex : Invent an elf tribe in Beleriand during the First Age"
    ),
    height=100,
    key="main_input",
)

submit = st.button("✨ Envoyer", type="primary")

# ==============================================================================
# ROUTING + EXECUTION
# ==============================================================================

if submit and user_input.strip():

    # ── 1. Classify ─────────────────────────────────────────────────────────
    with st.spinner("Analyse de la requête…"):
        route = classify_request(user_input, api_key=_groq_key)

    # ── 2. Display routing decision ──────────────────────────────────────────
    method_badge = "🔵 règles" if route["method"] == "rules" else "🟣 LLM"
    st.markdown(
        f"**→ {route['label']}** &nbsp; "
        f"<span style='color:grey;font-size:0.85em;'>({method_badge} · {route['reason']})</span>",
        unsafe_allow_html=True,
    )

    # Layer trace
    layers_str = " → ".join(route["layers"])
    st.caption(f"Layers : {layers_str}")
    st.divider()

    # ── 3. Execute ──────────────────────────────────────────────────────────

    # ──────────────── Q&A ───────────────────────────────────────────────────
    if route["route"] == "qa":

        if not _qa_available:
            st.warning("⚠️ Index FAISS non disponible — Q&A indisponible sur ce déploiement.")
        elif not _groq_key:
            st.error("❌ GROQ_API_KEY manquante.")
        else:
            with st.spinner("Recherche + génération de réponse…"):
                results  = retrieve(user_input, model, index, metadata, k=3)
                response = answer(user_input, results["faiss"], results["dictionary"])

            st.markdown("### Réponse")
            st.write(response)

            # Agent trace
            rewriter = results.get("rewriter", {})
            if rewriter:
                badge = "🟢 vocabulaire" if rewriter.get("type") == "vocabulary" else "🔵 lore / grammaire"
                st.caption(f"Query Rewriter → {badge} · mot-clé : **{rewriter.get('keyword', '?')}**")

            with st.expander("Sources utilisées"):
                if results["dictionary"]:
                    st.markdown("**Dictionnaire (SQLite)**")
                    for e in results["dictionary"][:5]:
                        st.markdown(f"- **{e.get('word')}** ({e.get('language')}) → {e.get('translation')}")
                if results["faiss"]:
                    st.markdown("**Passages (FAISS)**")
                    for r in results["faiss"]:
                        src = r.get("source", "").split("/")[-1]
                        st.markdown(f"*{src}* — score {r['score']:.3f}")
                        st.caption(r["text"][:300])

    # ──────────────── TRANSLATE ─────────────────────────────────────────────
    elif route["route"] == "translate":

        # Strip common translation prefixes so the engine gets the raw sentence
        import re as _re
        clean = _re.sub(
            r"^(translate[:\s]+|traduis[:\s]+|traduction[:\s]+|how do you say[:\s]+|comment dit-on[:\s]+)",
            "",
            user_input.strip(),
            flags=_re.IGNORECASE,
        ).strip().strip('"').strip("'")

        if not clean:
            st.warning("Impossible d'extraire la phrase à traduire. Essayez : *Translate: the warrior walks.*")
        else:
            try:
                import spacy as _spacy_check
                _spacy_ok = True
            except ImportError:
                _spacy_ok = False

            if not _spacy_ok:
                st.error("spaCy non installé. Exécutez `pip install spacy` puis relancez.")
            else:
                from src.translator import translate

                st.caption(f"Phrase détectée : *\"{clean}\"*")

                with st.spinner("Parsing + formes morphologiques…"):
                    try:
                        result = translate(clean)
                    except Exception as e:
                        st.error(f"Erreur de traduction : {e}")
                        result = None

                if result and not result.quenya_sentence:
                    st.error("❌ Traduction impossible — phrase non parsable.")
                    if result.warning:
                        for line in result.warning.split("\n"):
                            st.markdown(line)
                    st.info(
                        "**Conseils :**\n"
                        "- Utilisez une grammaire anglaise correcte\n"
                        "- Un sujet + un verbe conjugué + compléments\n"
                        "- Exemple : *The warrior walks into the forest.*"
                    )
                    result = None

                if result:
                    st.markdown("### Quenya")
                    st.markdown(f"**{result.quenya_sentence}**")

                    if result.warning:
                        st.warning(f"⚠️ {result.warning}")

                    from src.morphology import ConfidenceLevel
                    conf_badge = {
                        ConfidenceLevel.HIGH:   "🟢 HIGH",
                        ConfidenceLevel.MEDIUM: "🟡 MEDIUM",
                        ConfidenceLevel.LOW:    "🔴 LOW",
                    }.get(result.confidence_floor, "⚪ UNKNOWN")
                    st.caption(
                        f"Confiance : **{conf_badge}** · "
                        f"LLM : {'oui' if result.llm_used else 'non (assemblage déterministe)'}"
                    )
                    if result.explanation:
                        st.markdown(f"*{result.explanation}*")

                    with st.expander("🔬 Layer 2 — formes morphologiques"):
                        st.markdown("Formes calculées **déterministement** — pas de LLM.")
                        for f in result.morphed_forms:
                            icon = "✅" if f.is_reliable() else "⚠️"
                            conf_emoji = {
                                ConfidenceLevel.HIGH:   "🟢",
                                ConfidenceLevel.MEDIUM: "🟡",
                                ConfidenceLevel.LOW:    "🔴",
                            }.get(f.confidence_level, "⚪")
                            att_badge = {
                                "attested":      "📜 attested",
                                "reconstructed": "🔄 reconstructed",
                                "neo-quenya":    "✨ neo-quenya",
                            }.get(f.attestation, "❓ unknown")
                            st.markdown(
                                f"{icon} **{f.english_lemma}** → `{f.quenya_form}`  \n"
                                f"&nbsp;&nbsp;&nbsp;&nbsp;"
                                f"*{f.feature}* · {att_badge} · {conf_emoji} {f.confidence_level.value} · {f.source_note}"
                            )
                            if f.rule_id:
                                st.caption(f"    rule: {f.rule_id}")
                            if f.warning:
                                st.caption(f"    ⚠️ {f.warning}")

                    with st.expander("🧩 Layer 3 — Assemblage syntaxique"):
                        st.markdown("Ordre SOV, particules, arguments obliques.")
                        st.caption("Règles déterministes : subject-object-verb + particules.")

                    with st.expander("🔤 Layer 1 — IR sémantique (structure parsée)"):
                        from src.ir import parse_english
                        ir = parse_english(clean)
                        st.markdown(f"**Prédicat :** {ir.predicate.lemma} [{ir.predicate.tense} {ir.predicate.mood}]")
                        st.markdown("**Arguments :**")
                        for arg in ir.arguments:
                            st.markdown(f"- {arg.role.upper()} : {arg.lemma} [{arg.case} {arg.number}]")

    # ──────────────── LORE ──────────────────────────────────────────────────
    elif route["route"] == "lore":

        if not _anthropic_key:
            st.error("❌ ANTHROPIC_API_KEY manquante.")
        elif not _qa_available:
            st.error("❌ Index FAISS non disponible.")
        elif not _kg_ready:
            st.error("❌ Knowledge Graph non construit. Exécutez `python scripts/build_kg.py`.")
        else:
            with st.spinner("Récupération contexte FAISS + génération d'histoire…"):
                result = generate_lore_p4(
                    user_request=user_input,
                    api_key=_anthropic_key,
                    model=model,
                    index=index,
                    metadata=metadata,
                )

            if result["success"]:
                st.markdown("### 📖 Lore généré")
                st.write(result["story"])

                st.divider()
                validation = result["validation"]

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("Lieu", result["context"]["location"])
                with col_b:
                    st.metric("Espèce", result["context"]["species"])
                with col_c:
                    st.metric("Score KG", f"{validation.get('score', 0)}/100")
                with col_d:
                    is_valid = validation.get("is_valid", False)
                    st.metric("Canon", "✅ Valide" if is_valid else "❌ Violations")

                entities_found = validation.get("entities_found", [])
                if entities_found:
                    st.info(f"🗺️ Entités canon détectées : **{', '.join(entities_found)}**")

                violations = validation.get("violations", [])
                with st.expander("🔍 Validation KG", expanded=bool(violations)):
                    if not violations:
                        st.success("✅ Aucune violation canon détectée.")
                    else:
                        st.warning(f"⚠️ {len(violations)} violation(s) :")
                        for v in violations:
                            sev  = v.get("severity", "SOFT")
                            icon = "🔴" if sev == "HARD" else "🟡"
                            st.markdown(
                                f"{icon} **{sev}** · _{v.get('text', '')}_  \n"
                                f"→ {v.get('canon', '')}"
                            )
                    st.caption("Validation déterministe — 0 appel LLM supplémentaire.")
            else:
                st.error(f"❌ {result['error']}")


# ==============================================================================
# MODE MANUEL (expander — accès direct aux pipelines)
# ==============================================================================

st.divider()
with st.expander("⚙️ Mode manuel — accès direct aux pipelines"):
    st.caption("Utilisez cet espace si vous souhaitez forcer un pipeline spécifique.")

    tab_qa, tab_tr, tab_lore = st.tabs([
        "💬 Q&A (Phase 1)",
        "🧝 Traduction (Phase 2)",
        "📖 Lore (Phase 3)",
    ])

    # ── Q&A ──────────────────────────────────────────────────────────────────
    with tab_qa:
        if not _qa_available:
            st.warning("⚠️ Index FAISS non disponible.")
        else:
            q = st.text_input("Question", key="manual_qa")
            if q:
                with st.spinner("…"):
                    res = retrieve(q, model, index, metadata, k=3)
                    rep = answer(q, res["faiss"], res["dictionary"])
                st.markdown("### Réponse")
                st.write(rep)
                rw = res.get("rewriter", {})
                if rw:
                    badge = "🟢 vocabulaire" if rw.get("type") == "vocabulary" else "🔵 lore"
                    st.caption(f"Query Rewriter → {badge} · **{rw.get('keyword', '?')}**")
                with st.expander("Sources"):
                    for e in res["dictionary"][:5]:
                        st.markdown(f"- **{e.get('word')}** ({e.get('language')}) → {e.get('translation')}")
                    for r in res["faiss"]:
                        src = r.get("source", "").split("/")[-1]
                        st.markdown(f"*{src}* — {r['score']:.3f}")
                        st.caption(r["text"][:200])

    # ── TRANSLATE ─────────────────────────────────────────────────────────────
    with tab_tr:
        try:
            import spacy as _sp
            _sp_ok = True
        except ImportError:
            _sp_ok = False

        if not _sp_ok:
            st.error("spaCy non installé.")
        else:
            sent = st.text_input(
                "English sentence",
                placeholder="The warrior walks into the forest.",
                key="manual_tr",
            )
            if sent:
                from src.translator import translate as _translate
                with st.spinner("…"):
                    try:
                        tr = _translate(sent)
                    except Exception as e:
                        st.error(str(e))
                        tr = None
                if tr:
                    if not tr.quenya_sentence:
                        st.error("❌ Impossible de parser cette phrase.")
                    else:
                        st.markdown(f"**{tr.quenya_sentence}**")
                        from src.morphology import ConfidenceLevel
                        cb = {ConfidenceLevel.HIGH: "🟢 HIGH", ConfidenceLevel.MEDIUM: "🟡 MEDIUM", ConfidenceLevel.LOW: "🔴 LOW"}.get(tr.confidence_floor, "⚪")
                        st.caption(f"Confiance : {cb}")

    # ── LORE ──────────────────────────────────────────────────────────────────
    with tab_lore:
        if not _kg_ready:
            st.warning("⚠️ KG non construit.")
        elif not _anthropic_key:
            st.error("❌ ANTHROPIC_API_KEY manquante.")
        elif not _qa_available:
            st.error("❌ Index FAISS non disponible.")
        else:
            with KnowledgeGraph() as _kg:
                _stats = _kg.get_stats()
            st.caption(
                f"🗂️ KG : {_stats['entities']} entités · "
                f"{_stats['relations']} relations · "
                f"{_stats['canon_facts']} règles"
            )
            lreq = st.text_area("Requête lore", height=80, key="manual_lore")
            if st.button("Générer", key="manual_lore_btn"):
                with st.spinner("…"):
                    lr = generate_lore_p4(lreq, _anthropic_key, model, index, metadata)
                if lr["success"]:
                    st.write(lr["story"])
                    v = lr["validation"]
                    valid_str = "✅ valide" if v.get("is_valid") else "❌ violations"
                    st.caption(f"Score KG : {v.get('score', 0)}/100 · {valid_str}")
                else:
                    st.error(lr["error"])
