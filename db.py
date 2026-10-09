"""Baza: DATABASE_URL bo'lsa — Postgres (Supabase, Render uchun), bo'lmasa — mahalliy SQLite fayl."""
import logging
import sqlite3
import time

from config import DATABASE_URL, DB_PATH, DEFAULT_REMIND_NEW, DEFAULT_REMIND_PROGRESS

log = logging.getLogger(__name__)

_conn = None
_pg = False  # Postgres rejimi

SCHEMA = """
CREATE TABLE IF NOT EXISTS connections (
    id            TEXT PRIMARY KEY,
    owner_id      INTEGER NOT NULL,
    owner_chat_id INTEGER NOT NULL,
    enabled       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS owners (
    owner_id        INTEGER PRIMARY KEY,
    chat_id         INTEGER NOT NULL,
    remind_new      INTEGER NOT NULL,
    remind_progress INTEGER NOT NULL,
    quiet           INTEGER NOT NULL DEFAULT 1,
    summary_msg_id  INTEGER
);
CREATE TABLE IF NOT EXISTS requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id         INTEGER NOT NULL,
    client_id        INTEGER NOT NULL,
    client_name      TEXT NOT NULL,
    username         TEXT,
    status           TEXT NOT NULL,          -- new | progress | done
    created_at       INTEGER NOT NULL,
    updated_at       INTEGER NOT NULL,
    done_at          INTEGER,
    card_msg_id      INTEGER,
    last_reminded_at INTEGER NOT NULL,
    summary          TEXT,                   -- AI xulosasi
    urgent           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_req_owner_status ON requests(owner_id, status);
CREATE INDEX IF NOT EXISTS idx_req_owner_client ON requests(owner_id, client_id);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    text       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_req ON messages(request_id);
CREATE TABLE IF NOT EXISTS people (           -- papkada yo'q, yangi yozgan odamlar
    owner_id      INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    name          TEXT NOT NULL,
    username      TEXT,
    decision      TEXT NOT NULL,              -- pending | client | ignore
    prompt_msg_id INTEGER,
    PRIMARY KEY (owner_id, user_id)
);
CREATE TABLE IF NOT EXISTS pending_messages ( -- "Mijozmi?" javobini kutayotgan xabarlar
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    text       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tg_sessions (       -- ulangan akkauntlar (Telethon StringSession)
    owner_id INTEGER PRIMARY KEY,
    session  TEXT NOT NULL
);
"""

# Postgres'da Telegram ID'lari 32 bitga sig'maydi — hammasi BIGINT
SCHEMA_PG = (
    SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    .replace("INTEGER", "BIGINT")
)


def now() -> int:
    return int(time.time())


def _connect_pg():
    import psycopg
    from psycopg.rows import dict_row

    # prepare_threshold=None — Supabase pooler (pgbouncer) bilan mos ishlashi uchun
    return psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row, prepare_threshold=None)


def init(path: str = DB_PATH) -> None:
    global _conn, _pg
    if DATABASE_URL and path == DB_PATH:
        _pg = True
        _conn = _connect_pg()
        for stmt in SCHEMA_PG.split(";"):
            if stmt.strip():
                _conn.execute(stmt)
        log.info("Baza: Postgres")
        return
    _pg = False
    _conn = sqlite3.connect(path)
    _conn.row_factory = sqlite3.Row
    _conn.executescript(SCHEMA)
    # Eski bazalar uchun yangi ustunlar
    cols = {r["name"] for r in _conn.execute("PRAGMA table_info(requests)")}
    if "summary" not in cols:
        _conn.execute("ALTER TABLE requests ADD COLUMN summary TEXT")
    if "urgent" not in cols:
        _conn.execute("ALTER TABLE requests ADD COLUMN urgent INTEGER NOT NULL DEFAULT 0")
    _conn.commit()


def _q(sql: str, params: tuple = ()):
    global _conn
    if _pg:
        import psycopg

        sql = sql.replace("?", "%s")
        try:
            return _conn.execute(sql, params)
        except psycopg.OperationalError:
            log.warning("Baza ulanishi uzildi — qayta ulanamiz")
            _conn = _connect_pg()
            return _conn.execute(sql, params)
    cur = _conn.execute(sql, params)
    _conn.commit()
    return cur


