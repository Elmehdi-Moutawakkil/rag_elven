"""Build the Knowledge Graph for the Terran Empire (Star Trek Mirror Universe).

Run once (or whenever lore files change):
    python scripts/build_kg_terran.py

Entities and relations are hand-verified from the 7 canon lore files
in data/universes/terran_empire/lore/. Only episodic canon (TOS, DS9, ENT)
— no novels.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3

KG_PATH = PROJECT_ROOT / "vector_db" / "terran_empire" / "knowledge_graph.sqlite"
KG_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    aliases     TEXT    DEFAULT '[]',
    entity_type TEXT    NOT NULL,
    description TEXT,
    era         TEXT,
    source_file TEXT
);

CREATE TABLE IF NOT EXISTS relations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entity1_id    INTEGER NOT NULL,
    relation_type TEXT    NOT NULL,
    entity2_id    INTEGER NOT NULL,
    confidence    REAL    DEFAULT 1.0,
    note          TEXT,
    FOREIGN KEY (entity1_id) REFERENCES entities(id),
    FOREIGN KEY (entity2_id) REFERENCES entities(id)
);

CREATE TABLE IF NOT EXISTS canon_facts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    description       TEXT NOT NULL,
    violation_pattern TEXT,
    severity          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_name  ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type  ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_relations_e1   ON relations(entity1_id);
CREATE INDEX IF NOT EXISTS idx_relations_e2   ON relations(entity2_id);
"""

