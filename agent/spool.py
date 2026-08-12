"""
Local SQLite spool for durable metric buffering during WAN outages.

Design:
  - Events are written to spool BEFORE sending to the API
  - On successful API response, the event is marked sent
  - On agent restart, unsent events are replayed
  - The API's idempotent event_id enforcement prevents duplicate rows

Schema:
  pending_events(event_id TEXT PK, payload TEXT, created_at TEXT, sent INTEGER DEFAULT 0)
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SPOOL_PATH = Path(os.environ.get("SPOOL_PATH", "/var/lib/edgeguard/spool.db"))


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_events (
            event_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sent INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_pending_unsent ON pending_events(sent)")
    conn.commit()


@contextmanager
def _connect():
    SPOOL_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SPOOL_PATH))
    try:
        _init_db(conn)
        yield conn
    finally:
        conn.close()


def enqueue(event_id: str, payload: dict) -> None:
    """Write an event to the spool. Idempotent — duplicate event_id is silently ignored."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO pending_events (event_id, payload, created_at) VALUES (?, ?, ?)",
            (event_id, json.dumps(payload), datetime.now(UTC).isoformat()),
        )
        conn.commit()


def drain(limit: int = 100) -> list[tuple[str, dict]]:
    """Return up to `limit` unsent events as (event_id, payload) tuples."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT event_id, payload FROM pending_events WHERE sent = 0 ORDER BY created_at LIMIT ?",
            (limit,),
        ).fetchall()
    return [(row[0], json.loads(row[1])) for row in rows]


def mark_sent(event_id: str) -> None:
    """Mark a single event as successfully delivered."""
    with _connect() as conn:
        conn.execute("UPDATE pending_events SET sent = 1 WHERE event_id = ?", (event_id,))
        conn.commit()


def pending_count() -> int:
    """Return the number of unsent events (useful for monitoring)."""
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM pending_events WHERE sent = 0").fetchone()
    return row[0] if row else 0


def purge_sent(older_than_days: int = 7) -> int:
    """Remove sent events older than N days. Returns number of rows deleted."""
    cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta

    cutoff -= timedelta(days=older_than_days)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM pending_events WHERE sent = 1 AND created_at < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
        return cur.rowcount
