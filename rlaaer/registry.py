"""Experiment Registry — SQLite-backed searchable index of all experiments.

Replaces filesystem glob-based experiment discovery with indexed metadata.
Searchable by: pillar, hypothesis, dataset, author, engine version, outcome, status.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from rlaaer.config import REPO_ROOT


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    hypothesis TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    author TEXT,
    tags TEXT,            -- JSON list
    data_sources TEXT,    -- JSON list of source names
    systems TEXT,         -- JSON dict
    outcome TEXT,         -- published | rejected | null
    significance REAL,    -- p-value if computed
    effect_size REAL,     -- Cohen's d if computed
    git_commit TEXT,
    spec_hash TEXT,
    engine_version TEXT,
    created TEXT,
    updated TEXT,
    path TEXT
);

CREATE TABLE IF NOT EXISTS lifecycled_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL REFERENCES experiments(id),
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    detail TEXT          -- JSON
);

CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_tags ON experiments(tags);
CREATE INDEX IF NOT EXISTS idx_experiments_outcome ON experiments(outcome);
CREATE INDEX IF NOT EXISTS idx_events_experiment ON lifecycled_events(experiment_id);
"""


class ExperimentRegistryError(Exception):
    """Raised on registry failures."""


class ExperimentRegistry:
    """SQLite-backed experiment registry with searchable metadata."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.path.join(REPO_ROOT, "rlaaer", "data", "experiments.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def register(self, spec: dict, path: str = "") -> dict:
        """Register or update an experiment from its spec.yaml."""
        exp = spec.get("experiment", {})
        eid = exp.get("id", "unknown")
        tags = exp.get("tags", [])
        data_sources = [d.get("source", "") for d in spec.get("data_sources", [])]

        now = datetime.now(timezone.utc).isoformat()

        self._conn.execute("""
            INSERT INTO experiments (id, title, hypothesis, status, author, tags, data_sources, systems, created, updated, path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                hypothesis=excluded.hypothesis,
                status=excluded.status,
                author=excluded.author,
                tags=excluded.tags,
                data_sources=excluded.data_sources,
                systems=excluded.systems,
                updated=excluded.updated,
                path=excluded.path
        """, (
            eid,
            exp.get("title", ""),
            exp.get("hypothesis", ""),
            exp.get("status", "draft"),
            exp.get("author", ""),
            json.dumps(tags),
            json.dumps(data_sources),
            json.dumps(spec.get("systems", {})),
            exp.get("created", now),
            now,
            path,
        ))
        self._conn.commit()
        return self.get(eid)

    def update_status(self, experiment_id: str, status: str, from_status: str | None = None, detail: dict | None = None):
        """Update experiment status and record lifecycle event."""
        if from_status is None:
            old = self.get(experiment_id)
            from_status = old.get("status", "unknown") if old else "unknown"

        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE experiments SET status=?, updated=? WHERE id=?",
            (status, now, experiment_id),
        )
        self._conn.execute(
            "INSERT INTO lifecycled_events (experiment_id, from_status, to_status, timestamp, detail) VALUES (?, ?, ?, ?, ?)",
            (experiment_id, from_status, status, now, json.dumps(detail or {})),
        )
        self._conn.commit()

    def update_outcome(self, experiment_id: str, outcome: str, significance: float | None = None, effect_size: float | None = None):
        """Record publication outcome and statistics."""
        self._conn.execute(
            "UPDATE experiments SET outcome=?, significance=?, effect_size=?, updated=? WHERE id=?",
            (outcome, significance, effect_size, datetime.now(timezone.utc).isoformat(), experiment_id),
        )
        self._conn.commit()

    def update_provenance(self, experiment_id: str, git_commit: str, spec_hash: str, engine_version: str):
        """Update provenance fields."""
        self._conn.execute(
            "UPDATE experiments SET git_commit=?, spec_hash=?, engine_version=?, updated=? WHERE id=?",
            (git_commit, spec_hash, engine_version, datetime.now(timezone.utc).isoformat(), experiment_id),
        )
        self._conn.commit()

    def get(self, experiment_id: str) -> dict | None:
        """Get experiment by ID."""
        row = self._conn.execute(
            "SELECT * FROM experiments WHERE id=?", (experiment_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_all(self) -> list[dict]:
        """List all experiments, ordered by created."""
        rows = self._conn.execute(
            "SELECT * FROM experiments ORDER BY created DESC"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search(self, **kwargs) -> list[dict]:
        """Search experiments by any field.

        Examples:
            registry.search(pillar="07")
            registry.search(outcome="published")
            registry.search(status="draft")
            registry.search(tag="cognition")
            registry.search(author="R-LAAER")
        """
        query = "SELECT * FROM experiments WHERE 1=1"
        params = []

        for key, value in kwargs.items():
            if key == "tag":
                query += " AND tags LIKE ?"
                params.append(f"%{value}%")
            elif key == "data_source":
                query += " AND data_sources LIKE ?"
                params.append(f"%{value}%")
            elif key == "id":
                query += " AND id = ?"
                params.append(value)
            elif key in ("title", "hypothesis", "author", "status", "outcome", "git_commit", "spec_hash", "engine_version"):
                query += f" AND {key} LIKE ?"
                params.append(f"%{value}%")
            else:
                raise ExperimentRegistryError(f"Unknown search key: {key}")

        query += " ORDER BY created DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def history(self, experiment_id: str) -> list[dict]:
        """Get lifecycle history for an experiment."""
        rows = self._conn.execute(
            "SELECT * FROM lifecycled_events WHERE experiment_id=? ORDER BY timestamp",
            (experiment_id,),
        ).fetchall()
        return [{
            "id": r["id"],
            "from_status": r["from_status"],
            "to_status": r["to_status"],
            "timestamp": r["timestamp"],
            "detail": json.loads(r["detail"]) if r["detail"] else {},
        } for r in rows]

    def stats(self) -> dict:
        """Return aggregate statistics about the registry."""
        counts = self._conn.execute("""
            SELECT status, COUNT(*) as cnt FROM experiments GROUP BY status
        """).fetchall()
        return {
            "total": sum(r["cnt"] for r in counts),
            "by_status": {r["status"]: r["cnt"] for r in counts},
        }

    def close(self):
        self._conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        for field in ("tags", "data_sources", "systems"):
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
