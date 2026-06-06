"""Populate the Knowledge Graph SQLite database from lore corpus.

Run once (or whenever lore files change):
    python scripts/build_kg.py

This script hard-codes entities and relations extracted by reading the
9 lore/*.txt files.  Hard-coding is intentional: it lets us hand-verify
every entry, which is faster and more reliable than NLP auto-extraction
at this corpus size (~100 entities, ~200 relations).
"""

import sys
from pathlib import Path

# Make sure src/ is importable when running from the project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.knowledge_graph import KnowledgeGraph

# ==============================================================================
# DATA — extracted by reading the 9 lore/*.txt files
# ==============================================================================

# (name, [aliases], entity_type, description, age)
ENTITIES: list[tuple] = [

    # ── Characters ────────────────────────────────────────────────────────────
    ("Thingol",       ["Elwe", "Elu Thingol"],        "character", "High King of the Sindar, lord of Doriath", "first"),
    ("Melian",        [],                              "character", "Maia queen of Doriath, mother of Luthien", "first"),
    ("Luthien",       ["Luthien Tinuviel"],            "character", "Daughter of Thingol and Melian, most beautiful of all Elves", "first"),
    ("Feanor",        ["Curufinwe", "Feanaro"],        "character", "Greatest craftsman of the Noldor, creator of Silmarils and Tengwar", "first"),
    ("Galadriel",     [],                              "character", "One of the greatest Noldor, later Lady of Lothlorien", "first,second,third"),
    ("Celebrimbor",   [],                              "character", "Greatest smith of the Second Age, forged the three Elven rings", "second"),
    ("Elrond",        [],                              "character", "Half-elven lord of Rivendell", "second,third"),
    ("Gil-galad",     [],                              "character", "Last High King of the Noldor in Middle-earth", "second"),
    ("Fingolfin",     [],                              "character", "High King of the Noldor, wounded Morgoth seven times in single combat", "first"),
    ("Maedhros",      [],                              "character", "Eldest son of Feanor, great leader of the Noldor", "first"),
    ("Maglor",        [],                              "character", "Son of Feanor, greatest singer of the Noldor", "first"),
    ("Celeborn",      [],                              "character", "Lord of Lothlorien, husband of Galadriel, Sindarin", "third"),
    ("Cirdan",        ["Cirdan the Shipwright"],        "character", "Keeper of the Grey Havens, oldest of Elves in Middle-earth", "all"),
    ("Legolas",       [],                              "character", "Sindarin Elf of the Woodland Realm, member of the Fellowship", "third"),
    ("Finrod",        ["Finrod Felagund"],             "character", "Noldorin lord, founder of Nargothrond", "first"),
    ("Turgon",        [],                              "character", "Noldorin lord, king of Gondolin", "first"),
    ("Earendil",      [],                              "character", "Half-elven mariner who sailed to Valinor, set as the Evening Star", "first"),
    ("Turin",         ["Turin Turambar"],              "character", "Son of Hurin, cursed by Morgoth, slew Glaurung with Gurthang", "first"),
    ("Glorfindel",    [],                              "character", "Lord of Gondolin who slew a Balrog; later re-embodied and returned", "first,third"),
    ("Beren",         [],                              "character", "Mortal Man who cut a Silmaril from Morgoth's crown", "first"),
    ("Ingwe",         [],                              "character", "High King of all Elves, leader of the Vanyar", "first"),
    ("Olwe",          [],                              "character", "King of the Teleri in Valinor, brother of Thingol", "first"),
    ("Thranduil",     [],                              "character", "Sindarin king of Mirkwood, father of Legolas", "third"),
    ("Finwe",         [],                              "character", "King of the Noldor in Valinor, father of Feanor", "first"),
    ("Daeron",        [],                              "character", "Lore-master and minstrel of Doriath, inventor of the Cirth runes", "first"),
    ("Hurin",         [],                              "character", "Father of Turin, captured by Morgoth and set to watch his family's doom", "first"),
    ("Idril",         [],                              "character", "Elf of Gondolin, wife of Tuor, mother of Earendil", "first"),
    ("Imin",          [],                              "character", "First Elf to awake at Cuivienen", "primeval"),
    ("Glaurung",      [],                              "character", "First of the dragons, slain by Turin Turambar", "first"),
    ("Huan",          ["Hound of Valinor"],            "character", "Hound of the Valar who helped Beren and Luthien, defeated Sauron", "first"),
    ("Ungoliant",     [],                              "character", "Great spirit of darkness in spider form who helped Morgoth destroy the Two Trees", "first"),

    # ── Valar ─────────────────────────────────────────────────────────────────
    ("Manwe",         [],                              "character", "Lord of the Winds and King of Arda, highest of the Valar", "all"),
    ("Varda",         ["Elbereth"],                   "character", "Lady of the Stars, beloved above all Valar by the Elves", "all"),
    ("Ulmo",          [],                              "character", "Lord of Waters, dwells in the deep seas", "all"),
    ("Aule",          [],                              "character", "Lord of the Earth and Maker, secretly fashioned the Dwarves", "all"),
    ("Yavanna",       [],                              "character", "Giver of Fruits, created the Two Trees and the Ents", "all"),
    ("Mandos",        ["Namo"],                        "character", "Keeper of the Dead, his halls receive fallen Elves", "all"),
    ("Nienna",        [],                              "character", "Lady of Mercy and Grief, teacher of Gandalf", "all"),
    ("Orome",         [],                              "character", "Lord of Forests, first Vala to discover the Elves at Cuivienen", "all"),
    ("Tulkas",        [],                              "character", "Champion of the Valar, last to descend into Arda", "all"),

    # ── Maiar ─────────────────────────────────────────────────────────────────
    ("Sauron",        ["Annatar", "Mairon", "the Dark Lord"], "character", "Maia, Morgoth's lieutenant, Lord of Mordor in the Second and Third Age", "second,third"),
    ("Gandalf",       ["Olorin", "Mithrandir", "the Grey", "the White"], "character", "Maia, wisest of the Istari, carried Narya the Ring of Fire", "third"),
    ("Saruman",       ["Curunir", "the White"],        "character", "Maia of Aule, head of the Istari, corrupted by desire for the One Ring", "third"),
    ("Radagast",      ["Aiwendil"],                    "character", "Maia of Yavanna, lover of animals, dwelt at Rhosgobel", "third"),
    ("Eonwe",         [],                              "character", "Herald of Manwe, led the host of Valar in the War of Wrath", "first"),
    ("Osse",          [],                              "character", "Maia serving Ulmo, delights in storms and the seas of Middle-earth", "all"),
    ("Uinen",         [],                              "character", "Lady of the Seas, consort of Osse, calms storms", "all"),
    ("Arien",         [],                              "character", "Maia who guides the Sun across the sky", "all"),
    ("Tilion",        [],                              "character", "Maia who steers the Moon", "all"),

    # ── Morgoth ───────────────────────────────────────────────────────────────
    ("Morgoth",       ["Melkor", "Moringotto", "Black Enemy"], "character", "Greatest of the Valar, source of all evil, stole the Silmarils, cast into the Void", "first"),

    # ── Places ────────────────────────────────────────────────────────────────
    ("Doriath",       ["the hidden kingdom", "Forest of Doriath"], "place", "Realm of Thingol and Melian, protected by the Girdle of Melian", "first"),
    ("Beleriand",     [],                              "place", "Great land in northwest Middle-earth during the First Age; sank at the War of Wrath", "first"),
    ("Angband",       [],                              "place", "Morgoth's fortress in northwest Middle-earth beneath the Iron Mountains", "first"),
    ("Thangorodrim",  [],                              "place", "Three volcanic peaks above Angband, crown of Morgoth's realm", "first"),
    ("Gondolin",      ["the hidden city", "Ondolinde"], "place", "Hidden city of Turgon in Beleriand", "first"),
    ("Nargothrond",   [],                              "place", "Underground Noldorin kingdom founded by Finrod Felagund", "first"),
    ("Valinor",       ["Aman", "the Blessed Realm", "the Undying Lands", "the West"], "place", "Land of the Valar across the sea in the West", "all"),
    ("Tirion",        [],                              "place", "City of the Noldor in Valinor, built upon the hill of Tuna", "all"),
    ("Alqualonde",    ["Swan Haven"],                  "place", "City of the Teleri in Valinor, site of the Kinslaying", "all"),
    ("Cuivienen",     [],                              "place", "Bay in the far east of Middle-earth where the Elves first awoke", "primeval"),
    ("Rivendell",     ["Imladris"],                    "place", "Refuge founded by Elrond in the Second Age", "second,third"),
    ("Lothlorien",    ["Lorien", "Laurelindorenan", "the Golden Wood"], "place", "Realm of Galadriel and Celeborn, populated by Silvan Elves", "third"),
    ("Mirkwood",      ["Eryn Lasgalen", "Greenwood the Great"], "place", "Woodland realm of Thranduil in the Third Age", "third"),
    ("Mordor",        ["the Black Land"],              "place", "Land of Sauron in southeast Middle-earth, site of Mount Doom", "second,third"),
    ("Grey Havens",   ["Mithlond"],                    "place", "Haven maintained by Cirdan the Shipwright on the Gulf of Lune", "second,third"),
    ("Nan Elmoth",    [],                              "place", "Dark forest in Beleriand where Thingol encountered Melian", "first"),
    ("Hithlum",       [],                              "place", "Region of Beleriand ruled by Fingolfin and his sons", "first"),
    ("Valmar",        [],                              "place", "City of the Valar in Valinor, where the Vanyar dwelt", "all"),
    ("Mount Doom",    ["Orodruin"],                    "place", "Volcanic mountain in Mordor where Sauron forged the One Ring", "second,third"),
    ("Moria",         ["Khazad-dum", "the Dwarrowdelf"], "place", "Great underground Dwarf-realm beneath the Misty Mountains", "all"),
    ("Rhosgobel",     [],                              "place", "Dwelling of Radagast on the edge of Mirkwood", "third"),
    ("Isengard",      ["Orthanc"],                     "place", "Stronghold of Saruman in the Third Age", "third"),
    ("Tol Sirion",    ["Tol-in-Gaurhoth"],             "place", "Isle in Beleriand held by Sauron; later called Isle of Werewolves", "first"),
    ("Ard-galen",     ["Anfauglith"],                  "place", "Plains north of Beleriand burned by Morgoth in the Dagor Bragollach", "first"),
    ("Utumno",        [],                              "place", "Morgoth's first fortress, destroyed by the Valar in ancient times", "primeval"),
    ("Numenor",       ["Elenna"],                      "place", "Island given to the Edain after the War of Wrath; drowned by the Valar", "second"),

    # ── Groups / Races ────────────────────────────────────────────────────────
    ("Vanyar",        ["Minyar"],                      "group", "First and smallest clan of Eldar; faithful to the Valar; golden-haired", "all"),
    ("Noldor",        ["Tatyar", "Deep Elves"],        "group", "Second clan; greatest craftsmen and scholars of Elves", "all"),
    ("Sindar",        ["Grey Elves"],                  "group", "Elves of Beleriand who did not complete the Great Journey to Valinor", "first,second,third"),
    ("Teleri",        ["Nelyar"],                      "group", "Third and largest clan of Eldar; expert mariners", "all"),
    ("Avari",         ["the Unwilling"],               "group", "Elves who refused the Great Journey westward", "all"),
    ("Eldar",         [],                              "group", "Elves who began the Great Journey, whether or not they reached Valinor", "all"),
    ("Nandor",        [],                              "group", "Elves who turned back at the Misty Mountains during the Great Journey", "all"),
    ("Silvan Elves",  ["Wood-Elves"],                  "group", "Elves of Mirkwood and Lorien, of Nandor origin", "third"),
    ("Edain",         [],                              "group", "Men who allied with the Elves against Morgoth in the First Age", "first"),
    ("Numenoreans",   [],                              "group", "Descendants of the Edain given the island of Numenor", "second"),
    ("Istari",        ["Wizards"],                     "group", "Five Maiar sent to Middle-earth by the Valar at the start of the Third Age", "third"),
    ("Quendi",        [],                              "group", "Original name for all Elves: those who speak with voices", "all"),
    ("Dwarves",       ["Khazad"],                      "group", "Race fashioned secretly by Aule; speak Khuzdul", "all"),
    ("Orcs",          ["Yrch"],                        "group", "Corrupted creatures bred by Morgoth, armies of darkness", "all"),
    ("Balrogs",       ["Valaraukar"],                  "group", "Maiar corrupted by Morgoth and clad in fire and shadow", "first"),
    ("Maiar",         [],                              "group", "Angelic beings lesser than the Valar; servants of the Valar; some came to Middle-earth", "all"),
    ("Valar",         ["the Powers"],                  "group", "Fourteen great Ainur who descended into Arda to shape and govern it", "all"),
    ("Ainur",         [],                              "group", "Holy spirits created by Iluvatar before the world; includes both Valar and Maiar", "all"),

    # ── Artifacts ─────────────────────────────────────────────────────────────
    ("Silmarils",     ["the Jewels of Feanor"],        "artifact", "Three jewels capturing the light of the Two Trees, created by Feanor", "first"),
    ("One Ring",      ["the Ruling Ring", "the Ring of Power", "the One"], "artifact", "Ring forged by Sauron in Mount Doom, containing much of his power", "second,third"),
    ("Narya",         ["Ring of Fire", "the Red Ring"], "artifact", "One of the three Elven rings; carried by Gandalf", "second,third"),
    ("Nenya",         ["Ring of Water", "Ring of Adamant"], "artifact", "One of the three Elven rings; carried by Galadriel", "second,third"),
    ("Vilya",         ["Ring of Air", "Ring of Sapphire"], "artifact", "One of the three Elven rings; carried by Gil-galad, later Elrond", "second,third"),
    ("Palantiri",     ["Seeing Stones"],               "artifact", "Seven crystal spheres for far-seeing, made by Feanor and later used by Sauron", "second,third"),
    ("Tengwar",       [],                              "artifact", "Flowing writing system invented by Feanor of the Noldor", "all"),
    ("Cirth",         [],                              "artifact", "Angular runic script invented by Daeron of Doriath; adopted by Dwarves", "all"),
    ("Gurthang",      ["Anglachel"],                   "artifact", "Black sword forged from a meteorite, wielded by Turin Turambar", "first"),
    ("Two Trees",     ["Telperion", "Laurelin"],       "artifact", "Two trees of Valinor whose light illuminated the Blessed Realm; destroyed by Morgoth and Ungoliant", "primeval"),
    ("Girdle of Melian", [],                           "artifact", "Magical barrier cast by Melian around Doriath", "first"),

    # ── Events ────────────────────────────────────────────────────────────────
    ("Great Journey",      [],                         "event", "Westward journey of the Elves from Cuivienen to Valinor, led by Orome", "primeval"),
    ("Darkening of Valinor", [],                       "event", "Destruction of the Two Trees by Morgoth and Ungoliant", "first"),
    ("Kinslaying",         ["Kinslaying at Alqualonde"], "event", "Slaying of Teleri by the Noldor to steal their ships", "first"),
    ("Doom of Mandos",     ["Doom of the Noldor"],     "event", "Curse on the Noldor for their rebellion and the Kinslaying", "first"),
    ("War of Wrath",       ["Great Battle"],           "event", "Final war of the Valar against Morgoth; ended the First Age", "first"),
    ("Dagor-nuin-Giliath", ["Battle Under Stars"],     "event", "First battle of the First Age after the Noldor's return", "first"),
    ("Dagor Aglareb",      ["Glorious Battle"],        "event", "Second battle; established the Siege of Angband", "first"),
    ("Dagor Bragollach",   ["Battle of Sudden Flame"], "event", "Third battle; Morgoth broke the Siege of Angband with rivers of fire", "first"),
    ("Nirnaeth Arnoediad", ["Battle of Unnumbered Tears"], "event", "Fourth battle; catastrophic defeat of the Elves and their allies", "first"),
    ("Fall of Gondolin",   [],                         "event", "Destruction of Turgon's hidden city by Morgoth's forces", "first"),
    ("Fall of Nargothrond", [],                        "event", "Destruction of Finrod's underground kingdom by Glaurung", "first"),
    ("Fall of Doriath",    [],                         "event", "Destruction of Thingol's realm following his death", "first"),

    # ── Languages ─────────────────────────────────────────────────────────────
    ("Quenya",             ["High Elvish", "Elven-latin"], "language", "Ancient tongue of the Vanyar and Noldor in Valinor; language of lore and ceremony", "all"),
    ("Sindarin",           ["Grey Elvish"],            "language", "Language of the Sindar; most widely spoken Elvish tongue in Middle-earth", "all"),
    ("Telerin",            [],                         "language", "Language of the Teleri in Valinor", "all"),
    ("Primitive Quendian", ["Common Eldarin"],         "language", "Ancestral tongue of all Elves, from which all Elvish languages descend", "primeval"),
    ("Valarin",            [],                         "language", "Language of the Valar; oldest language in existence", "all"),
    ("Nandorin",           ["Silvan Elvish"],          "language", "Language of the Wood-Elves", "all"),
    ("Khuzdul",            [],                         "language", "Secret language of the Dwarves, modeled on Semitic patterns", "all"),
    ("Black Speech",       [],                         "language", "Language created by Sauron for his servants", "second,third"),
    ("Westron",            ["Common Speech", "Common Tongue"], "language", "Lingua franca of Middle-earth in the Third Age, descended from Adunaic", "third"),
]

