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
from html import escape

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from src.embeddings import load_model
from src.retrieval   import load_faiss, retrieve, search_faiss
from src.llm         import answer
from src.lore_generator_p4 import generate_lore_p4
from src.lore_generator_generic import generate_lore_for_universe
from src.router      import classify_request
from src.knowledge_graph import KG_DB_PATH, KnowledgeGraph
from src.layer_registry import LAYER_META, LAYER_ORDER
from src.pipeline_executor import execute_pipeline, format_final_output


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


@st.cache_resource
def load_universe_resources(universe: str):
    try:
        model = load_model()
        index, metadata = load_faiss(
            index_path=f"vector_db/{universe}/faiss.index",
            meta_path=f"vector_db/{universe}/metadata.json",
        )
        return model, index, metadata
    except Exception as e:
        return None, None, str(e)


# ==============================================================================
# PAGE CONFIG
# ==============================================================================

st.set_page_config(
    page_title="Elmehdi Fiction",
    page_icon="📚",
    layout="centered",
)

st.title("📚 Elmehdi Fiction")
st.markdown("### 🧝 Elfique")
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
    reason = escape(str(route.get("reason", "")))
    st.markdown(
        f"**→ {route['label']}** &nbsp; "
        f"<span style='color:grey;font-size:0.85em;'>({method_badge} · {reason})</span>",
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
# EMPIRE TERRAN
# ==============================================================================

st.divider()
st.markdown("### 🖖 Empire Terran")
st.caption("Univers miroir de Star Trek — explorez le lore de l'Empire Terran et de l'Alliance Klingon-Cardassian.")

with st.spinner("Chargement de l'index Empire Terran…"):
    _te_model, _te_index, _te_meta = load_universe_resources("terran_empire")

_te_available = _te_model is not None and _te_index is not None

te_tab_qa, te_tab_lore = st.tabs(["💬 Q&A", "📖 Générer du Lore"])

with te_tab_qa:
    te_input = st.text_area(
        label="Votre question",
        placeholder=(
            "Ex : Who is the Intendant?\n"
            "Ex : What is the Agony Booth?\n"
            "Ex : How did the Terran Empire fall?"
        ),
        height=100,
        key="te_input",
    )
    te_submit = st.button("⚡ Envoyer", type="primary", key="te_submit")

    if te_submit and te_input.strip():
        if not _te_available:
            st.error("❌ Index Empire Terran non disponible.")
        elif not _groq_key:
            st.error("❌ GROQ_API_KEY manquante.")
        else:
            with st.spinner("Recherche dans le lore de l'Empire Terran…"):
                faiss_results = search_faiss(te_input, _te_model, _te_index, _te_meta, k=3)
            with st.spinner("Génération de la réponse…"):
                response = answer(te_input, faiss_results, [])
            st.markdown("### Réponse")
            st.write(response)
            with st.expander("Sources utilisées"):
                for r in faiss_results:
                    src = r.get("source", "").split("/")[-1]
                    st.markdown(f"*{src}* — score {r['score']:.3f}")
                    st.caption(r["text"][:300])

with te_tab_lore:
    te_lore_input = st.text_area(
        label="Votre requête de lore",
        placeholder=(
            "Ex : Invent a secret rebel cell operating inside Terok Nor\n"
            "Ex : Create a Terran officer who survived the fall of the Empire\n"
            "Ex : Write about a skirmish between the Rebellion and Alliance forces"
        ),
        height=120,
        key="te_lore_input",
    )
    te_lore_submit = st.button("✨ Générer", type="primary", key="te_lore_submit")

    if te_lore_submit and te_lore_input.strip():
        if not _te_available:
            st.error("❌ Index Empire Terran non disponible.")
        elif not _anthropic_key:
            st.error("❌ ANTHROPIC_API_KEY manquante.")
        else:
            with st.spinner("Récupération du contexte + génération…"):
                result = generate_lore_for_universe(
                    user_request=te_lore_input,
                    universe_name="Terran Empire (Star Trek Mirror Universe)",
                    api_key=_anthropic_key,
                    model=_te_model,
                    index=_te_index,
                    metadata=_te_meta,
                    universe_id="terran_empire",
                )
            if result["success"]:
                st.markdown("### 📖 Lore généré")
                st.write(result["story"])
                st.caption(f"Contexte : {result['chunks_used']} passages utilisés")
                kg_validation = result.get("kg_validation") or {}
                if kg_validation.get("warning"):
                    st.info(f"Validation KG non appliquée : {kg_validation['warning']}")
                if result.get("kg_violations"):
                    st.warning(f"{len(result['kg_violations'])} violation(s) canon détectée(s).")
                    with st.expander("Voir les violations KG"):
                        st.json(result["kg_violations"])
            else:
                st.error(f"❌ {result['error']}")


# ==============================================================================
# MODE MANUEL (expander — accès direct aux pipelines)
# ==============================================================================

def _pipeline_html(layer_ids: list[str]) -> str:
    """Génère une ligne HTML 'Pipeline : L01 → L02 → ...' avec tooltips au survol."""
    parts = []
    for lid in layer_ids:
        meta = LAYER_META[lid]
        desc = meta.description.replace('"', "&quot;")
        parts.append(
            f'<span title="{desc}" style="'
            f"border-bottom:1px dashed #aaa;cursor:help;"
            f'">{meta.emoji} <b>{lid}</b> {meta.name}</span>'
        )
    arrow = ' <span style="color:#888">→</span> '
    return "<small><b>Pipeline :</b> " + arrow.join(parts) + "</small>"


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
        st.markdown(_pipeline_html(["L01", "L02", "L03", "L13"]), unsafe_allow_html=True)
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
        st.markdown(_pipeline_html(["L04", "L05", "L06"]), unsafe_allow_html=True)
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
        st.markdown(_pipeline_html(["L01", "L02", "L07", "L08", "L09"]), unsafe_allow_html=True)
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


# ==============================================================================
# LAB MODE (expander — sélection libre des layers atomiques)
# ==============================================================================

def _render_layer_output(output, otype):
    if otype == "text":
        st.write(output)
    elif otype == "json_rewrite":
        st.json(output)
    elif otype == "json_chunks":
        if output:
            for chunk in output[:3]:
                st.caption(f"[score {chunk.get('score', 0):.3f}] {chunk.get('source', '').split('/')[-1]}")
                st.write(chunk.get("text", "")[:300])
        else:
            st.caption("Aucun chunk trouvé.")
    elif otype == "json_dict":
        if output:
            for e in output[:5]:
                st.markdown(f"**{e.get('word')}** ({e.get('language')}) → {e.get('translation')}")
        else:
            st.caption("Aucune entrée trouvée.")
    elif otype == "semantic_ir":
        if hasattr(output, "predicate") and output.predicate:
            st.markdown(f"**Prédicat :** `{output.predicate.lemma}` [{output.predicate.tense} · {output.predicate.mood}]")
            for arg in (output.arguments or []):
                st.markdown(f"- **{arg.role.upper()}** : `{arg.lemma}` [{arg.case} · {arg.number}]")
        else:
            st.caption("Aucun prédicat détecté.")
    elif otype == "morph_forms":
        for f in output:
            st.markdown(f"**{f.english_lemma}** → `{f.quenya_form}` · {f.feature}")
    elif otype == "syntax_result":
        if hasattr(output, "quenya_sentence"):
            st.markdown(f"### {output.quenya_sentence}")
            st.caption(f"Règle : {output.word_order_rule} · Confiance : {output.confidence:.0%}")
    elif otype == "text_constraints":
        st.write(output)
    elif otype == "json_story":
        if isinstance(output, dict):
            st.write(output.get("story", ""))
            for w in output.get("warnings", []):
                st.warning(str(w))
        else:
            st.write(str(output))
    else:
        st.write(str(output))


with st.expander("🔬 Lab Mode — composition libre des layers"):
    st.caption(
        "Sélectionne directement les layers à combiner. "
        "Chaque layer est une unité atomique indépendante. "
        "Exécution dans l'ordre numérique (L01 → L13)."
    )

    # ── Sélecteur d'univers ───────────────────────────────────────────────────
    UNIVERSE_OPTIONS = {
        "🧝 Elfique (Tolkien)":        {"index": index,     "meta": metadata,  "model": model,     "universe": "Tolkien's Middle-earth"},
        "🖖 Empire Terran (Star Trek)": {"index": _te_index, "meta": _te_meta,  "model": _te_model, "universe": "Terran Empire (Star Trek Mirror Universe)"},
    }

    lab_universe = st.selectbox(
        "Univers (corpus FAISS pour L02)",
        options=list(UNIVERSE_OPTIONS.keys()),
        key="lab_universe",
    )
    _lab_universe_res = UNIVERSE_OPTIONS[lab_universe]

    unavailable_layers = []
    if lab_universe == "🖖 Empire Terran (Star Trek)":
        unavailable_layers = ["L03", "L04", "L05", "L06"]
        st.info("ℹ️ L03 (dictionnaire), L04–L06 (traduction Quenya) ne s'appliquent pas à cet univers.")

    st.markdown("---")

    # ── Inventaire des 13 layers ──────────────────────────────────────────────
    lab_selected: list[str] = []
    col_a, col_b = st.columns(2)

    for i, lid in enumerate(LAYER_ORDER):
        meta = LAYER_META[lid]
        col  = col_a if i % 2 == 0 else col_b
        cost_icon = {"free": "🟢", "groq": "🔵", "claude": "🟣", "gpu": "🔴"}.get(meta.cost, "⚪")
        det = "déterministe" if meta.deterministic else "LLM"
        universe_incompatible = lid in unavailable_layers

        with col:
            if not meta.available:
                st.checkbox(
                    f"{meta.emoji} **{lid}** — {meta.name}  *(non disponible)*",
                    value=False, disabled=True, key=f"lab_{lid}",
                )
                st.caption(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;{meta.description}  \n"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;⚫ Phase future · `{meta.output_type}`"
                )
            elif universe_incompatible:
                st.checkbox(
                    f"{meta.emoji} **{lid}** — {meta.name}  *(hors univers)*",
                    value=False, disabled=True, key=f"lab_{lid}",
                )
                st.caption(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;{meta.description}  \n"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;🚫 Non applicable à cet univers · `{meta.output_type}`"
                )
            else:
                checked = st.checkbox(
                    f"{meta.emoji} **{lid}** — {meta.name}",
                    value=(lid in ["L01", "L02", "L13"]),
                    key=f"lab_{lid}",
                )
                st.caption(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;{meta.description}  \n"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;{cost_icon} `{meta.cost}` · `{meta.output_type}` · {det}"
                )
                if checked:
                    lab_selected.append(lid)

    lab_selected = sorted(lab_selected, key=lambda l: LAYER_ORDER.index(l))

    # ── Pipeline composé + avertissements ─────────────────────────────────────
    if lab_selected:
        pipeline_str = " → ".join(f"{LAYER_META[l].emoji} {l}" for l in lab_selected)
        st.markdown(f"**Pipeline actif :** `{pipeline_str}`")

        if "L05" in lab_selected and "L04" not in lab_selected:
            st.warning("⚠️ L05 a besoin de L04 en amont.")
        if "L06" in lab_selected and not ("L04" in lab_selected and "L05" in lab_selected):
            st.warning("⚠️ L06 a besoin de L04 + L05 en amont.")
        if "L07" in lab_selected and "L02" not in lab_selected:
            st.warning("⚠️ L07 fonctionne mieux avec L02 (FAISS) en amont.")
        if "L08" in lab_selected and "L07" not in lab_selected:
            st.warning("⚠️ L08 fonctionne mieux avec L07 (Constraints) en amont.")
        if "L09" in lab_selected and "L08" not in lab_selected:
            st.warning("⚠️ L09 nécessite L08 en amont.")
    else:
        st.info("Aucune layer sélectionnée.")

    # ── Input + exécution ─────────────────────────────────────────────────────
    lab_input = st.text_input(
        "Input",
        placeholder="Ex: What does elda mean? / The warrior walks. / Invent an elf tribe.",
        key="lab_input",
    )
    lab_go = st.button("▶️ Exécuter", type="primary", key="lab_go", disabled=not lab_selected)

    if lab_go and lab_input and lab_selected:
        _lab_res = {
            "model":    _lab_universe_res["model"],
            "index":    _lab_universe_res["index"],
            "meta":     _lab_universe_res["meta"],
            "universe": _lab_universe_res["universe"],
        }
        with st.spinner("Exécution…"):
            lab_result = execute_pipeline(lab_selected, lab_input, _lab_res)

        st.markdown("---")
        st.markdown("**Sorties par layer**")

        for step in lab_result["trace"]:
            lid = step["layer_id"]
            lr  = lab_result["outputs"].get(lid)
            ok  = step["output_type"] != "error"
            with st.expander(
                f"{'✅' if ok else '❌'} {step['emoji']} **{step['name']}** `{lid}` "
                f"— {step['label']} · {step['duration_ms']} ms",
                expanded=ok,
            ):
                c1, c2, c3 = st.columns(3)
                c1.caption(f"→ `{step['output_type']}`")
                c2.caption(f"`{LAYER_META[lid].cost}`")
                c3.caption("✅ déterministe" if LAYER_META[lid].deterministic else "🎲 LLM")
                if lr:
                    _render_layer_output(lr.output, lr.output_type)

        st.markdown("---")
        st.markdown("**Résultat final**")
        if lab_result["error"]:
            st.error(f"❌ {lab_result['error']}")
        else:
            st.success(format_final_output(lab_result))

    elif lab_go and not lab_input:
        st.warning("Entre un input avant d'exécuter.")
