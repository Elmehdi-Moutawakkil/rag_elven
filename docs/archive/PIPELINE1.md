# Pipeline de transformation du projet RAGElven

Ce document formalise un plan de travail progressif pour transformer l'application actuelle en une plateforme modulaire, open source, robuste, compatible avec une architecture RAG / Knowledge Graph / agents / MCP, tout en gardant un mode normal simple et un mode laboratoire avancé.

L'objectif n'est pas de tout refaire brutalement. L'objectif est d'assainir, stabiliser, puis faire évoluer le projet par couches successives, chaque étape devant produire un état utilisable.

## Vision cible

Le projet doit devenir une application capable de gérer des univers documentaires complexes.

Elle doit pouvoir :

- stocker et versionner des corpus de lore, documents, notes, images, sons et métadonnées ;
- ingérer ces ressources dans un format exploitable ;
- indexer les contenus pour la recherche sémantique ;
- structurer les connaissances sous forme de graphe ;
- générer du texte cohérent à partir du corpus ;
- valider les générations contre les sources et les règles du monde ;
- permettre une exécution simple pour l'utilisateur normal ;
- permettre une composition libre des modules en mode laboratoire ;
- rester extensible par des modules locaux, des modèles locaux ou distants, et plus tard des MCP ;
- être publiable en open source sans dépendre d'un fournisseur unique.

## Principe général

Le bon ordre de travail est :

1. Auditer et nettoyer le projet existant.
2. Stabiliser les modules actuels.
3. Clarifier l'architecture cible.
4. Créer un coeur modulaire propre.
5. Rebrancher les fonctionnalités existantes sur ce coeur.
6. Ajouter ingestion, indexation, graphe, génération, validation.
7. Ajouter multimodal progressivement.
8. Ajouter le mode normal et le mode laboratoire.
9. Ajouter les idées utiles du template IA.
10. Ajouter les MCP seulement quand les modules internes sont stables.
11. Documenter, tester, packager, ouvrir le projet proprement.

## Etape 1 - Audit complet du projet existant

But :

Comprendre ce qui existe vraiment, ce qui marche, ce qui est fragile, ce qui est obsolète, et ce qui vient d'une ancienne architecture.

Actions :

- lire l'arborescence complète du projet ;
- identifier frontend, backend, scripts, données, index, modèles, tests ;
- lire les fichiers de configuration ;
- repérer les dépendances ;
- lancer les tests existants ;
- lancer l'application ;
- tester manuellement les fonctions principales ;
- repérer les modules cassés ou fictifs ;
- repérer les fichiers morts ;
- vérifier les clés API, variables d'environnement et secrets ;
- identifier les traces de code généré ou incohérent.

Prompt que tu pourrais me donner :

```text
Analyse entièrement le projet RAGElven. Lis l'arborescence, les fichiers de configuration, le backend, le frontend, les modules, les scripts et les tests. Fais-moi un audit technique complet : ce qui marche, ce qui est cassé, ce qui est inutile, ce qui est dangereux, ce qui est obsolète, et ce qui doit être priorisé. Ne modifie rien au début, commence par comprendre.
```

Comment je l'appliquerais :

- je commencerais par `rg --files`, `git status`, les fichiers de config et les README ;
- je cartographierais les routes, composants, modules et services ;
- je lancerais les tests ou l'application si possible ;
- je produirais une liste de constats classés par gravité ;
- je ne supprimerais rien sans avoir compris son rôle.

Livrable :

- un audit clair ;
- une liste de fichiers à conserver ;
- une liste de fichiers à nettoyer ;
- une liste de risques ;
- une première roadmap technique.

## Etape 2 - Nettoyage et sécurisation

But :

Retirer les éléments inutiles ou dangereux sans casser l'application.

Actions :

- retirer les clés API du code et de l'historique visible ;
- vérifier `.env`, `.env.example`, `.gitignore` ;
- supprimer ou archiver les prototypes morts ;
- renommer les modules ambigus ;
- supprimer les objets hérités de l'ancien design s'ils ne servent plus ;
- garder une compatibilité minimale avec les fonctions qui marchent ;
- rendre les erreurs plus lisibles ;
- clarifier les dépendances.