# ==============================================================================
# RELATIONS
# (entity1_name, relation_type, entity2_name, confidence, note)
# ==============================================================================

RELATIONS: list[tuple] = [

    # ── Leadership / Rulership ────────────────────────────────────────────────
    ("Thingol",    "king_of",       "Doriath",      1.0, ""),
    ("Melian",     "queen_of",      "Doriath",      1.0, ""),
    ("Turgon",     "king_of",       "Gondolin",     1.0, ""),
    ("Finrod",     "king_of",       "Nargothrond",  1.0, "founder and king"),
    ("Fingolfin",  "high_king_of",  "Noldor",       1.0, "High King of the Noldor in Middle-earth"),
    ("Ingwe",      "high_king_of",  "Vanyar",       1.0, ""),
    ("Ingwe",      "high_king_of",  "Quendi",       1.0, "High King of all Elves"),
    ("Finwe",      "king_of",       "Noldor",       1.0, "in Valinor"),
    ("Olwe",       "king_of",       "Teleri",       1.0, "in Valinor"),
    ("Thranduil",  "king_of",       "Mirkwood",     1.0, ""),
    ("Gil-galad",  "high_king_of",  "Noldor",       1.0, "last High King"),
    ("Manwe",      "king_of",       "Valinor",      1.0, "King of Arda"),
    ("Elrond",     "lord_of",       "Rivendell",    1.0, ""),
    ("Galadriel",  "lady_of",       "Lothlorien",   1.0, ""),
    ("Celeborn",   "lord_of",       "Lothlorien",   1.0, ""),
    ("Cirdan",     "keeper_of",     "Grey Havens",  1.0, ""),
    ("Morgoth",    "ruler_of",      "Angband",      1.0, ""),
    ("Sauron",     "ruler_of",      "Mordor",       1.0, ""),

    # ── Family ────────────────────────────────────────────────────────────────
    ("Melian",     "spouse_of",     "Thingol",      1.0, ""),
    ("Thingol",    "spouse_of",     "Melian",       1.0, ""),
    ("Luthien",    "daughter_of",   "Thingol",      1.0, ""),
    ("Luthien",    "daughter_of",   "Melian",       1.0, ""),
    ("Beren",      "spouse_of",     "Luthien",      1.0, ""),
    ("Luthien",    "spouse_of",     "Beren",        1.0, ""),
    ("Maedhros",   "son_of",        "Feanor",       1.0, "eldest son"),
    ("Maglor",     "son_of",        "Feanor",       1.0, ""),
    ("Galadriel",  "spouse_of",     "Celeborn",     1.0, ""),
    ("Celeborn",   "spouse_of",     "Galadriel",    1.0, ""),
    ("Olwe",       "brother_of",    "Thingol",      1.0, ""),
    ("Thingol",    "brother_of",    "Olwe",         1.0, ""),
    ("Turin",      "son_of",        "Hurin",        1.0, ""),
    ("Earendil",   "son_of",        "Idril",        1.0, ""),
    ("Feanor",     "son_of",        "Finwe",        1.0, ""),
    ("Elrond",     "son_of",        "Earendil",     1.0, ""),
    ("Legolas",    "son_of",        "Thranduil",    1.0, ""),

    # ── Creation / Craft ──────────────────────────────────────────────────────
    ("Feanor",     "created",       "Silmarils",    1.0, "three jewels capturing light of the Two Trees"),
    ("Feanor",     "invented",      "Tengwar",      1.0, "finest writing system in Middle-earth"),
    ("Daeron",     "invented",      "Cirth",        1.0, "runic script later adopted by Dwarves"),
    ("Aule",       "created",       "Dwarves",      1.0, "fashioned secretly before the Elves awoke"),
    ("Yavanna",    "created",       "Two Trees",    1.0, "Telperion and Laurelin"),
    ("Sauron",     "forged",        "One Ring",     1.0, "in the fires of Mount Doom"),
    ("Celebrimbor","forged",        "Narya",        1.0, "one of the three Elven rings"),
    ("Celebrimbor","forged",        "Nenya",        1.0, ""),
    ("Celebrimbor","forged",        "Vilya",        1.0, ""),
    ("Melian",     "cast",          "Girdle of Melian", 1.0, "magical barrier protecting Doriath"),
    ("Feanor",     "created",       "Palantiri",    0.8, "attributed to Feanor in some texts"),

    # ── Protection / Carrying ─────────────────────────────────────────────────
    ("Girdle of Melian", "protects", "Doriath",     1.0, ""),
    ("Gandalf",    "carries",       "Narya",        1.0, "given by Cirdan the Shipwright"),
    ("Galadriel",  "carries",       "Nenya",        1.0, ""),
    ("Gil-galad",  "carried",       "Vilya",        1.0, "before passing it to Elrond"),
    ("Elrond",     "carries",       "Vilya",        1.0, ""),

    # ── Theft / Possession ────────────────────────────────────────────────────
    ("Morgoth",    "stole",         "Silmarils",    1.0, "from Finwe's vault after killing him"),
    ("Morgoth",    "destroyed",     "Two Trees",    1.0, "with help of Ungoliant"),
    ("Ungoliant",  "helped_destroy","Two Trees",    1.0, ""),

    # ── Affiliation ───────────────────────────────────────────────────────────
    ("Thingol",    "member_of",     "Sindar",       1.0, ""),
    ("Melian",     "member_of",     "Maiar",        1.0, ""),
    ("Feanor",     "member_of",     "Noldor",       1.0, ""),
    ("Galadriel",  "member_of",     "Noldor",       1.0, ""),
    ("Celebrimbor","member_of",     "Noldor",       1.0, ""),
    ("Fingolfin",  "member_of",     "Noldor",       1.0, ""),
    ("Maedhros",   "member_of",     "Noldor",       1.0, ""),
    ("Maglor",     "member_of",     "Noldor",       1.0, ""),
    ("Ingwe",      "member_of",     "Vanyar",       1.0, ""),
    ("Olwe",       "member_of",     "Teleri",       1.0, ""),
    ("Cirdan",     "member_of",     "Sindar",       1.0, "of Telerin origin"),
    ("Thranduil",  "member_of",     "Sindar",       1.0, ""),
    ("Legolas",    "member_of",     "Sindar",       1.0, ""),
    ("Sauron",     "member_of",     "Maiar",        1.0, ""),
    ("Gandalf",    "member_of",     "Maiar",        1.0, ""),
    ("Gandalf",    "member_of",     "Istari",       1.0, ""),
    ("Saruman",    "member_of",     "Maiar",        1.0, ""),
    ("Saruman",    "member_of",     "Istari",       1.0, ""),
    ("Radagast",   "member_of",     "Maiar",        1.0, ""),
    ("Radagast",   "member_of",     "Istari",       1.0, ""),
    ("Manwe",      "member_of",     "Valar",        1.0, ""),
    ("Varda",      "member_of",     "Valar",        1.0, ""),
    ("Ulmo",       "member_of",     "Valar",        1.0, ""),
    ("Aule",       "member_of",     "Valar",        1.0, ""),
    ("Yavanna",    "member_of",     "Valar",        1.0, ""),
    ("Mandos",     "member_of",     "Valar",        1.0, ""),
    ("Orome",      "member_of",     "Valar",        1.0, ""),
    ("Tulkas",     "member_of",     "Valar",        1.0, ""),
    ("Morgoth",    "member_of",     "Valar",        1.0, "originally; later corrupted"),

    # ── Service ───────────────────────────────────────────────────────────────
    ("Sauron",     "served",        "Morgoth",      1.0, "chief lieutenant"),
    ("Gandalf",    "served",        "Manwe",        1.0, "Maia of Manwe and Varda"),
    ("Saruman",    "served",        "Aule",         1.0, "Maia of Aule originally"),
    ("Radagast",   "served",        "Yavanna",      1.0, "Maia of Yavanna"),
    ("Eonwe",      "served",        "Manwe",        1.0, "herald of Manwe"),
    ("Osse",       "served",        "Ulmo",         1.0, ""),
    ("Uinen",      "served",        "Ulmo",         1.0, ""),
    ("Arien",      "served",        "Valar",        1.0, "guides the Sun"),

    # ── Geographic ────────────────────────────────────────────────────────────
    ("Doriath",    "located_in",    "Beleriand",    1.0, ""),
    ("Gondolin",   "located_in",    "Beleriand",    1.0, ""),
    ("Nargothrond","located_in",    "Beleriand",    1.0, ""),
    ("Angband",    "located_in",    "Beleriand",    1.0, "far northwest"),
    ("Thangorodrim","located_above","Angband",      1.0, "three volcanic peaks"),
    ("Nan Elmoth", "located_in",    "Beleriand",    1.0, ""),
    ("Hithlum",    "located_in",    "Beleriand",    1.0, ""),
    ("Tol Sirion", "located_in",    "Beleriand",    1.0, ""),
    ("Ard-galen",  "located_in",    "Beleriand",    1.0, ""),
    ("Tirion",     "located_in",    "Valinor",      1.0, ""),
    ("Alqualonde", "located_in",    "Valinor",      1.0, ""),
    ("Valmar",     "located_in",    "Valinor",      1.0, ""),
    ("Mount Doom", "located_in",    "Mordor",       1.0, ""),
    ("Rhosgobel",  "located_near",  "Mirkwood",     1.0, "on the edge of Mirkwood"),

    # ── Events ────────────────────────────────────────────────────────────────
    ("Noldor",     "committed",     "Kinslaying",   1.0, "at Alqualonde"),
    ("Noldor",     "suffered",      "Doom of Mandos",1.0,"curse for rebellion and kinslaying"),
    ("Beleriand",  "destroyed_in",  "War of Wrath", 1.0, "sank beneath the sea"),
    ("Morgoth",    "defeated_in",   "War of Wrath", 1.0, "cast into the Void"),
    ("Orome",      "discovered",    "Cuivienen",    1.0, "first Vala to find the Elves"),

    # ── Languages — spoken_by ─────────────────────────────────────────────────
    ("Quenya",     "spoken_by",     "Vanyar",       1.0, ""),
    ("Quenya",     "spoken_by",     "Noldor",       1.0, "in Valinor; later as lore language"),
    ("Sindarin",   "spoken_by",     "Sindar",       1.0, ""),
    ("Sindarin",   "spoken_by",     "Noldor",       1.0, "adopted after arrival in Beleriand"),
    ("Telerin",    "spoken_by",     "Teleri",       1.0, ""),
    ("Nandorin",   "spoken_by",     "Nandor",       1.0, ""),
    ("Nandorin",   "spoken_by",     "Silvan Elves", 1.0, ""),
    ("Khuzdul",    "spoken_by",     "Dwarves",      1.0, "secret, never taught to outsiders"),
    ("Black Speech","spoken_by",    "Orcs",         1.0, ""),
    ("Westron",    "spoken_by",     "Edain",        1.0, ""),

    # ── Languages — descends from ─────────────────────────────────────────────
    ("Quenya",     "descends_from", "Primitive Quendian", 1.0, ""),
    ("Sindarin",   "descends_from", "Primitive Quendian", 1.0, ""),
    ("Telerin",    "descends_from", "Primitive Quendian", 1.0, ""),
    ("Nandorin",   "descends_from", "Primitive Quendian", 1.0, ""),

    # ── Artifacts — properties ────────────────────────────────────────────────
    ("Silmarils",  "contains",      "Two Trees",    1.0, "captured their light before destruction"),
    ("One Ring",   "forged_in",     "Mount Doom",   1.0, ""),
    ("Tengwar",    "used_to_write", "Quenya",       1.0, ""),
    ("Tengwar",    "used_to_write", "Sindarin",     1.0, ""),
    ("Tengwar",    "used_to_write", "Black Speech",  1.0, "Ring inscription"),
    ("Cirth",      "used_to_write", "Sindarin",     1.0, "original use"),
    ("Cirth",      "used_to_write", "Khuzdul",      1.0, "Dwarves extended and adopted Cirth"),
]

