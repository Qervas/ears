"""Migration: Add explanation_json column to vocabulary table."""

import sqlite3
from pathlib import Path
from config import DATABASE_PATH

def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(vocabulary)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'explanation_json' not in columns:
        print("Adding explanation_json column...")
        cursor.execute("ALTER TABLE vocabulary ADD COLUMN explanation_json TEXT")
        conn.commit()
        print("✓ Column added successfully")
    else:
        print("✓ Column already exists")

    conn.close()

if __name__ == "__main__":
    migrate()