Prompt :

```text
Nettoie le projet sans refactor massif. Retire les éléments morts ou dangereux, sécurise les secrets, clarifie les variables d'environnement, corrige les erreurs évidentes, mais ne change pas encore l'architecture profonde. Chaque suppression doit être justifiée.
```

Comment je l'appliquerais :

- je ferais des changements courts et vérifiables ;
- je testerais après chaque groupe de modifications ;
- je documenterais les variables nécessaires ;
- je garderais les suppressions dans un commit séparé.

Livrable :

- code plus propre ;
- secrets mieux protégés ;
- documentation minimale d'installation ;
- application encore lançable.

## Etape 3 - Stabilisation des modules existants

But :

Savoir quels modules fonctionnent réellement et lesquels doivent être réécrits.

Modules à vérifier :

- query rewriter ;
- recherche FAISS ou équivalent ;
- dictionnaire SQLite ;
- parser NLP ;
- moteur morphologique ;
- assembleur syntaxique ;
- builder de contraintes ;
- génération de lore ;
- validation KG ;
- modules image, audio ou multimodaux s'ils existent.

Prompt :

```text
Teste chaque module existant indépendamment. Pour chaque module, indique son entrée, sa sortie, ses dépendances, son état réel, ses limites, et écris ou corrige un test minimal. Le but est de savoir ce qui est fiable avant de construire dessus.
```

Comment je l'appliquerais :

- je définirais un contrat simple par module ;
- je créerais des exemples d'entrée/sortie ;
- je mettrais les modules non fonctionnels en statut expérimental ;
- je séparerais ce qui est production, lab, futur ou obsolète.

Livrable :

- matrice d'état des modules ;
- tests minimaux ;
- modules cassés isolés ;
- base saine pour le mode laboratoire.

## Etape 4 - Définition de l'architecture cible

But :

Traduire la vision du slide en architecture logicielle réelle.

Architecture cible :

1. Couche dépôt documentaire Git.
2. Couche ingestion.
3. Couche indexation.
4. Couche Knowledge Graph.
5. Couche mémoire validée.
6. Couche agent IA.
7. Couche outils / modules / MCP.
8. Couche génération.
9. Couche validation.
10. Couche sécurité, gouvernance et traçabilité.

Point important :

Git remplace mieux Zotero pour ton cas open source, car Git apporte versionnement, branches, historique, diff, contribution, reproductibilité et transparence.

Zotero peut rester une inspiration ou un connecteur futur, mais il ne doit pas être le coeur de l'architecture.

Prompt :

```text
Transforme l'architecture conceptuelle du projet en architecture technique concrète. Définis les couches, les responsabilités, les interfaces entre couches, les types de données échangées, et ce qui doit rester modulaire. Le projet doit rester open source, local-first autant que possible, et compatible avec modèles locaux ou API.
```

Comment je l'appliquerais :

- je créerais un document `ARCHITECTURE.md` ;
- je définirais les contrats entre couches ;
- je séparerais stockage, retrieval, génération et validation ;
- je m'assurerais que le mode lab manipule les mêmes briques que le mode normal.

Livrable :

- architecture écrite ;
- frontières claires ;
- vocabulaire stable ;
- base pour le refactor.

## Etape 5 - Création du coeur modulaire

But :

Faire des modules de vrais composants composables, pas seulement des boutons dans l'interface.

Chaque module doit avoir :

- un identifiant stable ;
- un nom ;
- une description ;
- un statut ;
- des entrées typées ;
- des sorties typées ;
- des dépendances ;
- une fonction d'exécution ;
- des erreurs propres ;
- des métadonnées ;
- éventuellement un coût estimé ;
- éventuellement un niveau de confiance.

Prompt :

```text
Crée un système de modules propre. Chaque module doit déclarer son contrat d'entrée, son contrat de sortie, ses dépendances, son statut, et une fonction d'exécution. Le mode normal et le mode laboratoire devront utiliser ce même registre de modules.
```

Comment je l'appliquerais :

