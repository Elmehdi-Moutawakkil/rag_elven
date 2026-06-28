"""Knowledge Graph for universe lore validation — Phase 4.

Provides deterministic validation of generated stories against canon facts
extracted from the lore corpus. Replaces the LLM-based validate_coherence()
from Phase 3 with SQLite-backed queries.

Schema:
  entities    — characters, places, artifacts, groups, events, languages
  relations   — typed edges between entities
  canon_facts — hard rules that generated text must not violate

Usage:
    kg = KnowledgeGraph()
    kg.connect()                          # open (or build) the DB
    result = kg.validate_story(story)     # deterministic check
    kg.close()

Populate the DB by running:
    python scripts/build_kg.py
"""

import re
import sqlite3
import json
from pathlib import Path
from typing import Optional

# DB lives alongside the other vector DBs
KG_DB_PATH = Path(__file__).parent.parent / "vector_db" / "knowledge_graph.sqlite"

# ==============================================================================
# SQL SCHEMA
# ==============================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    aliases     TEXT    DEFAULT '[]',   -- JSON array of alternate names
    entity_type TEXT    NOT NULL,       -- character|place|artifact|group|event|language
    description TEXT,
    age         TEXT,                   -- first|second|third|all|primeval  (comma-sep)
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
    description       TEXT NOT NULL,  -- human-readable rule
    violation_pattern TEXT,           -- regex that flags a potential violation in story text
    severity          TEXT NOT NULL   -- HARD|SOFT
);

