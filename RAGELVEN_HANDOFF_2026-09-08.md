# RAGElven — dossier de passation

**Date de référence:** 2026-09-08 (snapshot historique)
**Dépôt:** `/Volumes/ssd1/rag_elven`
**Branche:** `main`
**Commit du snapshot:** `75992c8` (`[phase-1] prepare open source governance`)
**Checkout vérifié le 2026-10-05:** `82b2df0` (`fix: add torchvision for Streamlit semantic retrieval`)
**Portée de ce document:** bootstrap autonome pour un nouveau modèle. Les faits techniques ci-dessous sont vérifiés au snapshot du 2026-09-08, sauf lorsqu’ils sont explicitement marqués comme historiques, optionnels ou non vérifiables. Vérifier le checkout et l’arbre de travail avant toute action.

## TL;DR

RAGElven est un workspace local-first de recherche et de génération de lore. Il combine:

- des corpus versionnés par univers;
- ingestion texte/Markdown par manifestes;
- chunks normalisés, retrieval lexical/hybride et index FAISS;
- Knowledge Graph SQLite avec provenance;
- mémoire générée soumise à validation humaine;
- interface LLM fournisseur-neutre;
- validation des sorties par sources, citations, KG, mémoire et contraintes;
- primitives multimodales metadata-first;
- agent contrôlé et traçable;
- wrappers MCP en lecture/validation;
- fondations d’export de datasets, sans fine-tuning exécuté.

La maturité actuelle est celle d’un **prototype de recherche avec fondations fonctionnelles**. Le chemin Terran est le pilote manifest-driven moderne. Tolkien/Elvish reste principalement un chemin runtime legacy autour de `vector_db/`.

La règle directrice est: **canon, mémoire générée, brouillon et invention ne doivent jamais être confondus**. Aucun contenu généré ne devient canon automatiquement. La validation canonique est humaine et explicite; il n’existe aucune validation canon automatique.

## Objectif et vocabulaire canon

### Objectif produit

Permettre de stocker des univers fictifs comme corpus versionnés, de les rechercher, de générer du contenu nouveau, de vérifier ce contenu contre les sources et le KG, puis d’expérimenter avec des modules interchangeables. Voir [TECHNICAL_SPEC_RAGELVEN.md](TECHNICAL_SPEC_RAGELVEN.md).

### Termes à conserver

- **Canon:** source de référence acceptée pour un univers. Un fichier ou une collection peut être marqué `canon`, `reference`, `review_needed` ou `generated` selon son contrat.
- **Validated memory:** contenu généré réutilisable seulement après citations, absence de contradiction KG forte et transition explicite vers `validated` par un reviewer.
- **Draft / pending / validated / rejected / superseded:** états de mémoire contrôlés, avec historique.
- **Fanon / invention / extrapolation:** contenu généré ou déduit qui n’est pas canon. Il doit rester étiqueté.
- **Universe isolation:** toute requête, index, KG, contrainte et mémoire doit être portée par un `universe_id` effectif.
- **Normal Mode:** le système choisit automatiquement la route, l’univers et les modules nécessaires.
- **Lab Mode:** l’utilisateur compose et inspecte les modules, providers, entrées et sorties intermédiaires.
- **Provenance:** chemin source, document/chunk, citation, modèle, prompt ou trace outil, résultat de validation et timestamp lorsque disponibles.
- **RAG:** retrieval-augmented generation; dans ce dépôt, le retrieval et ses preuves précèdent la génération.
- **KG:** Knowledge Graph; entités, relations, faits, règles et validation de continuité.
- **MCP:** protocole d’exposition d’outils; ce n’est ni un agent ni un fichier d’instructions. Les handlers Python stables précèdent le serveur MCP.
- **Agent:** planificateur/exécuteur contrôlé qui appelle des outils connus et produit une trace. Il n’est pas autonome au sens d’une autorisation d’écriture sans contrôle humain.
- **`.codex/agents/*.toml`:** configuration locale de spécialistes Codex. `.codex/agents.json` est conservé comme référence legacy de compatibilité.

### Décision de sûreté