- je créerais un registre central de modules ;
- je définirais un type commun `ModuleDefinition` ;
- je brancherais les modules existants dessus progressivement ;
- je ne réécrirais pas toute la logique métier d'un coup.

Livrable :

- registre de modules ;
- contrats de modules ;
- premiers modules migrés ;
- base du futur mode lab.

## Etape 6 - Mode normal et mode laboratoire

But :

Servir deux publics :

- utilisateur normal : il pose une question et obtient une réponse fiable ;
- utilisateur avancé : il compose les modules, teste des pipelines, remplace des briques, expérimente.

Mode normal :

- pipeline par défaut ;
- peu de réglages ;
- messages clairs ;
- validation automatique ;
- sources affichées ;
- résultat final propre.

Mode laboratoire :

- choix des modules ;
- ordre d'exécution ;
- paramètres avancés ;
- logs visibles ;
- entrées/sorties de chaque module ;
- comparaison de pipelines ;
- possibilité d'ajouter ses propres modules.

Prompt :

```text
Conçois deux modes d'utilisation pour l'application : un mode normal simple et un mode laboratoire avancé. Les deux doivent utiliser les mêmes modules internes, mais avec une interface différente. Le mode normal masque la complexité, le mode lab l'expose.
```

Comment je l'appliquerais :

- je garderais un pipeline officiel pour le mode normal ;
- je ferais du mode lab un orchestrateur visuel ou semi-visuel ;
- je rendrais chaque étape inspectable ;
- je veillerais à ce que le mode lab ne devienne pas un chaos incontrôlable.

Livrable :

- deux modes cohérents ;
- même moteur interne ;
- UX adaptée aux deux usages.

## Etape 7 - Ingestion documentaire

But :

Transformer les fichiers bruts en ressources exploitables.

Formats à gérer progressivement :

- Markdown ;
- texte brut ;
- PDF ;
- images ;
- audio ;
- éventuellement HTML, EPUB, CSV, JSON.

Chaque document doit produire :

- contenu brut ;
- contenu nettoyé ;
- métadonnées ;
- source ;
- hash ;
- version ;
- éventuelles annotations ;
- statut de validation.

Prompt :

```text
Implémente une couche d'ingestion documentaire. Elle doit lire des fichiers Markdown et texte au départ, puis être extensible aux PDF, images et audio. Chaque ressource ingérée doit produire un objet document normalisé avec contenu, métadonnées, source, hash et statut.
```

Comment je l'appliquerais :

- je commencerais par Markdown et texte ;
- j'ajouterais PDF ensuite ;
- je préparerais les champs multimodaux sans forcer leur implémentation immédiate ;
- je stockerais les résultats dans un format clair et versionnable.

Livrable :

- ingestion fiable ;
- format documentaire canonique ;
- base pour retrieval et KG.

## Etape 8 - Indexation et retrieval

But :

Permettre à l'IA de retrouver les bons documents rapidement.

Approche :

- chunking contrôlé ;
- embeddings ;
- index vectoriel ;
- recherche textuelle classique ;
- recherche hybride ;
- citation des sources ;
- scoring ;
- filtrage par univers, thème, type, date, statut.

Prompt :

```text
Crée une couche de retrieval hybride. Elle doit combiner recherche sémantique et recherche textuelle, retourner des passages sourcés, filtrables par univers et métadonnées, avec un score et une justification minimale.
```

Comment je l'appliquerais :

- je partirais d'un index simple ;
- j'ajouterais le filtrage ;
- je garderais les chunks traçables vers le fichier source ;
- je vérifierais la qualité avec des requêtes tests.

Livrable :

- recherche fiable ;
- chunks sourcés ;
- premiers benchmarks de récupération.

## Etape 9 - Knowledge Graph

But :

Structurer le lore sous forme d'entités, relations, événements, règles et contraintes.

Le KG ne remplace pas le RAG.

Il complète le RAG :

- RAG = retrouver les sources ;
- KG = vérifier la cohérence logique ;
- mémoire validée = conserver ce qui a été accepté.

Prompt :

```text
Ajoute une couche Knowledge Graph légère. Elle doit représenter les entités, relations, événements, règles de canon, contradictions possibles et sources. Le graphe doit servir à la validation, pas seulement à l'affichage.
```