def _insert(sql: str, params: tuple) -> int:
    """INSERT qilib, yangi qatorning id'sini qaytaradi."""
    if _pg:
        return _q(sql + " RETURNING id", params).fetchone()["id"]
    return _q(sql, params).lastrowid


# --- Business ulanishlar ---

def save_connection(conn_id: str, owner_id: int, owner_chat_id: int, enabled: bool) -> None:
    _q(
        "INSERT INTO connections(id, owner_id, owner_chat_id, enabled) VALUES (?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET owner_id=excluded.owner_id, "
        "owner_chat_id=excluded.owner_chat_id, enabled=excluded.enabled",
        (conn_id, owner_id, owner_chat_id, int(enabled)),
    )


def get_connection(conn_id: str) -> sqlite3.Row | None:
    return _q("SELECT * FROM connections WHERE id=?", (conn_id,)).fetchone()


# --- Egalar (bot ulangan akkauntlar) ---

def ensure_owner(owner_id: int, chat_id: int) -> None:
    _q(
        "INSERT INTO owners(owner_id, chat_id, remind_new, remind_progress) VALUES (?,?,?,?) "
        "ON CONFLICT(owner_id) DO UPDATE SET chat_id=excluded.chat_id",
        (owner_id, chat_id, DEFAULT_REMIND_NEW, DEFAULT_REMIND_PROGRESS),
    )


def get_owner(owner_id: int) -> sqlite3.Row | None:
    return _q("SELECT * FROM owners WHERE owner_id=?", (owner_id,)).fetchone()


def all_owners() -> list[sqlite3.Row]:
    return _q("SELECT * FROM owners").fetchall()


def delete_owner(owner_id: int) -> None:
    _q("DELETE FROM owners WHERE owner_id=?", (owner_id,))


def set_owner_field(owner_id: int, field: str, value) -> None:
    assert field in {"remind_new", "remind_progress", "quiet", "summary_msg_id"}
    _q(f"UPDATE owners SET {field}=? WHERE owner_id=?", (value, owner_id))


# --- Murojaatlar ---