`UNKNOWN` et `needs_human_review` sont préférables à une affirmation inventée. Une réponse qui ne peut pas être soutenue doit rester explicitement incertaine.

## Histoire et évolution

Les dates suivantes viennent des documents actifs et archivés; elles décrivent l’évolution du projet, pas nécessairement chaque changement Git.

1. Les premières phases ont établi un prototype de Q&A, traduction Quenya, génération de lore et index legacy Tolkien dans `data/` et `vector_db/`.
2. La spécification active du 2026-06-28 a posé l’architecture en couches, Normal/Lab, provenance, isolation et règle de non-canonisation automatique.
3. La structure `corpus/` et les manifestes ont été introduits progressivement. Terran Empire est devenu le pilote de l’ingestion manifest-driven.
4. L’ingestion, les chunks JSONL et le retrieval lexical/hybride Terran ont été stabilisés. Le retrieval Tolkien FAISS legacy a été conservé pour compatibilité.
5. Le KG SQLite a été documenté, exportable en JSON et relié aux contrôles de validation.
6. La mémoire validée a reçu statuts, gates, historique, versioning et rollback.
7. L’abstraction `LLMProvider`, la validation de sorties et les traces d’agent ont été ajoutées.
8. Le support multimodal a été introduit sous forme de contrats metadata-first.
9. Les outils Python stables ont été enveloppés par un serveur MCP optionnel, limité à la lecture et à la validation.
10. La stratégie LoRA/fine-tuning a été explicitement différée jusqu’à disposer de suffisamment d’exemples validés.
11. L’étape 18 a préparé la gouvernance open source sans déclarer le dépôt publiable.
12. Le travail local récent a déplacé le routage Codex vers les agents natifs et les TOML RAGElven, tout en conservant `.codex/agents.json` comme référence legacy.

Documents historiques: [docs/archive/](docs/archive/). Ils donnent du contexte mais ne remplacent pas la spécification active ni ce handoff.

## Architecture actuelle, couche par couche

### 1. Dépôt canonique et manifestes

Les univers sont décrits dans `corpus/universes/<universe_id>/manifest.json` et `SUMMARY.md`.

- `terran_empire`: statut `pilot`; sept sources texte sous `data/universes/terran_empire/lore`.
- `tolkien`: statut `legacy_runtime`; cours Quenya, dictionnaires et notes Tolkien migrées.
- Git versionne les sources; les bases, index et artefacts runtime vivent à côté du corpus selon les contrats historiques.

Les manifestes déclarent les collections, chemins, modalités, politique canonique, index, KG et mémoire. Le runtime conserve encore des chemins `data/` et `vector_db/`; ne pas supposer que la migration vers `corpus/`, `indexes/` et `kg/` est complète.

### 2. Ingestion et normalisation

Points d’entrée: `scripts/ingest_universe.py`, `src/ingestion/documents.py`, `src/ingestion/loaders.py`, `src/ingestion/manifests.py`.

Le flux actuel lit Markdown et texte à partir d’un manifeste, crée des documents normalisés avec identifiant stable, hash, chemin source, univers et statut, puis écrit notamment `storage/processed/terran_empire/documents.jsonl` et son rapport JSON.

Le rapport observé contient sept documents texte Terran. PDF et vidéo ne sont pas des chemins d’ingestion complets actuels. Image et audio peuvent être représentés comme documents metadata-only, sans OCR, transcription, captioning, embedding ou mutation de corpus.

### 3. Chunking, embeddings, retrieval et FAISS

Le pilote Terran produit `indexes/terran_empire/text/chunks.jsonl` et un manifeste d’index. `src/retrieval_adapter.py` est la façade unifiée: elle normalise les hits, ajoute `source_path`, `source_name`, `citation`, scores lexical/sémantique et peut fusionner le chemin FAISS legacy.

Artefacts runtime:

- Tolkien: `vector_db/faiss.index`, `vector_db/metadata.json`, dictionnaire `vector_db/dictionary.sqlite`.
- Terran: `vector_db/terran_empire/faiss.index`, `vector_db/terran_empire/metadata.json` et KG associé.
- Embedding déclaré par les manifestes: `all-MiniLM-L6-v2`.
- Comptages vérifiés par sanity: Tolkien 1490 chunks metadata, Terran 128 metadata chunks, nouvel index texte Terran 90 chunks.
- Le retrieval lexical/hybride normalisé est la voie moderne Terran; FAISS reste disponible pour Tolkien/Elvish et pour les ressources déjà construites.

Risques principaux: dérive metadata/index, index obsolète après changement du corpus, petits corpus difficiles à évaluer, couplage aux anciens chemins `vector_db/`.

### 4. Knowledge Graph

Implémentation: `src/knowledge_graph.py`, `src/kg_tools.py`, builders `scripts/build_kg.py` et `scripts/build_kg_terran.py`.

Les bases SQLite exposent `entities`, `relations` et `canon_facts`. Les outils fournissent lookup d’entités, lookup de relations, recherche de preuves source, validation d’assertions et export JSON.

Comptages vérifiés:

- Tolkien: 126 entités, 131 relations, 12 canon facts.
- Terran Empire: 42 entités, 33 relations, 12 canon facts.

Les records portent `source_file`; les spans précis restent une limite documentée. Les règles regex peuvent produire des faux positifs et ne couvrent pas tout le canon.

### 5. Mémoire validée

Implémentation: `src/memory_store.py`; documentation: [memory/README.md](memory/README.md).

Format courant: `memory/<universe_id>/memory.jsonl`. Les items portent notamment `memory_id`, `universe_id`, `status`, `content`, `sources`, `kg_validation`, `version`, `content_hash`, `validated_at`, `reviewer` et `events`.

Transitions autorisées: `draft -> pending/rejected`, `pending -> validated/rejected/draft`, `validated -> superseded/rejected`, `rejected -> draft`. Seuls les items `validated`, sourcés et sans contradiction KG forte sont réutilisables. Une édition repasse en `draft`; un rollback crée une nouvelle version draft et préserve l’historique.

Le manifeste Terran indique actuellement `memory.enabled: false`; les primitives backend existent mais ne sont pas pleinement exposées dans l’UI.

### 6. Abstraction LLM et génération

`src/llm_provider.py` définit une interface fournisseur-neutre avec implémentations ou compatibilités pour Groq, Anthropic, OpenAI-compatible/local, Ollama aliases et provider statique de test. `src/lore_generator*.py`, `src/prompt_templates.py` et `src/translator.py` consomment les couches de génération ou linguistiques.

Le générateur reçoit idéalement requête, extraits, contraintes KG, contraintes temporelles, mémoire validée, style et provenance. Les appels peuvent produire une trace incluant provider, modèle, durée, usage et coût estimé si les données tarifaires existent. Les clés sont optionnelles pour les validations locales et nécessaires aux appels provider-backed.

### 7. Validation des sorties

`src/output_validation.py` vérifie, selon les options:

- couverture par les hits de sources;
- citations explicites;
- contradictions et continuité KG;
- connaissance de la mémoire validée;
- contraintes déterministes;
- avertissements de style;
- visibilité des sources multimodales.

Les catégories distinguées incluent claims soutenus, claims soutenus non cités, extrapolations et inventions non soutenues. Une sortie acceptable n’est pas automatiquement canonisée.

### 8. Multimodal

`src/multimodal.py`, les loaders et [docs/MULTIMODAL.md](docs/MULTIMODAL.md) définissent des records d’assets, détection de modalité, dérivés planifiés et métadonnées de provenance.

État réel: texte/Markdown opérationnels; image/audio représentables metadata-first. OCR, captioning d’image, transcription audio, description vidéo et embeddings multimodaux sont différés. Les contrats prévoient `storage/raw/`, `storage/processed/`, sidecars et hashes, mais ces traitements ne sont pas une capacité actuelle à annoncer comme active.

### 9. Normal Mode et Lab Mode

`src/normal_mode.py`, `src/router.py`, `src/module_registry.py`, `src/layer_registry.py` et `src/pipeline_executor.py` partagent les contrats de modules.

