# 🧝 RAG Elfique

> **Un système multimodal d'exploration de l'univers de Tolkien** — traduction Quenya, Q&A sur le lore, génération narrative avec validation canonique, et à terme : images, sons, vidéos.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ragelven.streamlit.app)

---

## Vision

RAG Elfique n'est pas un simple traducteur. C'est une plateforme d'exploration de l'univers de Tolkien, construite couche par couche, qui ambitionne de devenir **le premier système multimodal lore-aware** dédié à cet univers.

```
Texte → Traduction Quenya        (Phase 2 ✅)
Texte → Génération de lore       (Phase 3 ✅)
Texte → Validation canon KG      (Phase 4 ✅)
Texte → Images                   (Phase 5 — à venir)
Texte → Sons / Musique elfique   (Phase 6 — à venir)
Texte → Vidéo narrative          (Phase 7 — à venir)
```

Le principe fondateur : **chaque génération respecte le canon Tolkien**. On peut inventer, mais on ne peut pas contredire.

---

## Phases de développement

### ✅ Phase 1 — Q&A (Terminée)

**Objectif :** Répondre à des questions sur les langues et le lore elfique.

**Architecture :**
```
Question utilisateur
    ↓
[Agent] Query Rewriter → identifie l'intention (vocabulaire ou lore)
    ↓
[FAISS] Recherche sémantique dans le corpus (1512 chunks)
    ↓
[SQLite] Lookup dictionnaire (8022 mots Quenya/Sindarin)
    ↓
[LLM Groq] Génère la réponse avec les sources
    ↓
Réponse avec sources citées
```

**Stack :**
- `sentence-transformers` — embeddings (`all-MiniLM-L6-v2`)
- `faiss-cpu` — recherche vectorielle
- `SQLite` — dictionnaire Quenya + Sindarin
- `Groq API` — LLM de réponse

**Données :**
- Cours Quenya PDF (~80 pages) → 1512 chunks FAISS
- 8022 mots en base SQLite
- Fichiers lore (Sindar, Noldor, Vanyar, Teleri...)

---

### ✅ Phase 2 — Traduction Quenya (Terminée)

**Objectif :** Traduire des phrases anglaises en Quenya de façon déterministe et traçable.

**Architecture (4 couches) :**
```
Phrase anglaise
    ↓
Layer 1 — src/ir.py          : spaCy → Semantic IR (sujet, verbe, objets, cas)
    ↓
Layer 2 — src/morphology.py  : formes Quenya déterministes (80+ règles)
    ↓
Layer 3 — src/syntax.py      : ordre SOV, particules, cas locatifs
    ↓
Layer 4 — src/llm.py         : polish stylistique optionnel (LLM)
    ↓
Phrase Quenya + explication
```

**Principes clés :**
- La morphologie est **déterministe** — pas d'hallucination LLM sur les formes
- **Système de confiance** : HIGH / MEDIUM / LOW par forme
- **Traçabilité complète** : chaque forme a un `rule_id` (ex: `RULE_NOUN_A_NOM_SG`)
- **Dégradation gracieuse** : l'app fonctionne sans LLM si nécessaire

**Couverture :**
- 116 tests unitaires (morphologie, syntaxe, validation)
- Déclinaisons : nominatif, accusatif, génitif, datif, locatif, allatif, ablatif, instrumental
- Conjugaisons : présent, passé, futur (singulier, pluriel, duel)

---

### ✅ Phase 3 — Génération de Lore (Terminée)

**Objectif :** Générer des histoires et du lore *inventé mais cohérent* avec l'univers Tolkien.

**Le défi :**
> Permettre la créativité. Protéger le canon.
>
> ✅ Bon : inventer une tribu elfique près de Doriath  
> ❌ Mauvais : cette tribu a forgé les Silmarils

**Architecture :**
```
Requête utilisateur ("Invente une tribu en Beleriand")
    ↓
[1] extract_context()      → localisation, période, espèce, langue
    ↓
[2] retrieve_context()     → FAISS : chunks pertinents comme contraintes
    ↓
[3] build_constraints()    → faits connus extraits des chunks
    ↓
[4] generate_story()       → Claude API + contexte + few-shot examples
    ↓
[5] validate_coherence()   → Claude re-vérifie les contradictions (2e appel LLM)
    ↓
Histoire générée + score de cohérence (0-100)
```

**Exemples de requêtes :**
- *"Invente une tribu d'elfes en Beleriand au Premier Âge"*
- *"Create a Sindarin kingdom in Mirkwood during the Second Age"*
- *"What if there was a dwarf kingdom in the Grey Mountains?"*

**Stack ajoutée :**
- `anthropic` — Claude Sonnet pour la génération et la validation

**Limitation identifiée :** La validation repose sur un second appel Claude — c'est mieux que rien, mais pas infaillible ni déterministe. C'est ce que Phase 4 résout.

---

### ✅ Phase 4 — Knowledge Graph (Terminée)