Comment je l'appliquerais :

- je commencerais par un schéma minimal ;
- je stockerais les relations avec leurs sources ;
- je créerais un validateur simple ;
- je ne complexifierais pas tant que les cas d'usage ne l'exigent pas.

Livrable :

- schéma KG ;
- premières entités/relation ;
- validation de cohérence minimale.

## Etape 10 - Mémoire validée

But :

Créer un espace où les résultats validés deviennent de nouvelles connaissances contrôlées.

Principe :

Une génération IA ne doit pas automatiquement devenir du canon.

Elle doit passer par :

- génération ;
- justification par sources ;
- validation humaine ou automatique ;
- sauvegarde ;
- versionnement ;
- possibilité de rollback.

Prompt :

```text
Implémente une mémoire validée. Les sorties générées par l'IA doivent pouvoir être acceptées, rejetées ou modifiées. Seules les sorties validées deviennent réutilisables comme connaissance dans les requêtes futures.
```

Comment je l'appliquerais :

- je créerais un statut `draft`, `validated`, `rejected` ;
- je stockerais les sources utilisées ;
- je relierais les entrées validées au KG ;
- je garderais l'historique versionné.

Livrable :

- mémoire contrôlée ;
- validation humaine possible ;
- historique exploitable.

## Etape 11 - Génération IA

But :

Produire du texte utile, cohérent et sourcé.

Modèles possibles :

- API payante type OpenAI ou Anthropic ;
- Groq pour certains modèles gratuits ou peu coûteux selon disponibilité ;
- modèle local via LM Studio, Ollama ou autre ;
- Hermes ou modèle similaire pour agent local ;
- modèle spécialisé plus tard via LoRA ou fine-tuning.

Point important :

Un abonnement ChatGPT ne donne pas automatiquement accès gratuit à l'API OpenAI. L'API est généralement facturée séparément à l'usage.

Prompt :

```text
Crée une couche LLM abstraite. L'application doit pouvoir utiliser plusieurs fournisseurs : OpenAI, Anthropic, Groq, modèle local via Ollama ou LM Studio. Le reste du code ne doit pas dépendre directement d'un fournisseur précis.
```

Comment je l'appliquerais :

- je créerais une interface commune `LLMProvider` ;
- je brancherais les fournisseurs un par un ;
- je mettrais les clés en variables d'environnement ;
- je prévoirais un fallback local ;
- je loguerais coût, modèle, durée et erreurs.

Livrable :

- génération indépendante du fournisseur ;
- configuration claire ;
- possibilité de modèle local.

## Etape 12 - Validation des sorties

But :

Empêcher les hallucinations et maintenir la cohérence.

Types de validation :

- validation par sources ;
- validation par contraintes ;
- validation par KG ;
- validation stylistique ;
- validation de continuité ;
- validation humaine.

Prompt :

```text
Ajoute une couche de validation des générations. Chaque sortie doit être vérifiée contre les sources récupérées, les contraintes du monde, le Knowledge Graph et la mémoire validée. Le système doit signaler les incertitudes au lieu de les masquer.
```

Comment je l'appliquerais :

- je commencerais avec une checklist simple ;
- je forcerais la génération à citer ses sources ;
- je signalerais les assertions non sourcées ;
- je distinguerais clairement canon, extrapolation et invention.

Livrable :

- sorties plus fiables ;
- erreurs mieux visibles ;
- base pour validation avancée.

## Etape 13 - Multimodal

But :

Ne pas limiter le projet au texte.

Types de ressources :

- images ;
- captures ;
- cartes ;
- schémas ;
- sons ;
- voix ;
- musiques ;
- vidéos plus tard.

Ce que ça change :

L'architecture ne change pas radicalement, mais les objets documentaires doivent accepter plusieurs modalités.

Il faut prévoir :

- extraction OCR ;
- description d'image ;
- embeddings image ;
- transcription audio ;
- embeddings audio ;
- liens entre médias et texte ;
- sources multimodales dans la validation.

Prompt :