CREATE INDEX IF NOT EXISTS idx_entities_name     ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type     ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_relations_e1      ON relations(entity1_id);
CREATE INDEX IF NOT EXISTS idx_relations_e2      ON relations(entity2_id);
CREATE INDEX IF NOT EXISTS idx_relations_type    ON relations(relation_type);
"""


# ==============================================================================
# KNOWLEDGE GRAPH CLASS
# ==============================================================================

class KnowledgeGraph:
    """SQLite-backed Knowledge Graph for lore validation."""

    def __init__(self, db_path: Path = KG_DB_PATH):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> "KnowledgeGraph":
        """Open DB connection and ensure schema exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        return self

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("KnowledgeGraph not connected. Call connect() first.")
        return self._conn

    # ------------------------------------------------------------------
    # Write helpers (used by build_kg.py)
    # ------------------------------------------------------------------

    def upsert_entity(
        self,
        name: str,
        entity_type: str,
        aliases: list[str] = None,
        description: str = "",
        age: str = "all",
        source_file: str = "",
    ) -> int:
        """Insert or replace an entity, return its id."""
        aliases_json = json.dumps(aliases or [])
        cur = self.conn.execute(
            """
            INSERT INTO entities (name, aliases, entity_type, description, age, source_file)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                aliases     = excluded.aliases,
                entity_type = excluded.entity_type,
                description = excluded.description,
                age         = excluded.age
            """,
            (name, aliases_json, entity_type, description, age, source_file),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM entities WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def upsert_relation(
        self,
        entity1_name: str,
        relation_type: str,
        entity2_name: str,
        confidence: float = 1.0,
        note: str = "",
    ):
        """Add a relation between two named entities (must already exist)."""
        e1 = self.conn.execute(
            "SELECT id FROM entities WHERE name = ?", (entity1_name,)
        ).fetchone()
        e2 = self.conn.execute(
            "SELECT id FROM entities WHERE name = ?", (entity2_name,)
        ).fetchone()

        if e1 is None:
            raise ValueError(f"Entity not found: {entity1_name!r}")
        if e2 is None:
            raise ValueError(f"Entity not found: {entity2_name!r}")

        # Avoid duplicate relations
        existing = self.conn.execute(
            """SELECT id FROM relations
               WHERE entity1_id=? AND relation_type=? AND entity2_id=?""",
            (e1["id"], relation_type, e2["id"]),
        ).fetchone()
        if existing:
            return

        self.conn.execute(
            """INSERT INTO relations (entity1_id, relation_type, entity2_id, confidence, note)
               VALUES (?, ?, ?, ?, ?)""",
            (e1["id"], relation_type, e2["id"], confidence, note),
        )
        self.conn.commit()

    def add_canon_fact(self, description: str, violation_pattern: str, severity: str):
        """Add a canon rule (HARD or SOFT)."""
        self.conn.execute(
            """INSERT INTO canon_facts (description, violation_pattern, severity)
               VALUES (?, ?, ?)""",
            (description, violation_pattern, severity),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def get_entity(self, name: str) -> Optional[dict]:
        """Fetch entity by exact name or alias."""
        # Try exact match first
        row = self.conn.execute(
            "SELECT * FROM entities WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if row:
            return dict(row)

        # Search through aliases
        all_entities = self.conn.execute("SELECT * FROM entities").fetchall()
        for entity in all_entities:
            aliases = json.loads(entity["aliases"] or "[]")
            for alias in aliases:
                if alias.lower() == name.lower():
                    return dict(entity)
        return None

    def get_relations(self, entity_name: str, relation_type: str = None) -> list[dict]:
        """Get all relations where entity is subject (entity1)."""
        entity = self.get_entity(entity_name)
        if not entity:
            return []

        if relation_type:
            rows = self.conn.execute(
                """
                SELECT r.relation_type, e2.name as target_name, e2.entity_type as target_type, r.confidence
                FROM relations r
                JOIN entities e2 ON e2.id = r.entity2_id
                WHERE r.entity1_id = ? AND r.relation_type = ?
                """,
                (entity["id"], relation_type),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT r.relation_type, e2.name as target_name, e2.entity_type as target_type, r.confidence
                FROM relations r
                JOIN entities e2 ON e2.id = r.entity2_id
                WHERE r.entity1_id = ?
                """,
                (entity["id"],),
            ).fetchall()

        return [dict(r) for r in rows]

    def get_canon_ruler(self, place_name: str) -> Optional[str]:
        """Return canonical ruler name for a place, or None."""
        place = self.get_entity(place_name)
        if not place:
            return None

        row = self.conn.execute(
            """
            SELECT e1.name
            FROM relations r
            JOIN entities e1 ON e1.id = r.entity1_id
            WHERE r.entity2_id = ?
              AND r.relation_type IN ('king_of','queen_of','lord_of','lady_of',
                                      'high_king_of','ruler_of','keeper_of')
            ORDER BY r.confidence DESC
            LIMIT 1
            """,
            (place["id"],),
        ).fetchone()
        return row[0] if row else None

    def get_canon_creator(self, artifact_name: str) -> Optional[str]:
        """Return canonical creator of an artifact."""
        artifact = self.get_entity(artifact_name)
        if not artifact:
            return None

        row = self.conn.execute(
            """
            SELECT e1.name
            FROM relations r
            JOIN entities e1 ON e1.id = r.entity1_id
            WHERE r.entity2_id = ?
              AND r.relation_type IN ('created','forged','invented','cast')
            ORDER BY r.confidence DESC
            LIMIT 1
            """,
            (artifact["id"],),
        ).fetchone()
        return row[0] if row else None

    def get_stats(self) -> dict:
        """Return entity and relation counts."""
        n_entities = self.conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        n_relations = self.conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        n_canon = self.conn.execute("SELECT COUNT(*) FROM canon_facts").fetchone()[0]
        by_type = self.conn.execute(
            "SELECT entity_type, COUNT(*) as n FROM entities GROUP BY entity_type"
        ).fetchall()
        return {
            "entities": n_entities,
            "relations": n_relations,
            "canon_facts": n_canon,
            "by_type": {r["entity_type"]: r["n"] for r in by_type},
        }

    def is_populated(self) -> bool:
        """True if the DB contains at least some entities."""
        if not self.db_path.exists():
            return False
        try:
            self.connect()
            n = self.conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            return n > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # VALIDATION  ← the core Phase 4 feature
    # ------------------------------------------------------------------

    def validate_story(self, story: str) -> dict:
        """Deterministically validate a generated story against the KG.

        Steps:
          1. Identify canon entities mentioned in the story.
          2. Detect role assertions (X is king of Y, X created Z, …).
          3. Compare against KG — flag contradictions.
          4. Compute a coherence score (0–100).

        Returns:
            {
                "score": int,
                "violations": [{"text", "canon", "severity"}],
                "entities_found": [str],
                "is_valid": bool,
                "method": "knowledge_graph",
            }
        """
        story_lower = story.lower()
        violations: list[dict] = []
        entities_found: list[str] = []

        # ── Step 1 : find canon entities in story ──────────────────────
        all_entities = self.conn.execute("SELECT * FROM entities").fetchall()
        for ent in all_entities:
            name = ent["name"]
            aliases = json.loads(ent["aliases"] or "[]")
            all_names = [name] + aliases
            for n in all_names:
                if n.lower() in story_lower:
                    if name not in entities_found:
                        entities_found.append(name)
                    break

        # ── Step 2 : role assertion checks ─────────────────────────────
        # Pattern: "<someone> is/was/became king/queen/lord/ruler of <place>"
        ROLE_PATTERN = re.compile(
            r"([\w\s]{2,25}?)\s+(?:is|was|became|served\s+as|ruled?\s+as)\s+"
            r"(?:the\s+)?(?:king|queen|lord|lady|ruler|master|keeper|high\s+king|high\s+queen)\s+"
            r"(?:of|over)\s+([\w\s]{2,25})",
            re.IGNORECASE,
        )
        for m in ROLE_PATTERN.finditer(story):
            subject_raw = m.group(1).strip()
            place_raw = m.group(2).strip().rstrip(".,;")

            canon_ruler = self.get_canon_ruler(place_raw)
            if canon_ruler and canon_ruler.lower() not in subject_raw.lower():
                violations.append({
                    "text": m.group(0).strip(),
                    "canon": f"Canon: {canon_ruler} is the ruler of {place_raw}",
                    "severity": "HARD",
                })

        # Pattern: "<someone> created/forged/invented/made <artifact>"
        CREATE_PATTERN = re.compile(
            r"([\w\s]{2,25}?)\s+(?:created|forged|invented|made|crafted|fashioned)\s+"
            r"(?:the\s+)?([\w\s]{2,25})",
            re.IGNORECASE,
        )
        for m in CREATE_PATTERN.finditer(story):
            subject_raw = m.group(1).strip()
            artifact_raw = m.group(2).strip().rstrip(".,;")

            canon_creator = self.get_canon_creator(artifact_raw)
            if canon_creator and canon_creator.lower() not in subject_raw.lower():
                violations.append({
                    "text": m.group(0).strip(),
                    "canon": f"Canon: {canon_creator} created {artifact_raw}",
                    "severity": "HARD",
                })

        # ── Step 3 : canon facts (hard-coded rules) ────────────────────
        canon_facts = self.conn.execute("SELECT * FROM canon_facts").fetchall()
        for fact in canon_facts:
            pattern = fact["violation_pattern"]
            if not pattern:
                continue
            if re.search(pattern, story_lower, re.IGNORECASE):
                violations.append({
                    "text": f"Pattern matched: {fact['description']}",
                    "canon": fact["description"],
                    "severity": fact["severity"],
                })

        # ── Step 4 : score ─────────────────────────────────────────────
        hard_count = sum(1 for v in violations if v["severity"] == "HARD")
        soft_count = sum(1 for v in violations if v["severity"] == "SOFT")
        score = max(0, 100 - hard_count * 25 - soft_count * 10)

        return {
            "score": score,
            "violations": violations,
            "entities_found": entities_found,
            "is_valid": hard_count == 0,
            "method": "knowledge_graph",
        }


# ==============================================================================
# HELPER
# ==============================================================================

def _extract_canon_answer(description: str) -> str:
    """Pull the first proper noun from a description like 'Feanor created the Silmarils'.
    Used to check whether the story already correctly names the canon subject.
    """
    # Return everything up to the first verb word as an approximation
    words = description.split()
    if words:
        return words[0]
    return ""