- Normal Mode résout la tâche et l’univers effectif. Les demandes Terran/Star Trek claires routent vers `terran_empire`; les pipelines non Tolkien excluent les modules dictionnaire/traduction/morphologie/syntaxe Tolkien-only.
- Lab Mode permet de sélectionner et composer les couches, provider et univers, avec sorties intermédiaires inspectables.
- Les deux modes ont encore un défaut connu de cohérence des traces UI. Le backend et les tests existent; l’expérience UI n’est pas une promesse de produit final.

### 10. Agent Codex et MCP

L’agent applicatif dans `src/agent/planner.py` dispose d’un registre limité: `retrieve`, `kg_validate`, `generate`, `validate_output`, `request_confirmation`, `expose_trace`. Chaque outil déclare risque, lecture seule et besoin de confirmation. Les écritures, suppression, canonisation, validation mémoire, publication, commit/push et archivage irréversible sont bloqués en attente de confirmation humaine.

La configuration Codex récente est dans `.codex/config.toml` et `.codex/agents/`:

- `codex-rag-engineer`: ingestion, chunking, index, retrieval, provenance, évaluation et MCP read-only;
- `codex-linguist`: traduction, morphologie, syntaxe et incertitude;
- `codex-lore-expert`: revue lecture seule du canon, KG, continuité et isolation.

`.codex/agents.json` est marqué `3.0-legacy` et `compatibility-only`; il reste utile pour comprendre le manager, l’historien et les frontières d’orchestration.

MCP: `src/mcp_tools.py` expose les handlers stables; `mcp/ragelven_server.py` les enveloppe avec le SDK MCP optionnel. Les outils actuels couvrent univers, lecture document, recherche corpus, entités, relations, assertions et validation de sortie. Le serveur est volontairement read-only/validation-only; les outils d’écriture MCP sont désactivés.

## Univers Tolkien/Elvish et Terran: isolation

### Tolkien / Elvish

Manifest: `corpus/universes/tolkien/manifest.json`. Le runtime actif FAISS pointe vers `data/quenya_course/Quenya-Elvish-Language-Course-Tolkien.pdf`; le dictionnaire SQLite compte 8022 entrées. Les notes `corpus/universes/tolkien/canon/*.txt` sont conservées comme `review_needed` et ne sont pas actuellement dans le FAISS actif. Les PDF dictionnaire sont référencés par le manifeste, mais leur présence dans l’index actif doit être vérifiée avant de l’affirmer.

### Terran Empire

Manifest: `corpus/universes/terran_empire/manifest.json`. Sept sources lore texte sous `data/universes/terran_empire/lore`, index FAISS dédié, chunks normalisés et KG dédié. Le manifest est un pilote; le runtime continue de lire les chemins `data/` et `vector_db/`.

### Garde-fous

Le `universe_id` doit être propagé à retrieval, KG, mémoire, contraintes et prompt. Les tests de régression couvrent notamment l’absence de biais Tolkien dans les contraintes Terran et l’exclusion des modules Tolkien-only. Ne jamais fusionner index, KG ou mémoire entre univers sans contrat explicite et tests d’isolation.

## Open source

Le dépôt n’est pas prêt à publier. Les blockers documentés dans [docs/OPEN_SOURCE_READINESS.md](docs/OPEN_SOURCE_READINESS.md) sont:

- licence absente/non choisie;
- droits de redistribution à examiner pour PDF, corpus et index;
- séparation public/privé ou licence incertaine;
- GitHub Actions à ajouter/tester lorsque le token aura le scope `workflow`;
- processus public de contribution et de sécurité à finaliser.

Le code d’audit existe dans `scripts/open_source_audit.py`, mais son résultat ne doit pas être assimilé à une autorisation de publication.

## Inventaire des fichiers et répertoires

### Entrées principales