**Objectif :** Remplacer la validation LLM par une validation **entièrement déterministe** basée sur un graphe de connaissances extrait du corpus lore.

**Décision architecturale :**  
La Phase 4 est une copie isolée de la Phase 3. La Phase 3 (validation Claude) reste intacte pour la comparaison. Les deux tabs tournent côte à côte dans l'app.

**Le problème résolu :**
```
Phase 3 : génération Claude → validation Claude
           → circulaire, non-déterministe, 2 appels API

Phase 4 : génération Claude → validation KG (SQLite)
           → déterministe, reproductible, 0 appel API supplémentaire
```

**Architecture KG :**
```
Corpus lore (9 fichiers .txt)
    ↓
scripts/build_kg.py — extraction manuelle et curatée
    ↓
vector_db/knowledge_graph.sqlite
    ├── entities   — 126 entités (personnages, lieux, artefacts, groupes, événements, langues)
    ├── relations  — 131 relations typées (king_of, created, spouse_of, located_in…)
    └── canon_facts — 12 règles HARD/SOFT

    ↓
src/knowledge_graph.py — validate_story()
    ├── Détection d'assertions de rôle (regex + requête KG)
    │   "X est roi de Doriath" → Thingol est le roi de Doriath → VIOLATION HARD
    ├── Détection de création d'artefacts
    │   "X a forgé les Silmarils" → créés par Feanor → VIOLATION HARD
    └── Vérification des règles canon
        "Beleriand au 2e Âge" → Beleriand a sombré → VIOLATION SOFT
```

**Score Phase 4 :**
- 100 = aucune violation détectée
- -25 par violation HARD (contradiction claire)
- -10 par violation SOFT (improbable mais pas impossible)

**Exemples de violations détectées :**

| Histoire générée | Violation | Sévérité |
|-----------------|-----------|----------|
| "X était reine de Doriath" | Melian est la reine de Doriath | HARD |
| "X a créé les Silmarils" | Feanor a créé les Silmarils | HARD |
| "X a inventé le Tengwar" | Feanor a inventé le Tengwar | HARD |
| "Royaume en Beleriand au 2e Âge" | Beleriand a sombré à la fin du 1er Âge | SOFT |

**Ce qui reste possible en Phase 4+** (améliorations futures) :
- Enrichissement automatique du KG depuis les chunks FAISS (NLP extraction)
- Extension de la couverture 2e et 3e Âge (actuellement plus mince que 1er Âge)
- Patterns de détection plus sophistiqués (NLP plutôt que regex purs)
- Export d'un rapport de comparaison Phase 3 vs Phase 4 sur un jeu de tests commun

**Fichiers :**

| Fichier | Rôle |
|---------|------|
| `src/knowledge_graph.py` | Classe KG — connexion SQLite, validation, requêtes |
| `src/lore_generator_p4.py` | Pipeline Phase 4 (clone Phase 3 + KG validation) |
| `scripts/build_kg.py` | Population du KG (entités + relations + règles canon) |
| `vector_db/knowledge_graph.sqlite` | Base SQLite pré-construite (disponible sur Streamlit Cloud) |

---

### 🔜 Phase 5 — Images (Planifiée, session parallèle)

**Objectif :** Associer des images aux mots, concepts, et lore généré.

**Deux approches :**

#### 5a. Recherche d'images (rapide)
```
Mot traduit ("mahtar" = guerrier)
    ↓
CLIP embeddings → recherche dans une base d'images curées
    ↓
Image pertinente affichée
```

#### 5b. Génération d'images (plus riche)
```
Histoire générée (Phase 3/4)
    ↓
Stable Diffusion / DALL-E + prompt enrichi avec style elfique
    ↓
Illustration de la scène ou du personnage
```

**Cas d'usage :**
- Afficher une illustration quand on traduit un mot concret
- Générer une image de la tribu inventée en Phase 3/4
- Rendu Tengwar (script elfique) en image typographique

**Stack envisagée :**
- `CLIP` (OpenAI) — embeddings image+texte
- `diffusers` (Stable Diffusion) — génération
- `pillow` — traitement image
- Cache local des formes populaires

---

### 🔜 Phase 6 — Son / Musique (Planifiée)

**Objectif :** Donner une dimension sonore à l'univers elfique.

**Cas d'usage :**
- **Prononciation Quenya** : text-to-speech avec accent elfique (modèle TTS fine-tuné)
- **Musique d'ambiance** : générer des mélodies évocatrices selon le lore (région, période, tribu)
- **Chants elfiques** : générer des paroles chantées en Quenya pour une histoire donnée

**Stack envisagée :**
- `Bark` / `XTTS` — TTS multilingue, fine-tunable
- `MusicGen` (Meta) — génération musicale depuis texte
- `AudioCraft` — modèles audio génératifs

---

### 🔜 Phase 7 — Vidéo (Vision long terme)

**Objectif :** Créer des mini-récits visuels animés à partir du lore généré.