```text
Prépare l'architecture multimodale du projet. Les documents doivent pouvoir contenir texte, image et audio. Commence par définir les types et métadonnées nécessaires, puis ajoute l'OCR, la description d'image et la transcription audio progressivement.
```

Comment je l'appliquerais :

- je modifierais le modèle documentaire sans tout implémenter tout de suite ;
- je commencerais par image + OCR ;
- j'ajouterais ensuite image embedding ;
- je traiterais l'audio après stabilisation du texte et des images.

Livrable :

- modèle documentaire multimodal ;
- premiers modules image/audio ;
- architecture prête pour la suite.

## Etape 14 - Agents IA

But :

Créer une couche capable d'orchestrer les outils, choisir où chercher, quand valider et quand demander confirmation.

Attention :

Un agent IA n'est utile que si les outils sont bons.

Il faut d'abord avoir :

- ingestion fiable ;
- retrieval fiable ;
- modules déclarés ;
- validation ;
- logs ;
- limites de sécurité.

Prompt :

```text
Crée une couche agent au-dessus des modules existants. L'agent doit pouvoir choisir les outils à appeler, expliquer son plan, exécuter les modules, vérifier ses résultats et demander validation quand une décision est risquée.
```

Comment je l'appliquerais :

- je commencerais par un agent simple à étapes explicites ;
- je limiterais les outils disponibles ;
- je loggerais chaque action ;
- je donnerais priorité à la traçabilité plutôt qu'à l'autonomie totale.

Livrable :

- agent contrôlé ;
- orchestration des modules ;
- décisions inspectables.

## Etape 15 - Intégration du template IA

But :

Récupérer les bonnes idées du template sans importer du bruit.

Ce qui peut être utile :

- personnalités d'agents ;
- templates de prompts ;
- organisation de workflows ;
- mémoire de projet ;
- profils d'assistants ;
- structure documentaire ;
- exemples d'orchestration.

Ce qu'il faut éviter :

- importer une architecture incompatible ;
- multiplier les abstractions ;
- créer des agents décoratifs ;
- mélanger ton identité personnelle, tes projets et le moteur applicatif sans séparation claire.

Use cases pour ton parcours professionnel IA :

- portfolio vivant ;
- laboratoire d'agents ;
- démonstrateur RAG/KG/multimodal ;
- base personnelle de connaissances ;
- assistant de recherche ;
- outil pour documenter tes projets ;
- preuve concrète de compétence open source.

Prompt :

```text
Analyse le template IA et propose uniquement les éléments transférables dans RAGElven. Classe-les en trois catégories : à intégrer maintenant, à adapter plus tard, à ignorer. Ne copie rien mécaniquement.
```

Comment je l'appliquerais :

- je lirais le template ;
- je comparerais ses concepts au coeur modulaire ;
- je n'intégrerais que ce qui sert les objectifs ;
- je garderais l'identité du projet RAGElven prioritaire.

Livrable :

- rapport de réutilisation ;
- éventuels prompts ou agents adaptés ;
- aucune dépendance inutile.

## Etape 16 - MCP

But :

Exposer certaines capacités du projet comme outils utilisables par des agents externes.

Question importante :

Les MCP ne remplacent pas les modules internes.

Ils sont plutôt une interface standardisée autour de modules déjà propres.

Donc :

- module interne d'abord ;
- MCP ensuite.

Exemples de MCP futurs :

- rechercher dans le corpus ;
- lire un document ;
- extraire les entités ;
- interroger le KG ;
- valider une assertion ;
- générer une entrée de lore ;
- ajouter une mémoire validée ;
- lister les univers disponibles.

Coût :

Un MCP local peut être gratuit à héberger.

Il peut tourner :

- sur ta machine ;
- dans ton application ;
- dans un serveur local ;
- dans un VPS ;
- dans une plateforme cloud.

Ce qui peut coûter :

- hébergement cloud ;
- stockage ;
- appels API IA ;
- embeddings via API ;
- base vectorielle managée ;
- trafic ;
- maintenance.

Prompt :

```text
Transforme certains modules stables en outils MCP. Commence par les outils les plus utiles : recherche corpus, lecture document, interrogation KG, validation d'assertion. Les MCP doivent rester fins et appeler le coeur applicatif existant.
```