- `app.py`: application/UI actuelle.
- `src/`: logique de domaine et contrats; notamment `router.py`, `normal_mode.py`, `pipeline_executor.py`, `retrieval*.py`, `knowledge_graph.py`, `memory_store.py`, `llm_provider.py`, `output_validation.py`, `multimodal.py`.
- `src/ingestion/`, `src/indexing/`, `src/agent/`: ingestion, indexation et agent.
- `scripts/`: ingestion, construction d’index/KG, audit open source et sanity check.
- `tests/`: 20 fichiers de tests couvrant retrieval, ingestion, KG, mémoire, LLM, MCP, normal mode, multimodal, validation et régressions.
- `corpus/`: manifestes et notes par univers.
- `data/`: sources runtime historiques et pilote Terran.
- `vector_db/`: index FAISS et SQLite legacy/actuels.
- `indexes/`: chunks JSONL et manifeste du nouvel index Terran.
- `storage/processed/`: documents normalisés et rapport Terran.
- `kg/`: exports JSON lisibles des KG.
- `memory/`: contrat et emplacement de mémoire validée.
- `prompts/`: profils d’agents et templates de workflow.
- `mcp/`: serveur MCP optionnel.
- `inspector/`: base et outils d’inspection/évaluation locaux.
- `docs/`: architecture, répertoire documentaire, KG, multimodal, agents, fine-tuning et readiness open source.
- `.codex/`: instructions, configuration et spécialistes Codex RAGElven.

### Artefacts vérifiés

- `vector_db/faiss.index`, `vector_db/metadata.json`, `vector_db/dictionary.sqlite`, `vector_db/knowledge_graph.sqlite`;
- `vector_db/terran_empire/faiss.index`, `metadata.json`, `knowledge_graph.sqlite`;
- `indexes/terran_empire/text/chunks.jsonl` et `manifest.json`;
- `storage/processed/terran_empire/documents.jsonl` et `ingestion_report.json`;
- `kg/tolkien/export.json` et `kg/terran_empire/export.json`.

## État Git historique au 2026-09-08

Au moment du snapshot, `main` était alignée avec `origin/main` et `HEAD` valait `75992c8`. Aucun commit ni push n’avait été effectué pour cette passation. Cet état ne décrit pas le checkout courant : le 2026-10-05, `HEAD` a été vérifié à `82b2df0`.

Changements locaux à préserver au moment du snapshot:

- modifié: `.codex/agents.json`;
- modifié: `.codex/cost-models.json`;
- modifié: `.codex/instructions.md`;
- modifié: `README.md`;
- modifié: `docs/PIPELINE1_STATUS.md`;
- nouveau non suivi: `.codex/agents/`;
- nouveau non suivi: `.codex/config.toml`.

Le fichier de passation lui-même était une nouvelle documentation autorisée par la mission. Ne réinitialiser, nettoyer ou écraser aucun changement local courant sans demande explicite.

## Acquis vérifiés

- Sanity Manager demandé: `.venv/bin/python scripts/sanity_check.py` réussi.
- Résultat de référence communiqué par le Manager: `213 passed, 7 subtests passed in 10.39s` avec `.venv/bin/python -m pytest -q`.
- Rerun effectué pendant cette passation avec la même commande: `213 passed, 7 subtests passed in 6.43s`.
- Le sanity check a confirmé Python `3.13.2`, syntaxe sans erreur, assets FAISS/SQLite présents, dictionnaire 8022 entrées, KG Tolkien 126 entités, KG Terran 42 entités, metadata Tolkien 1490 chunks, Terran 128 chunks, manifestes 2, documents traités 7 et index texte 90 chunks.
- Le sanity check signale la présence de variables `GROQ_API_KEY` et `ANTHROPIC_API_KEY`; il ne donne jamais leurs valeurs. Ne jamais lire, copier ou exposer ces valeurs.
- Les imports attendus, dont Streamlit, FAISS, sentence-transformers, providers, spaCy, pypdf, pytest et dépendances associées, sont disponibles dans `.venv` au moment de la vérification.

## Limites, prototypes et contradictions à surveiller