# ==============================================================================
# CANON FACTS (deterministic rules)
# ==============================================================================

CANON_FACTS: list[tuple] = [
    # (description, violation_pattern, severity)

    # Artifacts — creation (HARD: only canon creator can have made these)
    ("Feanor created the Silmarils",
     r"\b(silmaril|silmarilli)\b",
     "HARD"),

    ("Feanor invented the Tengwar writing system",
     r"\btengwar\b",
     "HARD"),

    ("Daeron invented the Cirth runes",
     r"\bcirth\b",
     "HARD"),

    ("Sauron forged the One Ring in Mount Doom",
     r"\b(one ring|ruling ring)\b",
     "HARD"),

    ("Celebrimbor forged the three Elven rings (Narya, Nenya, Vilya)",
     r"\b(narya|nenya|vilya|elven ring|three rings)\b",
     "HARD"),

    # Rulership (HARD: known rulers of named places)
    ("Thingol is the king of Doriath — no other character can hold that title",
     r"\b(king|ruler|lord)\b.{0,40}\bdoriath\b",
     "HARD"),

    ("Melian is the queen of Doriath",
     r"\bqueen\b.{0,40}\bdoriath\b",
     "HARD"),

    ("Turgon is the king of Gondolin",
     r"\b(king|ruler|lord)\b.{0,40}\bgondolin\b",
     "HARD"),

    ("Finrod Felagund founded Nargothrond",
     r"\b(founded|built|established)\b.{0,40}\bnargothrond\b",
     "HARD"),

    # Geography (SOFT: Beleriand sank — cannot host kingdoms in 2nd or 3rd Age)
    ("Beleriand sank beneath the sea at the end of the First Age",
     r"\bbeleriand\b.{0,60}\b(second age|third age|2nd age|3rd age)\b",
     "SOFT"),

    # Morgoth-specific
    ("Morgoth was cast into the Void after the War of Wrath — he cannot act in the Second or Third Age",
     r"\bmorgoth\b.{0,60}\b(second age|third age|2nd age|3rd age|rules|commands|leads)\b",
     "SOFT"),

    # Two Trees
    ("The Two Trees of Valinor were destroyed by Morgoth and Ungoliant — they no longer exist in Middle-earth",
     r"\btwo trees\b.{0,60}\b(exist|grow|stand|bloom)\b.{0,30}\b(middle-earth|beleriand|mirkwood)\b",
     "SOFT"),
]


