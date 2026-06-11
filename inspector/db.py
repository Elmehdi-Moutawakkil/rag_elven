"""SQLite store for inspector run history."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from inspector.config import INSPECTOR_DB


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(INSPECTOR_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      TEXT NOT NULL,
                ts          TEXT NOT NULL,
                feature_id  TEXT NOT NULL,
                universe    TEXT NOT NULL,
                feature     TEXT NOT NULL,
                question    TEXT NOT NULL,
                app_response TEXT,
                verdict     TEXT,          -- CORRECT | PARTIAL | HALLUCINATION | ERROR | IRRELEVANT
                score       REAL,          -- 0.0 to 1.0
                judge_notes TEXT,
                duration_ms INTEGER,
                error       TEXT
            );

            CREATE TABLE IF NOT EXISTS reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                report_type TEXT NOT NULL,  -- daily | weekly
                content     TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_runs_feature ON runs(feature_id);
            CREATE INDEX IF NOT EXISTS idx_runs_ts      ON runs(ts);
            CREATE INDEX IF NOT EXISTS idx_runs_verdict ON runs(verdict);
        """)


def save_run(
    run_id: str,
    feature_id: str,
    universe: str,
    feature: str,
    question: str,
    app_response: str | None,
    verdict: str,
    score: float,
    judge_notes: str,
    duration_ms: int,
    error: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO runs
               (run_id, ts, feature_id, universe, feature, question,
                app_response, verdict, score, judge_notes, duration_ms, error)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id,
                datetime.utcnow().isoformat(),
                feature_id, universe, feature, question,
                app_response, verdict, score, judge_notes, duration_ms, error,
            ),
        )


def save_report(report_type: str, content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (ts, report_type, content) VALUES (?,?,?)",
            (datetime.utcnow().isoformat(), report_type, content),
        )


def get_recent_questions(feature_id: str, days: int = 30) -> list[str]:
    """Return questions asked in the last N days for a feature (anti-repeat)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT question FROM runs
               WHERE feature_id = ?
                 AND ts >= datetime('now', ?)
               ORDER BY ts DESC""",
            (feature_id, f"-{days} days"),
        ).fetchall()
    return [r["question"] for r in rows]


def get_runs_since(hours: int = 24) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM runs
               WHERE ts >= datetime('now', ?)
               ORDER BY ts ASC""",
            (f"-{hours} hours",),
        ).fetchall()


def get_runs_since_days(days: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM runs
               WHERE ts >= datetime('now', ?)
               ORDER BY ts ASC""",
            (f"-{days} days",),
        ).fetchall()


def get_last_report(report_type: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM reports WHERE report_type = ? ORDER BY ts DESC LIMIT 1",
            (report_type,),
        ).fetchone()