# ─────────────────────────────────────────────────────────────────────────────
# ENTITIES  (name, aliases_json, entity_type, description, era, source_file)
# ─────────────────────────────────────────────────────────────────────────────
ENTITIES = [

    # ── Characters — Terran Empire era ────────────────────────────────────────
    ("Mirror Kirk",    '["Captain Kirk", "James T. Kirk (Mirror)"]',
     "character", "Ruthless captain of the ISS Enterprise, possessor of the Tantalus Field", "TOS", "key_figures.txt"),
    ("Mirror Spock",   '["Commander Spock (Mirror)", "Emperor Spock"]',
     "character", "Vulcan first officer of ISS Enterprise; later reformed the Empire, leading to its downfall", "TOS,DS9", "key_figures.txt"),
    ("Mirror Sulu",    '["Hikaru Sulu (Mirror)"]',
     "character", "Helmsman of ISS Enterprise, opportunistic and dangerous", "TOS", "key_figures.txt"),
    ("Mirror Uhura",   '["Nyota Uhura (Mirror)"]',
     "character", "Communications officer of ISS Enterprise, conspired against Kirk", "TOS", "key_figures.txt"),
    ("Mirror Scotty",  '["Montgomery Scott (Mirror)"]',
     "character", "Chief engineer of ISS Enterprise", "TOS", "key_figures.txt"),
    ("Mirror McCoy",   '["Leonard McCoy (Mirror)", "Bones (Mirror)"]',
     "character", "Chief medical officer of ISS Enterprise", "TOS", "key_figures.txt"),
    ("Mirror Marlena", '["Marlena Moreau"]',
     "character", "Captain's woman on ISS Enterprise, helped Prime Kirk return home", "TOS", "key_figures.txt"),

    # ── Characters — Alliance era ──────────────────────────────────────────────
    ("Intendant Kira", '["Kira Nerys (Mirror)", "The Intendant"]',
     "character", "Bajoran Intendant of Terok Nor under the Klingon-Cardassian Alliance, sadistic and vain", "DS9", "key_figures.txt"),
    ("Mirror Sisko",   '["Benjamin Sisko (Mirror)"]',
     "character", "Terran rebel leader who worked with Prime Sisko; later became a freedom fighter", "DS9", "key_figures.txt"),
    ("Mirror Bashir",  '["Julian Bashir (Mirror)"]',
     "character", "Terran rebel, works with Mirror Sisko's cell", "DS9", "key_figures.txt"),
    ("Mirror O'Brien", '["Miles OBrien (Mirror)", "Smiley"]',
     "character", "Terran slave engineer on Terok Nor, later key rebel figure who stole the ISS Defiant plans", "DS9", "key_figures.txt"),
    ("Mirror Ezri",    '["Ezri Tigan (Mirror)"]',
     "character", "Mercenary and resistance fighter in the Mirror Universe", "DS9", "key_figures.txt"),
    ("Mirror Garak",   '["Elim Garak (Mirror)"]',
     "character", "Cardassian regent's enforcer, brutal and calculating", "DS9", "key_figures.txt"),
    ("Mirror Worf",    '["Worf (Mirror)", "Regent Worf"]',
     "character", "Klingon regent of the Alliance after Kira's fall from power", "DS9", "key_figures.txt"),
    ("Mirror Quark",   '["Quark (Mirror)"]',
     "character", "Ferengi arms dealer operating on Terok Nor", "DS9", "key_figures.txt"),
    ("Mirror Nog",     '["Nog (Mirror)"]',
     "character", "Son of Mirror Rom, rebel fighter", "DS9", "key_figures.txt"),
    ("Mirror Archer",  '["Jonathan Archer (Mirror)"]',
     "character", "Captain of ISS Enterprise NX-01, brutal commander of the Terran Empire", "ENT", "key_figures.txt"),
    ("Mirror T'Pol",   '["TPol (Mirror)"]',
     "character", "Vulcan first officer on ISS Enterprise NX-01", "ENT", "key_figures.txt"),
    ("Mirror Tucker",  '["Charles Tucker (Mirror)", "Trip (Mirror)"]',
     "character", "Chief engineer of ISS Enterprise NX-01, conspirator against Archer", "ENT", "key_figures.txt"),
    ("Hoshi Sato",     '["Empress Hoshi Sato"]',
     "character", "Communications officer turned Empress after seizing the ISS Defiant (NX-01 era)", "ENT", "key_figures.txt"),
    ("Phlox (Mirror)", '[]',
     "character", "Denobulan doctor on ISS Enterprise NX-01, performed experiments on alien prisoners", "ENT", "key_figures.txt"),
    ("Zefram Cochrane",'["Cochrane (Mirror)"]',
     "character", "First human to achieve warp — in Mirror Universe, fired on the Vulcan ship and killed the crew", "ENT", "history_and_origins.txt"),

    # ── Factions ───────────────────────────────────────────────────────────────
    ("Terran Empire",         '["The Empire"]',
     "faction", "Brutal human-dominated interstellar empire that ruled through fear and slavery", "TOS,ENT", "political_structure.txt"),
    ("Klingon-Cardassian Alliance", '["The Alliance"]',
     "faction", "Coalition that overthrew the Terran Empire after Spock's reforms weakened it", "DS9", "the_alliance_and_fall.txt"),
    ("Terran Rebellion",      '["The Rebellion", "Terran resistance"]',
     "faction", "Underground resistance of enslaved Terrans fighting the Alliance", "DS9", "terok_nor_and_rebellion.txt"),
    ("Vulcan Resistance",     '[]',
     "faction", "Vulcan cells that sometimes cooperated with the Terran Rebellion", "DS9", "terok_nor_and_rebellion.txt"),

    # ── Locations ──────────────────────────────────────────────────────────────
    ("Terok Nor",      '["Mirror Deep Space 9"]',
     "place", "Cardassian ore-processing station in the Bajoran sector; hub of Alliance power and Terran slave labor", "DS9", "terok_nor_and_rebellion.txt"),
    ("ISS Enterprise NCC-1701", '["ISS Enterprise"]',
     "place", "Flagship of the Terran Empire during the TOS era", "TOS", "technology_and_fleet.txt"),
    ("ISS Enterprise NX-01",   '["NX-01 Mirror"]',
     "place", "First warp-capable ISS vessel; later seized by Hoshi Sato", "ENT", "technology_and_fleet.txt"),
    ("ISS Defiant",    '["Defiant NX-74205 (Mirror)"]',
     "place", "Federation starship from the Prime Universe, brought to Mirror Universe by Mirror O'Brien; became key rebel weapon", "DS9", "technology_and_fleet.txt"),
    ("Bajor (Mirror)", '[]',
     "place", "Bajoran homeworld under Alliance occupation", "DS9", "terok_nor_and_rebellion.txt"),
    ("Earth (Mirror)", '["Terra"]',
     "place", "Homeworld of the Terran Empire", "TOS,ENT", "history_and_origins.txt"),

    # ── Artifacts / Technology ─────────────────────────────────────────────────
    ("Tantalus Field", '[]',
     "artifact", "Device used by Mirror Kirk to remotely disintegrate enemies; origin unknown", "TOS", "technology_and_fleet.txt"),
    ("Agony Booth",    '[]',
     "artifact", "Full-body torture device used as standard punishment aboard Terran Empire vessels and stations", "TOS", "political_structure.txt"),
    ("Agonizer",       '["Personal agonizer"]',
     "artifact", "Personal pain-delivery device carried by Terran Empire officers", "TOS", "political_structure.txt"),
    ("Terran Empire emblem", '[]',
     "artifact", "Globe-and-sword insignia of the Terran Empire", "TOS,ENT", "political_structure.txt"),

    # ── Events ─────────────────────────────────────────────────────────────────
    ("Mirror Universe Crossover (TOS)", '["Mirror Mirror"]',
     "event", "Ion storm transporter accident swapped Prime Kirk's crew with Mirror counterparts aboard ISS Enterprise", "TOS", "mirror_universe_crossover_events.txt"),
    ("Cochrane's Attack",  '[]',
     "event", "Zefram Cochrane fired on and killed the Vulcan first contact delegation, founding the Terran Empire's expansionist ideology", "ENT", "history_and_origins.txt"),
    ("Spock's Reforms",    '[]',
     "event", "Mirror Spock implemented humanitarian reforms after Kirk's report; weakened the Empire, enabling Alliance conquest", "TOS,DS9", "the_alliance_and_fall.txt"),
    ("Fall of the Terran Empire", '[]',
     "event", "Klingon-Cardassian Alliance conquered the weakened Terran Empire, enslaving Terrans and Bajorans", "DS9", "the_alliance_and_fall.txt"),
    ("ISS Defiant Heist",  '[]',
     "event", "Mirror O'Brien brought plans of the Prime Universe Defiant; rebels built a copy that shifted the war", "DS9", "technology_and_fleet.txt"),
    ("Empress Hoshi Seizure", '[]',
     "event", "Hoshi Sato seized the ISS Defiant (NX-01 era) and declared herself Empress of the Terran Empire", "ENT", "mirror_universe_crossover_events.txt"),
]

