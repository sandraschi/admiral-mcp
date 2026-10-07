"""SQLite persistence for runs and approvals.

Replaces the in-memory registries with a persistent SQLite database.
Uses asyncio.Lock for concurrent write safety - no thread pool needed
since FastMCP/uvicorn runs single-threaded async.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from admiral_mcp.config import get_config
from admiral_mcp.models import ApprovalDecision, ApprovalRecord, RunPhase, RunRecord

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id         TEXT PRIMARY KEY,
    repo           TEXT NOT NULL,
    phases         TEXT NOT NULL,
    harness        TEXT NOT NULL,
    current_phase  INTEGER DEFAULT 0,
    status         TEXT DEFAULT 'queued',
    cost           REAL DEFAULT 0.0,
    diff_content   TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id    TEXT PRIMARY KEY,
    run_id         TEXT NOT NULL,
    summary        TEXT NOT NULL,
    diff_ref       TEXT,
    created_at     TEXT NOT NULL,
    decision       TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
"""


def _db_path() -> Path:
    config = get_config()
    db_dir = Path(config.data_dir)
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "admiral.sqlite3"


class Database:
    def __init__(self) -> None:
        path = _db_path()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        self._lock = asyncio.Lock()
        logger.info("SQLite database at %s", path)

    # -- Runs ---------------------------------------------------------------

    async def register_run(self, run_id: str, repo: str, phases: list[str], harness: str) -> RunRecord:
        now = datetime.now(UTC).isoformat()
        phases_json = json.dumps(phases)
        async with self._lock:
            self._conn.execute(
                "INSERT INTO runs (run_id, repo, phases, harness, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, repo, phases_json, harness, now, now),
            )
            self._conn.commit()
        return RunRecord(
            run_id=run_id,
            repo=repo,
            phases=phases,
            harness=harness,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get_run(self, run_id: str) -> RunRecord | None:
        async with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    async def update_run_phase(self, run_id: str, phase: int, cost: float, status: RunPhase) -> RunRecord | None:
        now = datetime.now(UTC).isoformat()
        async with self._lock:
            self._conn.execute(
                "UPDATE runs SET current_phase = ?, cost = ?, status = ?, updated_at = ? WHERE run_id = ?",
                (phase, cost, status.value, now, run_id),
            )
            self._conn.commit()
        return await self.get_run(run_id)

    async def store_diff(self, run_id: str, diff_content: str) -> bool:
        async with self._lock:
            cur = self._conn.execute(
                "UPDATE runs SET diff_content = ? WHERE run_id = ?",
                (diff_content, run_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    async def get_diff(self, run_id: str) -> str | None:
        async with self._lock:
            row = self._conn.execute("SELECT diff_content FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None or row["diff_content"] is None:
            return None
        return row["diff_content"]

    async def list_runs(self, limit: int = 20) -> list[RunRecord]:
        async with self._lock:
            rows = self._conn.execute("SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_to_run(r) for r in rows]

    async def count_runs(self) -> int:
        async with self._lock:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM runs").fetchone()
        return row["cnt"]

    # -- Approvals ----------------------------------------------------------

    async def create_approval(self, run_id: str, summary: str, diff_ref: str | None) -> ApprovalRecord:
        approval_id = str(uuid.uuid4())[:8]
        now = datetime.now(UTC).isoformat()
        async with self._lock:
            self._conn.execute(
                "INSERT INTO approvals (approval_id, run_id, summary, diff_ref, created_at) VALUES (?, ?, ?, ?, ?)",
                (approval_id, run_id, summary, diff_ref, now),
            )
            self._conn.commit()
        return ApprovalRecord(
            approval_id=approval_id,
            run_id=run_id,
            summary=summary,
            diff_ref=diff_ref,
            created_at=datetime.fromisoformat(now),
        )

    async def resolve_approval(self, approval_id: str, decision: ApprovalDecision) -> bool:
        async with self._lock:
            cur = self._conn.execute(
                "UPDATE approvals SET decision = ? WHERE approval_id = ? AND decision IS NULL",
                (decision.value, approval_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    async def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        async with self._lock:
            row = self._conn.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_approval(row)

    async def list_pending_approvals(self) -> list[ApprovalRecord]:
        async with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM approvals WHERE decision IS NULL ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_approval(r) for r in rows]

    async def count_pending_approvals(self) -> int:
        async with self._lock:
            row = self._conn.execute("SELECT COUNT(*) as cnt FROM approvals WHERE decision IS NULL").fetchone()
        return row["cnt"]

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            repo=row["repo"],
            phases=json.loads(row["phases"]),
            harness=row["harness"],
            current_phase=row["current_phase"],
            status=RunPhase(row["status"]),
            cost=row["cost"],
            diff_content=row["diff_content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_approval(row: sqlite3.Row) -> ApprovalRecord:
        decision = None
        if row["decision"]:
            decision = ApprovalDecision(row["decision"])
        return ApprovalRecord(
            approval_id=row["approval_id"],
            run_id=row["run_id"],
            summary=row["summary"],
            diff_ref=row["diff_ref"],
            created_at=datetime.fromisoformat(row["created_at"]),
            decision=decision,
        )


_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