# ==============================================================================
# MAIN
# ==============================================================================

def build(verbose: bool = True) -> KnowledgeGraph:
    kg = KnowledgeGraph()
    kg.connect()

    if verbose:
        print(f"Building Knowledge Graph → {kg.db_path}")
        print(f"  Inserting {len(ENTITIES)} entities…")

    # Insert entities
    for row in ENTITIES:
        name, aliases, etype, desc, age = row
        kg.upsert_entity(
            name=name,
            entity_type=etype,
            aliases=aliases,
            description=desc,
            age=age,
        )

    if verbose:
        print(f"  Inserting {len(RELATIONS)} relations…")

    # Insert relations
    errors = []
    for row in RELATIONS:
        e1, rel, e2, conf, note = row
        try:
            kg.upsert_relation(e1, rel, e2, confidence=conf, note=note)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        print(f"  ⚠️  {len(errors)} relation(s) skipped (missing entity):")
        for e in errors:
            print(f"    - {e}")

    if verbose:
        print(f"  Inserting {len(CANON_FACTS)} canon facts…")

    # Insert canon facts
    for desc, pattern, severity in CANON_FACTS:
        kg.add_canon_fact(desc, pattern, severity)

    stats = kg.get_stats()
    if verbose:
        print("\n✅ Knowledge Graph built:")
        print(f"   Entities  : {stats['entities']}")
        print(f"   Relations : {stats['relations']}")
        print(f"   Canon rules: {stats['canon_facts']}")
        print("   By type:")
        for t, n in sorted(stats["by_type"].items()):
            print(f"     {t:<12} {n}")

    return kg


if __name__ == "__main__":
    kg = build(verbose=True)
    kg.close()