# ─────────────────────────────────────────────────────────────────────────────
# RELATIONS  (entity1_name, relation_type, entity2_name, confidence, note)
# ─────────────────────────────────────────────────────────────────────────────
RELATIONS = [
    # Mirror Kirk
    ("Mirror Kirk",    "commands",       "ISS Enterprise NCC-1701", 1.0, "TOS canon"),
    ("Mirror Kirk",    "possesses",      "Tantalus Field",           1.0, "Mirror Mirror episode"),
    ("Mirror Kirk",    "member_of",      "Terran Empire",            1.0, None),
    ("Mirror Kirk",    "ally_of",        "Mirror Marlena",           0.9, "Captain's Woman"),

    # Mirror Spock
    ("Mirror Spock",   "first_officer_of", "ISS Enterprise NCC-1701", 1.0, None),
    ("Mirror Spock",   "member_of",      "Terran Empire",            1.0, None),
    ("Mirror Spock",   "initiated",      "Spock's Reforms",          1.0, "After Prime Kirk's advice"),
    ("Spock's Reforms","caused",         "Fall of the Terran Empire", 1.0, "Weakened Empire"),

    # Intendant Kira
    ("Intendant Kira", "controls",       "Terok Nor",                1.0, "DS9 Mirror episodes"),
    ("Intendant Kira", "member_of",      "Klingon-Cardassian Alliance", 1.0, None),
    ("Intendant Kira", "enemy_of",       "Terran Rebellion",         1.0, None),

    # Mirror Sisko / Rebellion
    ("Mirror Sisko",   "leads",          "Terran Rebellion",         0.9, "DS9 Mirror episodes"),
    ("Mirror Sisko",   "enemy_of",       "Klingon-Cardassian Alliance", 1.0, None),
    ("Mirror O'Brien", "member_of",      "Terran Rebellion",         1.0, None),
    ("Mirror Bashir",  "member_of",      "Terran Rebellion",         1.0, None),
    ("Mirror O'Brien", "stole_plans_of", "ISS Defiant",              1.0, "ISS Defiant Heist"),
    ("ISS Defiant Heist", "part_of",     "Terran Rebellion",         1.0, None),

    # Terok Nor
    ("Terok Nor",      "located_in",     "Bajor (Mirror)",           1.0, "Bajoran sector"),
    ("Terok Nor",      "controlled_by",  "Klingon-Cardassian Alliance", 1.0, None),

    # Alliance
    ("Klingon-Cardassian Alliance", "conquered", "Terran Empire",    1.0, "DS9 backstory"),
    ("Fall of the Terran Empire",   "caused_by", "Spock's Reforms",  1.0, None),

    # Technology
    ("Agony Booth",    "used_by",        "Terran Empire",            1.0, "Standard punishment"),
    ("Agonizer",       "used_by",        "Terran Empire",            1.0, "Personal device"),
    ("Tantalus Field", "owned_by",       "Mirror Kirk",              1.0, None),

    # ENT era
    ("Mirror Archer",  "commands",       "ISS Enterprise NX-01",     1.0, "ENT In a Mirror Darkly"),
    ("Hoshi Sato",     "seized",         "ISS Enterprise NX-01",     1.0, "Became Empress"),
    ("Cochrane's Attack", "founded",     "Terran Empire",            0.9, "Ideological origin"),
    ("Zefram Cochrane","triggered",      "Cochrane's Attack",        1.0, None),

    # Crossover event
    ("Mirror Universe Crossover (TOS)", "involved", "Mirror Kirk",   1.0, "Mirror Mirror TOS"),
    ("Mirror Universe Crossover (TOS)", "involved", "Mirror Spock",  1.0, None),

    # Mirror Worf
    ("Mirror Worf",    "member_of",      "Klingon-Cardassian Alliance", 1.0, None),
    ("Mirror Worf",    "regent_of",      "Klingon-Cardassian Alliance", 0.9, "Late DS9 Mirror episodes"),
    ("Mirror Garak",   "enforcer_for",   "Mirror Worf",              0.9, None),
]