- La documentation parle parfois de “done” pour les étapes 10 à 18, mais `docs/PIPELINE1_STATUS.md` précise qu’il s’agit de fondations/prototypes/backend slices, pas d’un produit public fini.
- Le manifest Terran déclare la mémoire désactivée, alors que les primitives de mémoire sont testées et opérationnelles en backend.
- Les chemins cibles `corpus/`, `indexes/`, `kg/` coexistent avec les chemins runtime `data/`, `vector_db/`; ne pas conclure à une migration complète.
- Le manifest Tolkien référence plusieurs sources, tandis que la metadata FAISS active est centrée sur le PDF du cours Quenya.
- Les comptes de chunks diffèrent selon l’artefact: 1490 Tolkien et 128 Terran dans metadata FAISS, 90 dans le nouvel index texte Terran. Ils ne désignent pas le même pipeline.
- La couverture retrieval et les source spans précis restent insuffisants pour une évaluation forte.
- Le KG s’appuie encore sur des règles déterministes/regex et une provenance fichier, non toujours sur un extrait précis.
- L’UI n’expose pas complètement la mémoire validée et les traces Normal/Lab ne sont pas parfaitement cohérentes.
- Il n’existe pas de table durable `agent_runs` ni de telemetry durable complète budget/tool runs.
- Les outils MCP write, la canonisation automatique et l’auto-approbation sont absents par choix de sûreté.
- OCR, captioning, transcription, vidéo, embeddings multimodaux et fine-tuning ne sont pas implémentés.
- Le projet ne fournit pas encore les garanties de production: authentification, déploiement WSGI/reverse proxy, TLS, sauvegardes, isolation serveur et durcissement public doivent être traités séparément.

## Dette et risques

1. Décider licence et droits corpus/index avant toute publication.
2. Ajouter secret scan et CI publique après clarification des permissions.
3. Élargir les jeux d’évaluation retrieval et mesurer recall/source-span precision.
4. Formaliser la cohérence des traces et la confirmation UI.
5. Ajouter des logs durables pour runs agent, outils et validations.
6. Réduire la dérive entre manifestes, chemins runtime, metadata FAISS et chunks JSONL.
7. Renforcer les spans de provenance et les règles KG sans confondre heuristique et preuve.
8. Connecter la mémoire validée à l’UI avec revue humaine explicite.
9. Contrôler taille, droits et redistribution des PDF, corpus et index.

## Priorités recommandées

### P0 — préserver la confiance

- Ne pas auto-canoniser, auto-valider ou activer des write tools.
- Maintenir l’isolation par `universe_id`.
- Conserver la provenance et les statuts de mémoire.
- Rejouer sanity et tests avec `.venv`, jamais avec le Python système comme référence du projet.

### P1 — rendre le pilote mesurable

- Stabiliser le contrat retrieval Terran et ses évaluations.
- Ajouter des source spans précis et détecter les index périmés.
- Aligner manifestes, chemins et artefacts sans casser le runtime legacy.

### P2 — améliorer l’usage contrôlé

- Unifier les traces Normal/Lab.
- Ajouter l’UI de mémoire validée et la confirmation humaine.
- Ajouter des logs agent/tool durables.

### P3 — seulement après données propres

- Étudier OCR/transcription/captioning multimodal.
- Produire des datasets uniquement depuis mémoire réutilisable `validated`.
- Reconsidérer LoRA/fine-tuning quand les exemples validés sont assez nombreux et mesurés.

## Commandes de setup, run, test et audit

Depuis `/Volumes/ssd1/rag_elven`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Vérifications de référence du projet
.venv/bin/python scripts/sanity_check.py
.venv/bin/python -m pytest -q
git diff --check

