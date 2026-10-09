"""Mahalliy bot.db (SQLite) -> Postgres (Supabase) ko'chirish. Bir marta ishga tushiriladi:
    .env ga DATABASE_URL yozing, keyin:  python migrate_to_pg.py
Ulangan akkauntlar ham ko'chadi — Render'da qayta ulanish shart bo'lmaydi."""
import sqlite3

import db
from config import DATABASE_URL, DB_PATH

TABLES = ["connections", "owners", "requests", "messages", "people", "pending_messages", "tg_sessions"]
SERIAL = ["requests", "messages", "pending_messages"]  # id avtomatik oshadigan jadvallar


def main() -> None:
    if not DATABASE_URL:
        raise SystemExit(".env da DATABASE_URL yo'q")
    src = sqlite3.connect(DB_PATH)
    src.row_factory = sqlite3.Row
    db.init()  # Postgres'da jadvallarni yaratadi
    for table in TABLES:
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        for r in rows:
            cols = list(r.keys())
            marks = ",".join("?" * len(cols))
            db._q(
                f"INSERT INTO {table}({','.join(cols)}) VALUES ({marks}) ON CONFLICT DO NOTHING",
                tuple(r[c] for c in cols),
            )
        print(f"{table}: {len(rows)} ta qator")
    for table in SERIAL:  # keyingi id'lar ko'chirilganlardan keyin davom etsin
        db._q(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")
    print("✅ Tayyor")


if __name__ == "__main__":
    main()
