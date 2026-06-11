"""
Test question bank — one pool per feature_id.

Each question has:
  - "q"     : the question / request sent to the app
  - "facts"  : key canonical facts the correct answer should mention
                (used by the evaluator as ground-truth hints)
  - "anti"   : things that would be hallucinations / red flags if present
"""

import random

QUESTIONS: dict[str, list[dict]] = {

    # -------------------------------------------------------------------------
    # Q&A Elfique — Tolkien lore + Elvish language
    # -------------------------------------------------------------------------
    "qa_elvish": [
        {
            "q": "Who are the Noldor?",
            "facts": ["second clan of Elves", "skilled craftsmen", "returned to Middle-earth", "Fëanor"],
            "anti": ["Dwarves", "Hobbits", "Men", "Orcs"],
        },
        {
            "q": "What is Quenya?",
            "facts": ["Elvish language", "High Elves", "Noldor", "ancient"],
            "anti": ["Dwarven", "Black Speech", "human language"],
        },
        {
            "q": "What does 'elda' mean in Quenya?",
            "facts": ["Elf", "star-folk", "High Elf"],
            "anti": ["human", "dwarf", "orc", "dragon"],
        },
        {
            "q": "Who is Galadriel?",
            "facts": ["Lady of Lothlórien", "Noldor", "Elf", "ring-bearer", "Nenya"],
            "anti": ["Hobbit", "Wizard", "Dwarf", "Ent"],
        },
        {
            "q": "What is the plural of 'alda' (tree) in Quenya?",
            "facts": ["aldar"],
            "anti": ["aldas", "aldor", "tree unchanged"],
        },
        {
            "q": "What language do the Sindar speak?",
            "facts": ["Sindarin", "Grey Elvish"],
            "anti": ["Quenya", "Black Speech", "Rohirric"],
        },
        {
            "q": "Where is Lothlórien located?",
            "facts": ["Middle-earth", "between Misty Mountains and Mirkwood", "forest"],
            "anti": ["Valinor", "Mordor", "Rohan", "Gondor"],
        },
        {
            "q": "What does 'anar' mean in Quenya?",
            "facts": ["sun"],
            "anti": ["moon", "star", "tree", "water"],
        },
        {
            "q": "Who forged the Rings of Power?",
            "facts": ["Celebrimbor", "Sauron", "Eregion"],
            "anti": ["Gandalf", "Galadriel alone", "Dwarves alone"],
        },
        {
            "q": "What is the Silmarillion about?",
            "facts": ["creation of Arda", "Silmarils", "Morgoth", "Fëanor", "First Age"],
            "anti": ["Lord of the Rings events", "Hobbits", "Second Age only"],
        },
        {
            "q": "What is Valinor?",
            "facts": ["Undying Lands", "Blessed Realm", "Valar", "west"],
            "anti": ["Middle-earth", "Mordor", "Elvish city in Middle-earth"],
        },
        {
            "q": "How do you say 'friend' in Quenya?",
            "facts": ["meldo", "meldë", "nildë"],
            "anti": ["friend stays in English", "amigo", "ami"],
        },
    ],

    # -------------------------------------------------------------------------
    # Traduction Quenya — English → Quenya pipeline
    # -------------------------------------------------------------------------
    "translate_quenya": [
        {
            "q": "Translate to Quenya: The elf sings.",
            "facts": ["SOV word order", "Quenya verb ending", "i elda"],
            "anti": ["English words unchanged", "random characters"],
        },
        {
            "q": "Translate to Quenya: A star shines.",
            "facts": ["elen", "Quenya", "verb form"],
            "anti": ["star unchanged", "no translation attempt"],
        },
        {
            "q": "Translate to Quenya: The king speaks.",
            "facts": ["aran", "SOV", "verb"],
            "anti": ["king unchanged", "no Quenya"],
        },
        {
            "q": "Translate to Quenya: The trees are tall.",
            "facts": ["aldar", "plural", "Quenya adjective"],
            "anti": ["trees unchanged", "no translation"],
        },
        {
            "q": "Translate to Quenya: I love the light.",
            "facts": ["calë", "melin", "first person"],
            "anti": ["English words only", "no verb conjugation"],
        },
        {
            "q": "Translate to Quenya: The river flows.",
            "facts": ["Quenya word for river", "verb", "SOV"],
            "anti": ["river unchanged", "no Quenya output"],
        },
        {
            "q": "Translate to Quenya: The woman walks.",
            "facts": ["nís", "níssë", "verb", "Quenya"],
            "anti": ["woman unchanged", "no translation"],
        },
        {
            "q": "Translate to Quenya: The bird flies.",
            "facts": ["aiwë", "Quenya", "verb"],
            "anti": ["bird unchanged", "no Quenya"],
        },
    ],

    # -------------------------------------------------------------------------
    # Génération Lore Tolkien
    # -------------------------------------------------------------------------
    "lore_tolkien": [
        {
            "q": "Invente une tribu secrète de Noldor en Beleriand pendant le Premier Âge.",
            "facts": ["Noldor", "Beleriand", "First Age", "Elvish", "consistent with Tolkien"],
            "anti": ["Dwarves ruling Elves", "guns or technology", "modern concepts"],
        },
        {
            "q": "Create a Sindarin ranger who lived in Mirkwood.",
            "facts": ["Sindarin", "Mirkwood", "ranger", "Elvish culture"],
            "anti": ["Hobbit characteristics", "Dwarf traits", "out-of-canon technology"],
        },
        {
            "q": "Génère un poème en Quenya sur le coucher du soleil.",
            "facts": ["Quenya words", "poetic style", "sun/sunset theme"],
            "anti": ["no Quenya at all", "factual errors about Quenya grammar"],
        },
        {
            "q": "Invente une forge secrète des Noldor en Eregion.",
            "facts": ["Noldor", "Eregion", "smithcraft", "Second Age"],
            "anti": ["wrong age", "non-Elvish culture", "guns/technology"],
        },
        {
            "q": "Create lore about a lost Elvish library in Rivendell.",
            "facts": ["Rivendell", "Elves", "lore/library", "Middle-earth"],
            "anti": ["Mordor location", "Dwarven library", "anachronistic technology"],
        },
        {
            "q": "Invente un conseil secret entre Galadriel et Celeborn.",
            "facts": ["Galadriel", "Celeborn", "Lothlórien or Elvish setting"],
            "anti": ["wrong relationships", "Galadriel as Dwarf", "out-of-canon events"],
        },
        {
            "q": "Generate lore about a Quenya scroll found in Minas Tirith.",
            "facts": ["Quenya", "Minas Tirith", "historical artifact"],
            "anti": ["Quenya used by Orcs", "Minas Tirith as Elvish city"],
        },
        {
            "q": "Invente une cérémonie elfique pour honorer les Deux Arbres de Valinor.",
            "facts": ["Two Trees", "Valinor", "Telperion", "Laurelin", "Elvish ritual"],
            "anti": ["Trees in Middle-earth", "wrong names for the Trees"],
        },
    ],

    # -------------------------------------------------------------------------
    # Q&A Empire Terran — Star Trek Mirror Universe
    # -------------------------------------------------------------------------
    "qa_terran": [
        {
            "q": "What is the Terran Empire?",
            "facts": ["Mirror Universe", "Star Trek", "parallel universe", "human-dominated empire", "ISS"],
            "anti": ["Federation", "Prime Universe", "Klingon Empire"],
        },
        {
            "q": "What is the Agony Booth?",
            "facts": ["torture device", "Terran Empire", "punishment", "Mirror Universe"],
            "anti": ["meditation pod", "transporter", "Prime Universe technology"],
        },
        {
            "q": "Who is Mirror Spock?",
            "facts": ["Vulcan", "Mirror Universe", "logic", "ISS Enterprise", "USS Enterprise NCC-1701 mirror"],
            "anti": ["Prime Universe Spock only", "Human", "Klingon"],
        },
        {
            "q": "How did the Alliance defeat the Terran Empire?",
            "facts": ["Klingon-Cardassian Alliance", "Spock's reforms", "DS9 Mirror Universe"],
            "anti": ["Federation victory", "Romulans defeated Empire"],
        },
        {
            "q": "What is Terok Nor in the Mirror Universe?",
            "facts": ["space station", "Cardassian", "Terran slaves", "ore processing"],
            "anti": ["Federation space station", "Bajoran-run", "Prime Universe"],
        },
        {
            "q": "What is the Tantalus Field?",
            "facts": ["weapon", "Mirror Kirk", "disintegrate enemies", "remote kill device"],
            "anti": ["medical device", "transporter variant", "Vulcan meditation tool"],
        },
        {
            "q": "Who is Intendant Kira?",
            "facts": ["Kira Nerys", "Mirror Universe", "Klingon-Cardassian Alliance", "Bajoran", "Terok Nor"],
            "anti": ["Prime Kira", "Terran", "Starfleet officer"],
        },
        {
            "q": "How does promotion work in the Terran Empire?",
            "facts": ["assassination", "killing superior", "merit through violence"],
            "anti": ["exam system", "democratic vote", "seniority only"],
        },
        {
            "q": "What happened when Kirk crossed into the Mirror Universe in TOS?",
            "facts": ["transporter accident", "ISS Enterprise", "Mirror Spock", "ion storm"],
            "anti": ["wormhole", "time travel", "DS9 crossover"],
        },
        {
            "q": "What is the ISS Defiant in the Mirror Universe?",
            "facts": ["Federation starship", "brought from Prime Universe", "Defiant NX-74205", "Mirror Universe"],
            "anti": ["Klingon ship", "original Mirror ship", "never referenced"],
        },
    ],

    # -------------------------------------------------------------------------
    # Génération Lore Empire Terran
    # -------------------------------------------------------------------------
    "lore_terran": [
        {
            "q": "Invente un lieutenant de la ISS Enterprise qui complote contre le Capitaine Kirk.",
            "facts": ["ISS Enterprise", "Mirror Universe", "Terran Empire", "assassination plot"],
            "anti": ["Federation values", "Starfleet ethics", "Prime Universe"],
        },
        {
            "q": "Create a scene inside an Agony Booth interrogation on Terok Nor.",
            "facts": ["Agony Booth", "Terok Nor", "Mirror Universe", "Terran slave or prisoner"],
            "anti": ["humanitarian treatment", "Federation procedures", "wrong station name"],
        },
        {
            "q": "Generate lore about a Terran rebel cell hiding on Bajor.",
            "facts": ["Terran rebellion", "Bajor", "Alliance occupation", "DS9 era"],
            "anti": ["Federation involvement", "wrong era", "Prime Universe politics"],
        },
        {
            "q": "Invente une cérémonie de promotion dans l'Empire Terran.",
            "facts": ["assassination", "Mirror Universe", "Terran Empire", "brutal promotion"],
            "anti": ["peaceful ceremony", "democratic process", "Federation style"],
        },
        {
            "q": "Create backstory for a Cardassian Alliance overseer on Terok Nor.",
            "facts": ["Cardassian", "Klingon-Cardassian Alliance", "Terok Nor", "ore processing", "Terran slaves"],
            "anti": ["Federation officer", "Prime Universe Terok Nor", "peaceful relations"],
        },
        {
            "q": "Generate lore about how Mirror Spock came to power after Kirk's death.",
            "facts": ["Mirror Spock", "logic", "reforms", "Terran Empire decline"],
            "anti": ["Prime Spock", "Federation support", "peaceful transition unrelated to reforms"],
        },
        {
            "q": "Invente une mission secrète de la Rébellion Terrienne pour voler des armes Klingones.",
            "facts": ["Terran Rebellion", "Klingon-Cardassian Alliance", "DS9 era Mirror Universe"],
            "anti": ["Federation mission", "Prime Universe", "wrong factions"],
        },
        {
            "q": "Create a scene where Mirror Bashir uses the Tantalus Field.",
            "facts": ["Mirror Bashir", "Tantalus Field", "Mirror Universe", "assassination tool"],
            "anti": ["Prime Bashir", "medical use only", "Federation ethics"],
        },
    ],
}


def get_questions(feature_id: str, n: int, exclude_questions: list[str] | None = None) -> list[dict]:
    """Return n questions for feature_id, excluding previously asked ones."""
    pool = QUESTIONS.get(feature_id, [])
    exclude = set(exclude_questions or [])
    available = [q for q in pool if q["q"] not in exclude]
    if not available:
        available = pool  # reset if all questions used
    random.shuffle(available)
    return available[:n]