# ─────────────────────────────────────────────────────────────────────────────
# CANON FACTS — hard rules for story validation
# ─────────────────────────────────────────────────────────────────────────────
CANON_FACTS = [
    # HARD — factual errors that break canon
    ("The Terran Empire is from the Mirror Universe, not the Prime Star Trek universe",
     r"(?i)(prime universe|federation universe).{0,30}terran empire|terran empire.{0,30}(prime universe|star fleet command(?! mirror))",
     "HARD"),
    ("Terok Nor is a space station, not a planet or ship",
     r"(?i)terok nor.{0,20}(planet|ship|vessel|colony)",
     "HARD"),
    ("The Agony Booth is a torture device, not a medical or relaxation device",
     r"(?i)agony booth.{0,30}(meditation|healing|relaxation|comfort|pleasure)",
     "HARD"),
    ("Promotion in the Terran Empire is achieved through assassination, not merit exams",
     r"(?i)(exam|test|evaluation|merit review).{0,30}promotion.{0,30}(terran empire|iss enterprise)",
     "HARD"),
    ("Mirror Spock is a Vulcan, not human",
     r"(?i)mirror spock.{0,20}(human|terran|man|earthling)",
     "HARD"),
    ("The Tantalus Field is a weapon/kill device, not a transporter or medical device",
     r"(?i)tantalus field.{0,30}(transport|heal|cure|medical)",
     "HARD"),
    ("In Mirror Universe, the Alliance defeated the Empire — not the Federation",
     r"(?i)federation.{0,30}(defeated|conquered|overthrew).{0,30}(terran empire|empire)",
     "HARD"),
    ("ISS vessels belong to the Terran Empire, USS vessels to the Federation — do not mix",
     r"(?i)uss enterprise.{0,20}mirror universe|mirror.{0,20}uss enterprise(?! prime)",
     "HARD"),

    # SOFT — likely errors but could be creative license
    ("The Klingon-Cardassian Alliance enslaved Terrans, not exterminated them",
     r"(?i)(klingon.cardassian alliance|the alliance).{0,40}(exterminated|wiped out|genocide).{0,20}terran",
     "SOFT"),
    ("Mirror Bashir and O'Brien are rebel fighters, not Alliance loyalists",
     r"(?i)(mirror bashir|mirror o.brien|smiley).{0,30}(alliance officer|cardassian agent|loyal to the alliance)",
     "SOFT"),
    ("Cochrane's first contact in Mirror Universe ended in violence, not peace",
     r"(?i)cochrane.{0,30}(peaceful|friendly|welcomed).{0,30}(vulcan|first contact)",
     "SOFT"),
]