**Pipeline envisagé :**
```
Histoire (Phase 3/4)
    ↓
Découpage en scènes (LLM)
    ↓
Image par scène (Phase 5)
    ↓
Animation / transitions (vidéo)
    ↓
Narration vocale en Quenya (Phase 6)
    ↓
Mini-film elfique
```

**Stack envisagée :**
- `Stable Video Diffusion` — image → vidéo courte
- `Sora` / `Runway` — si API disponible
- `MoviePy` — assemblage final

---

## Architecture Globale

```
┌─────────────────────────────────────────────────────────────┐
│              Shared Universe Knowledge Base                  │
│                                                             │
│  FAISS Index (1512 chunks)  +  SQLite (8022 mots)          │
│  + Knowledge Graph (126 entités, 131 relations) ✅          │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌──────────────┐  ┌─────────────────┐
│  Language   │  │     Lore     │  │     Visual      │
│   Engine    │  │    Engine    │  │     Engine      │
│  (Phase 2)  │  │ (Phase 3+4)  │  │   (Phase 5+)   │
└──────┬──────┘  └──────┬───────┘  └────────┬────────┘
       ▼                ▼                    ▼
  Traduction        Histoires            Images
   Quenya          et Culture           Son / Vidéo
```

---

## Structure du projet

```
rag_elven/
├── app.py                      # Interface Streamlit (4 tabs)
├── requirements.txt            # Dépendances
│
├── src/
│   ├── ir.py                   # Layer 1 — spaCy → Semantic IR
│   ├── morphology.py           # Layer 2 — formes Quenya déterministes
│   ├── syntax.py               # Layer 3 — assemblage syntaxique
│   ├── translator.py           # Orchestrateur traduction (Phase 2)
│   ├── lore_generator.py       # Pipeline génération lore (Phase 3)
│   ├── lore_generator_p4.py    # Pipeline Phase 4 (KG validation)
│   ├── knowledge_graph.py      # Knowledge Graph — SQLite + validation déterministe
│   ├── prompt_templates.py     # Templates Claude (Phase 3/4)
│   ├── retrieval.py            # FAISS + SQLite retrieval
│   ├── embeddings.py           # Modèle d'embeddings
│   ├── llm.py                  # LLM Q&A (Groq)
│   ├── query_rewriter.py       # Agent d'analyse d'intention
│   ├── database.py             # SQLite access
│   └── data_loader.py          # Chargement des données
│
├── scripts/
│   └── build_kg.py             # Population du Knowledge Graph (run once)
│
├── vector_db/
│   ├── faiss.index             # Index FAISS (1512 vecteurs)
│   ├── metadata.json           # Metadata des chunks
│   ├── dictionary.sqlite       # Dictionnaire 8022 mots
│   └── knowledge_graph.sqlite  # Knowledge Graph (126 entités, 131 relations)
│
└── data/
    ├── quenya_course/          # Cours Quenya PDF (~80 pages)
    ├── sindarin/               # Ressources Sindarin
    └── lore/                   # Fichiers lore (9 fichiers .txt)
        ├── elves_origin.txt
        ├── sindar.txt
        ├── noldor.txt
        ├── vanyar_teleri.txt
        ├── maiar_sauron.txt
        ├── valar_morgoth.txt
        ├── first_age_wars.txt
        ├── languages_overview.txt
        └── quenya_vs_sindarin.txt
```

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Interface | Streamlit |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Recherche vectorielle | FAISS |
| Dictionnaire | SQLite |
| Knowledge Graph | SQLite (126 entités, 131 relations) |
| NLP parsing | spaCy (`en_core_web_sm`) |
| Q&A LLM | Groq API |
| Génération lore | Claude API (Anthropic) |
| Validation lore Phase 3 | Claude API (2e appel) |
| Validation lore Phase 4 | Déterministe — KG SQLite (0 appel LLM) |
| Déploiement | Streamlit Cloud |

---

## Installation locale

```bash
# Clone
git clone https://github.com/Elmehdi-Moutawakkil/rag_elven.git
cd rag_elven

# Environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Dépendances
pip install -r requirements.txt

# Variables d'environnement
cp .env.example .env
# Remplis .env avec tes clés API :
# GROQ_API_KEY=...
# ANTHROPIC_API_KEY=...  (Phase 3 et 4 — génération uniquement)

# (Optionnel) Reconstruire le Knowledge Graph depuis le corpus
python scripts/build_kg.py
# → Le fichier vector_db/knowledge_graph.sqlite est déjà commité,
#   cette étape n'est nécessaire qu'après modification du corpus lore.

# Lancement
streamlit run app.py
```

---

## Configuration Streamlit Cloud

Dans **Settings → Secrets** de ton app Streamlit Cloud :

```toml
GROQ_API_KEY = "gsk_..."
ANTHROPIC_API_KEY = "sk-ant-..."   # requis pour Phase 3 et 4 (génération uniquement)
```

---

## Auteur

**Elmehdi Moutawakkil** — [elmehdi@moutawakkil.com](mailto:elmehdi@moutawakkil.com)

---

*RAG Elfique — Namárië.*
