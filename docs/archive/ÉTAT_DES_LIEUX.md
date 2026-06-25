# État des lieux — Elmehdi Fiction
**Dernière mise à jour :** 2026-06-11  
**Repo :** [github.com/Elmehdi-Moutawakkil/rag_elven](https://github.com/Elmehdi-Moutawakkil/rag_elven)  
**App live :** [ragelven.streamlit.app](https://ragelven.streamlit.app)  
**Projet local :** `/Users/emm/Projets/RAGElven/`

> Note de maintenance, 2026-06-25 :
> ce fichier est un snapshot d'audit, pas une documentation active. Il reste
> utile pour comprendre l'état du projet au 2026-06-11, mais certains détails
> ont changé depuis : le projet local principal est `/Volumes/ssd1/rag_elven`,
> la configuration est centralisée dans `src/settings.py`, L09 valide via le
> Knowledge Graph local, et le modèle Anthropic lore par défaut est
> `claude-sonnet-4-6`.

---

## 1. Vision du projet

**Elmehdi Fiction** est une plateforme d'exploration de lore fictif basée sur une architecture RAG (Retrieval-Augmented Generation) modulaire. L'ambition est de pouvoir ajouter n'importe quel univers fictif (Tolkien, Star Trek, Dune, Witcher, Star Wars…) en fournissant simplement un corpus de lore et un index vectoriel. Les requêtes passent par un pipeline de layers atomiques composables.

**Philosophie :** tester les limites des LLMs sur du lore fictif — notamment leur capacité à gérer un lore pauvre (Empire Terran, 128 chunks intentionnellement faible) vs un lore riche (Elfique, 1490 chunks + dictionnaire 8022 mots).

---

## 2. Architecture générale

```
Requête utilisateur
        ↓
[Routeur — src/router.py]
  Fast-path règles → route détectée
  LLM fallback    → si ambigu
        ↓
Pipeline de layers exécuté
        ↓
Réponse + trace des layers

─────────── Univers disponibles ───────────
🧝 Elfique (Tolkien)        → FAISS 1490 vectors + SQLite 8022 mots
🖖 Empire Terran (Trek)     → FAISS 128 vectors

─────────── Modes d'interface ─────────────
Interface unifiée   → routeur automatique
Mode manuel         → accès direct aux pipelines + tooltip layers
Lab Mode            → composition libre des layers + sélecteur d'univers
```

---

## 3. Stack technique

| Composant | Technologie |
|-----------|-------------|
| Interface | Streamlit |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| Recherche vectorielle | FAISS (faiss-cpu) |
| Dictionnaire Quenya | SQLite (8 022 entrées, source : Fauskanger 152p) |
| Knowledge Graph | SQLite (schéma entities/relations/canon_facts) |
| LLM Q&A | Groq — `llama-3.1-8b-instant` |
| LLM Génération lore | Claude Sonnet (`claude-sonnet-4-6` par défaut actuel) |
| LLM Polish traduction | Claude Haiku (`claude-haiku-4-5-20251001`) |
| NLP parsing | spaCy `en_core_web_sm` |
| Variables d'env | `.env` local / Streamlit Cloud Secrets |

---

## 4. Layers atomiques (L01 → L13)

| Layer | Fonction | Universel ? |
|-------|----------|-------------|
| L01 | Query Rewriter | ✅ |
| L02 | FAISS Semantic Search | ✅ (index par univers) |
| L03 | SQLite Dictionary | ❌ Elfique uniquement |
| L04 | spaCy NLP Parser | ❌ Elfique uniquement |
| L05 | Morphologie Quenya | ❌ Elfique uniquement |
| L06 | Syntax SOV | ❌ Elfique uniquement |
| L07 | Constraint Builder | ✅ |
| L08 | Story Generation | ✅ (universe-aware depuis fix) |
| L09 | KG Validator | ✅ (optionnel selon univers) |
| L10 | Image Search | 🔲 Phase future |
| L11 | Image Generation | 🔲 Phase future |
| L12 | TTS | 🔲 Phase future |
| L13 | Answer LLM | ✅ |

---

## 5. Univers disponibles

### 🧝 Elfique (Tolkien)

| Donnée | Valeur |
|--------|--------|
| Corpus lore | `data/lore/` — cours Quenya/Sindarin + lore Tolkien |
| FAISS index | `vector_db/faiss.index` — **1 490 vectors** |
| Dictionnaire | `vector_db/dictionary.sqlite` — **8 022 entrées** |
| Knowledge Graph | `vector_db/knowledge_graph.sqlite` — **126 entités, 131 relations** |
| Features | Q&A, Traduction Quenya (EN→QY), Génération Lore |

**Pipeline Traduction Quenya (4 layers) :**
1. spaCy → parse EN → SemanticIR
2. Morphologie déterministe (80+ règles) → formes Quenya
3. Syntax SOV → assemblage déterministe
4. Claude Haiku → polish stylistique (valide que les formes pré-calculées sont préservées)

### 🖖 Empire Terran (Star Trek Mirror Universe)

| Donnée | Valeur |
|--------|--------|
| Corpus lore | `data/universes/terran_empire/lore/` — 7 fichiers canon épisodique (TOS, DS9, ENT) |
| FAISS index | `vector_db/terran_empire/faiss.index` — **128 vectors** (intentionnellement faible) |
| Knowledge Graph | `vector_db/terran_empire/knowledge_graph.sqlite` — **42 entités, 33 relations, 11 règles canon** |
| Features | Q&A, Génération Lore |
| Pas de traduction | Aucune langue fictive canonique |

**Note intentionnelle :** le corpus Terran est volontairement pauvre (128 chunks vs 1490 pour Tolkien) pour tester la capacité du modèle à gérer un lore faible — stress test de l'hallucination.

---

## 6. Inspector Agent — système de monitoring automatique

Système de test et surveillance automatique construit le 2026-06-11, installé dans `inspector/`.

### Architecture

```
Cron (01h, 07h, 13h, 19h)
        ↓
run_tests.py — sélectionne des questions inédites par feature
        ↓
app_bridge.py — appels directs aux modules Python (bypass Streamlit)
        ↓
evaluator.py — Claude Sonnet juge la réponse
  + DuckDuckGo web search pour vérification ground-truth
        ↓
db.py — sauvegarde dans inspector.db (SQLite)
        ↓
reporter.py
  → Rapport journalier (08h00) → inspector/reports/daily_*.md
  → Rapport hebdo tendances (dimanche 08h30) → inspector/reports/weekly_*.md
```

### Fichiers

| Fichier | Rôle |
|---------|------|
| `inspector/config.py` | Registre des features — **ajouter un univers = 5 lignes** |
| `inspector/question_bank.py` | 60+ questions avec ground truth (5 features) |
| `inspector/app_bridge.py` | Appels directs aux modules Python |
| `inspector/evaluator.py` | Juge Claude + web search DuckDuckGo |
| `inspector/db.py` | SQLite historique + anti-répétition 30 jours |
| `inspector/reporter.py` | Génération rapports MD |
| `inspector/run_tests.py` | Runner principal |
| `inspector/setup_cron.sh` | Setup cron automatique |

### Verdicts possibles
- `CORRECT` — réponse factuellement juste (score 0.85–1.0)
- `PARTIAL` — partiellement correct, manque des faits clés (0.4–0.84)
- `HALLUCINATION` — contient des informations fausses (0.0–0.3)
- `IRRELEVANT` — n'adresse pas la question (0.1–0.3)
- `ERROR` — erreur technique de l'app

### Seuils d'alerte
- Taux de correction < 70% → 🟠 ATTENTION
- Taux d'hallucination > 25% → 🔴 DÉGRADÉ

### Commandes utiles
```bash
# Lancer des tests manuellement
python -m inspector.run_tests --n 24

# Rapport journalier immédiat
python -m inspector.run_tests --report

# Rapport hebdo immédiat
python -m inspector.run_tests --weekly

# Tester une feature spécifique
python -m inspector.run_tests --feature qa_elvish
```

---

## 7. Bugs corrigés (session 2026-06-11)

### Fix 1 — Traduction Quenya : hallucinations `Qelionar`
**Problème :** le LLM polish (Groq llama-3.1-8b) ignorait les instructions de format et générait du charabia (`Qelionar Quenya`) au lieu de polir la traduction déterministe.

**Fix :**
- Bascule du polish de **Groq → Claude Haiku** (bien meilleure compréhension des langues tolkieniennes)
- Ajout d'une validation : si l'output LLM ne contient aucun mot des formes pré-calculées, on rejette et on garde l'assemblage déterministe
- Température réduite de 0.4 → 0.1

**Fichier :** `src/translator.py`

### Fix 2 — Q&A : refus de répondre hors-contexte FAISS
**Problème :** le prompt disait `Answer using ONLY the context` — le modèle refusait de répondre quand la question dépassait l'index FAISS (ex: Silmarils, Rings of Power).

**Fix :** le modèle peut maintenant utiliser ses connaissances générales en signalant `(general knowledge)` — le refus est interdit.

**Fichier :** `src/llm.py`

### Fix 3 — Génération Lore : ignore les entités nommées du prompt
**Problème :** `generate_story()` reconstruisait sa propre requête depuis `context['species']`/`location` en ignorant la demande originale. "Invente un Noldor" → générait des Sindar.

**Fix :**
- Extraction des entités nommées du prompt utilisateur (Noldor, Galadriel, Eregion…)
- Injection comme contraintes dures : `"MANDATORY — these elements MUST appear: Noldor, Galadriel"`
- Utilisation du `raw_request` directement au lieu de le reconstruire

**Fichier :** `src/lore_generator.py`

---

## 8. Résultats des premiers tests inspector (run propre, 2026-06-11)

*(Basé sur les runs avec clés API valides — hors erreurs techniques dues aux clés expirées)*

| Feature | Corrects | Hallucinations | Score moy. | Statut |
|---------|----------|----------------|------------|--------|
| Q&A Elfique | ~25% | 0% | 0.45 | 🟠 Réponses trop courtes |
| Traduction Quenya | 0% | 66% | 0.03 | 🔴 Bug pycache → fixé |
| Génération Lore Tolkien | ~60% | 0% | 0.55 | 🟡 Amélioré par Fix 3 |
| Q&A Terran | ~25% | 12% | 0.30 | 🟠 Corpus trop faible (intentionnel) |
| Génération Lore Terran | 75% | 0% | 0.80 | 🟢 Meilleure feature |

**Hallucination récurrente identifiée :** le Q&A Terran a inversé l'événement Kirk/Mirror Universe (raconté à l'envers). Origine : chunk insuffisant dans l'index 128 vectors.

---

## 9. État du code — commits récents

```
f98008c  feat(terran_empire): KG 42 entités, 33 relations, 11 canon facts
956424d  feat(inspector): inspector agent + 3 bug fixes
4a42faa  fix(L08): story generation universe-aware
3388734  fix(L09): pass api_key to validate_coherence()
6779ede  feat(lab): universe selector Lab Mode
f26303f  feat(terran_empire): lore generation tab
f0daf71  feat: Empire Terran universe + FAISS index
dd1f7c3  feat: rebrand → Elmehdi Fiction
```

---

## 10. Roadmap — prochaines étapes

### Priorité haute
- [ ] **Nettoyage dictionnaire Quenya** — corriger les POS tags corrompus (`linda-` stocké `noun` au lieu de `vb.`). Les mots pour "sing" existent (`liria`, `linna`, `lir-`) mais le moteur morphologique les rate à cause des tags. C'est un fix SQLite, pas un ajout de mots.
- [ ] **Laisser tourner l'inspector 7 jours** avant d'agir sur les métriques — avoir une baseline hebdo propre.

### Priorité moyenne
- [ ] **KG Tolkien → brancher dans la validation Terran** — le KG Tolkien existe (126 entités) mais `lore_generator_generic.py` ne le consomme pas encore pour la validation post-génération. (Le KG Terran, lui, est branché.)
- [ ] **Routeur principal** — reconnaître les requêtes Empire Terran et ne pas les router vers les pipelines Elfique. Actuellement le routeur n'a pas de règles pour l'univers Mirror.
- [ ] **Enrichir le corpus Terran** — si le test du lore faible est concluant, ajouter des épisodes TOS mirror (Mirror Mirror) et ENT (In a Mirror, Darkly) pour monter à ~300-400 chunks.

### Phase 4 — Multimédia (futur)
- [ ] **L10 Image Search** — CLIP pour recherche d'images par similarité sémantique
- [ ] **L11 Image Generation** — Stable Diffusion / DALL-E pour illustrer le lore généré
- [ ] **L12 TTS** — Text-to-Speech (Quenya ou autre)

### Nouveaux univers (futur)
Guide d'ajout : `add_universe_pipeline.md` (Downloads) — 6 étapes pour tout nouvel univers.
Candidats : Dune, Star Wars, Witcher, Game of Thrones.

---

## 11. Infrastructure de monitoring

### Cron actif (machine locale)
```
01h, 07h, 13h, 19h  → tests automatiques → logs/tests.log
08h00 quotidien      → rapport journalier → reports/daily_YYYYMMDD_HHMM.md
08h30 dimanche       → rapport hebdo      → reports/weekly_YYYYMMDD_HHMM.md
```

### Supprimer le cron
```bash
crontab -l | grep -v elmehdi-fiction-inspector | crontab -
```

### Réinstaller le cron
```bash
bash inspector/setup_cron.sh
```

---

## 12. Clés API en place

| Service | Utilisation | Fichier |
|---------|-------------|---------|
| Groq | Q&A (llama-3.1-8b-instant) | `.env` → `GROQ_API_KEY` |
| Anthropic | Lore gen (Sonnet) + Polish traduction (Haiku) + Juge inspector (Sonnet) | `.env` → `ANTHROPIC_API_KEY` |

**Note :** les clés Streamlit Cloud sont dans les Settings → Secrets de l'app (séparées du `.env` local).

---

## 13. Points de vigilance connus

1. **Traduction Quenya confidence = LOW systématique** — normal : le dictionnaire couvre ~95% du lexique attesté mais les verbes rares manquent de conjugaisons. Améliorer = enrichir les règles morphologiques dans `src/morphology.py`.

2. **Q&A trop court** — Groq `llama-3.1-8b-instant` répond avec 1-2 phrases là où 4-5 seraient utiles. Augmenter `MAX_TOKENS` dans `src/llm.py` (actuellement 1024) ou changer le prompt pour exiger plus de détails.

3. **Inspector agrège toute la journée** — le rapport journalier inclut TOUS les runs des 24h. Les erreurs d'une session (ex : clés expirées) polluent les stats. Solution future : filtrer par `run_id` ou ajouter un flag "valid run".

4. **Le cron tourne uniquement si le Mac est allumé** — pas de monitoring cloud. Si la machine dort, le run est skippé (cron ne rattrape pas les runs manqués).

---

*Document généré le 2026-06-11 — Elmehdi Fiction Inspector*
