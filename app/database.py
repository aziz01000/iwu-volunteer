import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "app.db"


def db_path() -> Path:
    configured_path = os.environ.get("DATABASE_PATH")
    if configured_path:
        return Path(configured_path)

    # Vercel Functions have a read-only application filesystem. SQLite can be
    # used for this demo from /tmp, but its data is not durable across function
    # instances or cold starts.
    if os.environ.get("VERCEL"):
        return Path("/tmp/neighborhood-match.db")

    return DEFAULT_DB


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('volunteer', 'coordinator'))
        );

        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            bio TEXT NOT NULL DEFAULT '',
            skills TEXT NOT NULL DEFAULT '[]',
            availability TEXT NOT NULL DEFAULT '[]',
            location TEXT NOT NULL DEFAULT '',
            interests TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            availability TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            filled INTEGER NOT NULL DEFAULT 0,
            coordinator_id INTEGER NOT NULL,
            organization TEXT NOT NULL,
            FOREIGN KEY(coordinator_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            volunteer_id INTEGER NOT NULL,
            opportunity_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'completed')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(volunteer_id) REFERENCES users(id),
            FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
        );

        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=True)


def json_loads(value: str):
    return json.loads(value or "[]")
