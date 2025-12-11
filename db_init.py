import sqlite3
from pathlib import Path

DB_PATH = Path("instance/expenses.db")
DB_PATH.parent.mkdir(exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            date TEXT NOT NULL,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f"Initialized DB at {DB_PATH.resolve()}")

if __name__ == "__main__":
    init_db()