# Flux de données documenté
make ingest-terran
make index-terran
make run
```

Commandes ciblées utiles:

```bash
.venv/bin/python scripts/open_source_audit.py --strict
.venv/bin/python scripts/build_kg_terran.py
.venv/bin/python scripts/export_kg.py
```

Vérifier les cibles réelles du `Makefile` avant d’exécuter une variante. Les providers externes ne sont pas nécessaires pour les tests locaux, mais les appels provider-backed exigent une configuration locale. Les valeurs de secrets restent hors de tout rapport.

## Protocole conseillé au prochain modèle

1. Lire ce fichier, `README.md`, `TECHNICAL_SPEC_RAGELVEN.md` et `docs/PIPELINE1_STATUS.md`.
2. Vérifier `git status --short --branch` et préserver tous les changements locaux listés plus haut.
3. Lire le manifeste de l’univers visé et son `SUMMARY.md` avant les chunks détaillés.
4. Identifier si la question est Normal ou Lab, puis résoudre explicitement `universe_id`.
5. Utiliser la façade de retrieval et conserver les citations/source paths dans toute sortie intermédiaire.
6. Consulter le KG avant d’accepter une relation, un événement ou une continuité.
7. Traiter toute génération comme draft; appeler la validation des sorties.
8. Ne mettre en mémoire que sous les transitions prévues; ne jamais transformer un draft en canon.
9. Pour une demande d’écriture, publication, canonisation, suppression, commit ou push, demander confirmation humaine et rester bloqué avant l’action.
10. Pour un changement de code ou de comportement, exécuter les tests ciblés puis les deux commandes de référence avec `.venv`.
11. Pour une modification d’architecture, consulter d’abord les contrats actifs et les documents de dette; éviter une migration globale des chemins sans preuve.
12. Avant de conclure, distinguer systématiquement faits vérifiés, hypothèses, prototypes et inconnues.

## Décisions à ne pas casser

- Generated content is not canon until human validation.
- Provenance is mandatory for durable outputs.
- Canon, generated memory, raw assets, indexes and runtime caches remain separate.
- `universe_id` isolation is a cross-cutting invariant.
- Retrieval evidence precedes generation quality.
- Normal and Lab must share explicit, testable module contracts.
- Provider-backed and local models use the same high-level abstraction.
- Missing keys must degrade gracefully where possible.
- MCP wraps stable internal Python tools; it is not a shortcut around contracts.
- Risky write/canonization/publishing actions require human confirmation.
- Fine-tuning waits for enough reusable validated examples.
- No API key may be committed or exposed.
- Do not use system Python as evidence against the verified `.venv` result.

## Contexte récent: Mem0 et Obsidian

Mem0 et Obsidian sont des **options de contexte récentes, non implémentées dans RAGElven**.

- Aucun module Mem0 actif, aucune dépendance intégrée et aucun flux de synchronisation Mem0 ne doit être annoncé comme présent.
- Aucun export Obsidian intégré, aucune synchronisation bidirectionnelle et aucun plugin Obsidian ne sont présents dans ce dépôt.
- Ces options peuvent être étudiées plus tard comme couche d’interface ou d’export autour de la mémoire validée, mais elles ne doivent pas devenir une nouvelle source canonique sans contrat de provenance, versioning, isolation par univers et revue humaine.
- La mémoire native actuelle reste `memory/<universe_id>/memory.jsonl` avec les statuts et l’historique décrits plus haut.

## Sources principales

- [TECHNICAL_SPEC_RAGELVEN.md](TECHNICAL_SPEC_RAGELVEN.md)
- [README.md](README.md)
- [docs/PIPELINE1_STATUS.md](docs/PIPELINE1_STATUS.md)
- [docs/DOCUMENT_REPERTORY.md](docs/DOCUMENT_REPERTORY.md)
- [docs/KNOWLEDGE_GRAPH.md](docs/KNOWLEDGE_GRAPH.md)
- [docs/AGENT_ORCHESTRATION.md](docs/AGENT_ORCHESTRATION.md)
- [docs/MULTIMODAL.md](docs/MULTIMODAL.md)
- [docs/FINE_TUNING_STRATEGY.md](docs/FINE_TUNING_STRATEGY.md)
- [docs/OPEN_SOURCE_READINESS.md](docs/OPEN_SOURCE_READINESS.md)
- [memory/README.md](memory/README.md)
- [mcp/README.md](mcp/README.md)
- [src/retrieval_adapter.py](src/retrieval_adapter.py)
- [src/knowledge_graph.py](src/knowledge_graph.py)
- [src/memory_store.py](src/memory_store.py)
- [src/output_validation.py](src/output_validation.py)
- [src/agent/planner.py](src/agent/planner.py)
- [src/mcp_tools.py](src/mcp_tools.py)
- [scripts/sanity_check.py](scripts/sanity_check.py)