# ─────────────────────────────────────────────────────────────────────────────
# BUILD
# ─────────────────────────────────────────────────────────────────────────────

def build():
    conn = sqlite3.connect(KG_PATH)
    conn.executescript(SCHEMA_SQL)

    # Insert entities
    name_to_id = {}
    for name, aliases, etype, desc, era, src in ENTITIES:
        cur = conn.execute(
            "INSERT OR REPLACE INTO entities (name, aliases, entity_type, description, era, source_file) "
            "VALUES (?,?,?,?,?,?)",
            (name, aliases, etype, desc, era, src)
        )
        name_to_id[name] = cur.lastrowid

    # Re-fetch all ids (INSERT OR REPLACE may reassign)
    for row in conn.execute("SELECT id, name FROM entities"):
        name_to_id[row[1]] = row[0]

    # Insert relations
    skipped = 0
    for e1, rtype, e2, conf, note in RELATIONS:
        id1 = name_to_id.get(e1)
        id2 = name_to_id.get(e2)
        if not id1 or not id2:
            print(f"  ⚠️  skipping relation ({e1} → {e2}): entity not found")
            skipped += 1
            continue
        conn.execute(
            "INSERT INTO relations (entity1_id, relation_type, entity2_id, confidence, note) "
            "VALUES (?,?,?,?,?)",
            (id1, rtype, id2, conf, note)
        )

    # Insert canon facts
    for desc, pattern, severity in CANON_FACTS:
        conn.execute(
            "INSERT INTO canon_facts (description, violation_pattern, severity) VALUES (?,?,?)",
            (desc, pattern, severity)
        )

    conn.commit()
    conn.close()

    print(f"✅ Terran Empire KG built → {KG_PATH}")
    print(f"   Entities : {len(ENTITIES)}")
    print(f"   Relations: {len(RELATIONS) - skipped} inserted ({skipped} skipped)")
    print(f"   Canon facts: {len(CANON_FACTS)}")


if __name__ == "__main__":
    build()