def get_request(req_id: int) -> sqlite3.Row | None:
    return _q("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()


def get_open_request(owner_id: int, client_id: int) -> sqlite3.Row | None:
    return _q(
        "SELECT * FROM requests WHERE owner_id=? AND client_id=? AND status!='done' "
        "ORDER BY id DESC LIMIT 1",
        (owner_id, client_id),
    ).fetchone()


def create_request(owner_id: int, client_id: int, name: str, username: str | None) -> int:
    t = now()
    return _insert(
        "INSERT INTO requests(owner_id, client_id, client_name, username, status, "
        "created_at, updated_at, last_reminded_at) VALUES (?,?,?,?, 'new', ?,?,?)",
        (owner_id, client_id, name, username, t, t, t),
    )


def touch_request(req_id: int, name: str, username: str | None) -> None:
    """Mijoz yana yozdi: ismini yangilaymiz, eslatma hisobini qaytadan boshlaymiz."""
    t = now()
    _q(
        "UPDATE requests SET client_name=?, username=?, updated_at=?, last_reminded_at=? WHERE id=?",
        (name, username, t, t, req_id),
    )


def set_status(req_id: int, status: str) -> None:
    t = now()
    _q(
        "UPDATE requests SET status=?, updated_at=?, last_reminded_at=?, done_at=? WHERE id=?",
        (status, t, t, t if status == "done" else None, req_id),
    )


def set_analysis(req_id: int, summary: str, urgent: bool) -> None:
    _q("UPDATE requests SET summary=?, urgent=? WHERE id=?", (summary, int(urgent), req_id))


def set_card(req_id: int, msg_id: int | None) -> None:
    _q("UPDATE requests SET card_msg_id=? WHERE id=?", (msg_id, req_id))


def list_open(owner_id: int) -> list[sqlite3.Row]:
    return _q(
        "SELECT * FROM requests WHERE owner_id=? AND status!='done' ORDER BY urgent DESC, created_at",
        (owner_id,),
    ).fetchall()


def list_for_day(owner_id: int, day_start: int) -> list[sqlite3.Row]:
    """Bugun ochilganlar + oldindan qolgan bajarilmaganlar."""
    return _q(
        "SELECT * FROM requests WHERE owner_id=? AND (created_at>=? OR status!='done') "
        "ORDER BY created_at",
        (owner_id, day_start),
    ).fetchall()


def mark_reminded(req_ids: list[int]) -> None:
    if not req_ids:
        return
    marks = ",".join("?" * len(req_ids))
    _q(f"UPDATE requests SET last_reminded_at=? WHERE id IN ({marks})", (now(), *req_ids))


# --- Xabarlar ---

def add_message(req_id: int, text: str, created_at: int | None = None) -> int:
    return _insert(
        "INSERT INTO messages(request_id, text, created_at) VALUES (?,?,?)",
        (req_id, text, created_at or now()),
    )


def update_message_text(msg_id: int, text: str) -> None:
    _q("UPDATE messages SET text=? WHERE id=?", (text, msg_id))


def last_messages(req_id: int, limit: int = 5) -> list[sqlite3.Row]:
    rows = _q(
        "SELECT * FROM messages WHERE request_id=? ORDER BY id DESC LIMIT ?", (req_id, limit)
    ).fetchall()
    return list(reversed(rows))


def count_messages(req_id: int) -> int:
    return _q("SELECT COUNT(*) AS n FROM messages WHERE request_id=?", (req_id,)).fetchone()["n"]


def last_text(req_id: int) -> str:
    row = _q("SELECT text FROM messages WHERE request_id=? ORDER BY id DESC LIMIT 1", (req_id,)).fetchone()
    return row["text"] if row else ""


# --- Yangi odamlar ("Mijozmi?") ---

def get_person(owner_id: int, user_id: int) -> sqlite3.Row | None:
    return _q("SELECT * FROM people WHERE owner_id=? AND user_id=?", (owner_id, user_id)).fetchone()


def save_person(owner_id: int, user_id: int, name: str, username: str | None, decision: str) -> None:
    _q(
        "INSERT INTO people(owner_id, user_id, name, username, decision) VALUES (?,?,?,?,?) "
        "ON CONFLICT(owner_id, user_id) DO UPDATE SET name=excluded.name, "
        "username=excluded.username, decision=excluded.decision",
        (owner_id, user_id, name, username, decision),
    )


def set_decision(owner_id: int, user_id: int, decision: str) -> None:
    _q("UPDATE people SET decision=? WHERE owner_id=? AND user_id=?", (decision, owner_id, user_id))


def set_prompt(owner_id: int, user_id: int, msg_id: int | None) -> None:
    _q("UPDATE people SET prompt_msg_id=? WHERE owner_id=? AND user_id=?", (msg_id, owner_id, user_id))


def add_pending(owner_id: int, user_id: int, text: str) -> None:
    _q(
        "INSERT INTO pending_messages(owner_id, user_id, text, created_at) VALUES (?,?,?,?)",
        (owner_id, user_id, text, now()),
    )


def get_pending(owner_id: int, user_id: int) -> list[sqlite3.Row]:
    return _q(
        "SELECT * FROM pending_messages WHERE owner_id=? AND user_id=? ORDER BY id",
        (owner_id, user_id),
    ).fetchall()


def clear_pending(owner_id: int, user_id: int) -> None:
    _q("DELETE FROM pending_messages WHERE owner_id=? AND user_id=?", (owner_id, user_id))


# --- Ulangan akkauntlar (Telethon sessiyasi matn ko'rinishida) ---

def save_session(owner_id: int, session: str) -> None:
    _q(
        "INSERT INTO tg_sessions(owner_id, session) VALUES (?,?) "
        "ON CONFLICT(owner_id) DO UPDATE SET session=excluded.session",
        (owner_id, session),
    )


def all_sessions() -> list:
    return _q("SELECT * FROM tg_sessions").fetchall()


def delete_session(owner_id: int) -> None:
    _q("DELETE FROM tg_sessions WHERE owner_id=?", (owner_id,))