Comment je l'appliquerais :

- je sélectionnerais seulement les modules stables ;
- je créerais un serveur MCP minimal ;
- je documenterais les outils ;
- je testerais depuis un client compatible ;
- je ne transformerais pas toute l'application en MCP.

Livrable :

- premiers outils MCP ;
- documentation ;
- interopérabilité avec agents externes.

## Etape 17 - Fine-tuning et LoRA

But :

Adapter un modèle à ton style, tes formats ou ton domaine.

Attention :

Le fine-tuning ne doit pas être fait trop tôt.

Avant de fine-tuner, il faut :

- corpus propre ;
- données validées ;
- tâches répétitives identifiées ;
- prompts stables ;
- évaluation ;
- budget matériel ou cloud ;
- métriques.

Ce qui peut être entraîné :

- style d'écriture ;
- classification de documents ;
- extraction d'entités ;
- reformulation de requêtes ;
- formatage canonique ;
- génération de lore dans un ton spécifique.

Ce qui ne doit pas dépendre seulement du fine-tuning :

- connaissance factuelle exacte ;
- recherche de sources ;
- validation ;
- cohérence globale.

Prompt :

```text
Prépare une stratégie LoRA/fine-tuning pour RAGElven. Identifie les tâches qui bénéficieraient vraiment d'un entraînement, les données nécessaires, le format dataset, les métriques d'évaluation et les risques. Ne lance pas l'entraînement tant que le corpus validé n'est pas prêt.
```

Comment je l'appliquerais :

- je commencerais par collecter les exemples validés ;
- je créerais un dataset versionné ;
- je ferais une baseline sans fine-tuning ;
- je comparerais avant/après ;
- je garderais le RAG comme source principale de vérité.

Livrable :

- stratégie d'entraînement ;
- dataset prêt ;
- LoRA seulement si utile.

## Etape 18 - Open source et gouvernance

But :

Préparer le projet pour GitHub.

Actions :

- README clair ;
- installation simple ;
- `.env.example` ;
- licence ;
- contribution guide ;
- architecture documentée ;
- exemples de corpus ;
- tests ;
- CI ;
- pas de secrets ;
- données sous licence claire ;
- séparation entre code et corpus privés.

Prompt :

```text
Prépare le projet pour une publication open source propre. Ajoute ou corrige README, licence, .env.example, guide de contribution, documentation d'architecture, scripts de lancement et tests de base. Vérifie qu'aucun secret ou fichier privé n'est publié.
```

Comment je l'appliquerais :

- je ferais un audit secrets ;
- je vérifierais les fichiers suivis par Git ;
- je créerais des exemples minimaux ;
- je documenterais l'installation ;
- je garderais les gros corpus hors repo principal si nécessaire.

Livrable :

- projet publiable ;
- installation compréhensible ;
- contribution possible.

## Ordre conseillé des prompts

Prompt 1 :

```text
Analyse entièrement le projet et fais un audit technique complet sans modifier les fichiers.
```

Prompt 2 :

```text
Nettoie le projet en retirant les éléments morts, dangereux ou obsolètes, tout en gardant l'application lançable.
```

Prompt 3 :

```text
Teste et documente chaque module existant avec son entrée, sa sortie, ses dépendances et son état réel.
```

Prompt 4 :

```text
Ecris l'architecture cible du projet sous forme technique, avec les couches, responsabilités et interfaces.
```

Prompt 5 :

```text
Crée un coeur modulaire avec registre de modules, contrats typés et exécution standardisée.
```

Prompt 6 :

```text
Branche les modules existants sur le nouveau registre sans changer encore leur logique profonde.
```

Prompt 7 :

```text
Crée le mode normal et le mode laboratoire au-dessus du même moteur modulaire.
```

Prompt 8 :

```text
Implémente l'ingestion documentaire Markdown/texte puis prépare l'extension PDF/image/audio.
```

Prompt 9 :

```text
Implémente le retrieval hybride avec chunks sourcés, score, filtres et citations.
```

Prompt 10 :

```text
Ajoute un Knowledge Graph minimal pour entités, relations, règles, événements et sources.
```

Prompt 11 :

```text
Ajoute une mémoire validée avec statuts draft, validated et rejected.
```

Prompt 12 :

```text
Crée une abstraction LLM compatible OpenAI, Anthropic, Groq, Ollama et LM Studio.
```

Prompt 13 :

```text
Ajoute une couche de validation des générations contre les sources, contraintes, KG et mémoire validée.
```

Prompt 14 :

```text
Prépare le multimodal avec types documentaires image/audio, OCR, transcription et embeddings futurs.
```

Prompt 15 :

```text
Ajoute un agent contrôlé capable d'orchestrer les modules stables avec logs et limites.
```

Prompt 16 :

```text
Analyse le template IA et intègre seulement les éléments réellement utiles.
```

Prompt 17 :

```text
Expose certains modules stables en MCP fins et documentés.
```

Prompt 18 :

```text
Prépare le projet pour GitHub open source avec README, licence, .env.example, tests et guide de contribution.
```

## Roadmap concrète recommandée

Phase 1 - Stabilisation :

- audit ;
- nettoyage ;
- sécurité ;
- lancement fiable ;
- tests minimaux.

Phase 2 - Architecture :

- documentation cible ;
- registre de modules ;
- contrats ;
- migration des modules existants.

Phase 3 - Données :

- ingestion ;
- chunking ;
- retrieval ;
- sources ;
- corpus versionné Git.

Phase 4 - Intelligence :

- génération ;
- validation ;
- KG ;
- mémoire validée ;
- abstraction LLM.

Phase 5 - Interfaces :

- mode normal ;
- mode lab ;
- logs ;
- comparaison de pipelines.

Phase 6 - Extension :

- multimodal ;
- agents ;
- template IA ;
- MCP.

Phase 7 - Professionnalisation :

- documentation open source ;
- tests ;
- CI ;
- exemples ;
- publication GitHub ;
- éventuellement LoRA/fine-tuning.

## Ce que je ferais en premier

Je commencerais par trois choses seulement :

1. Audit + nettoyage.
2. Stabilisation des modules existants.
3. Création du registre de modules.

Pourquoi :

Parce que tout le reste dépend de ça.

Si les modules sont flous, les MCP seront flous.

Si les données sont floues, le KG sera fragile.

Si la génération n'est pas sourcée, la mémoire validée deviendra dangereuse.

Si le mode lab n'a pas de contrats propres, il deviendra une interface de bricolage au lieu d'un vrai laboratoire.

## Position honnête sur la stratégie

Ton idée est solide.

Mais elle devient solide seulement si elle reste progressive.

Les risques principaux sont :

- vouloir faire agent, multimodal, KG, MCP et fine-tuning trop tôt ;
- accumuler des modules décoratifs ;
- confondre génération et connaissance validée ;
- laisser l'application dépendre d'une seule API ;
- rendre le mode lab trop libre sans garde-fous ;
- publier open source avant d'avoir sécurisé les secrets et les données.

La bonne stratégie est :

- d'abord un socle propre ;
- ensuite des modules fiables ;
- ensuite une mémoire et une validation ;
- ensuite agents et MCP ;
- enfin fine-tuning si les données le justifient.

## Résumé final

Oui, le plan général est bon :

1. Epurer et vérifier le code existant.
2. Basculer vers l'architecture cible.
3. Récupérer seulement les bonnes idées du template IA.
4. Créer ou stabiliser les modules.
5. Exposer certains modules en MCP.

Mais il faut ajouter explicitement :

- une phase sécurité/secrets ;
- une phase tests ;
- une abstraction LLM ;
- une mémoire validée ;
- une couche de validation ;
- une stratégie multimodale ;
- une préparation open source ;
- une stratégie fine-tuning seulement après constitution d'un corpus propre.

Le coeur du projet doit rester modulaire.

Les MCP viendront comme interface externe.

Le mode normal servira l'utilisateur.

Le mode lab servira les contributeurs, chercheurs, bidouilleurs et utilisateurs avancés.

Cette dualité est probablement l'une des meilleures idées du projet.
