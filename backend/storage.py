"""SQLite storage for transcripts."""

import sqlite3
from datetime import datetime
from pathlib import Path
from config import DATABASE_PATH


def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            cleaned_text TEXT,
            confidence REAL,
            duration_seconds REAL,
            language TEXT DEFAULT 'sv',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add language column if it doesn't exist (migration for existing DBs)
    try:
        cursor.execute("ALTER TABLE transcripts ADD COLUMN language TEXT DEFAULT 'sv'")
    except sqlite3.OperationalError:
        pass  # Column already exists

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            total_segments INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def save_transcript(raw_text: str, confidence: float = None, duration: float = None, language: str = "sv") -> int:
    """Save a transcript segment. Returns the ID."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO transcripts (timestamp, raw_text, confidence, duration_seconds, language)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), raw_text, confidence, duration, language))

    transcript_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return transcript_id


def update_cleaned_text(transcript_id: int, cleaned_text: str):
    """Update a transcript with LLM-cleaned text."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE transcripts SET cleaned_text = ? WHERE id = ?
    """, (cleaned_text, transcript_id))

    conn.commit()
    conn.close()


def get_uncleaned_transcripts(limit: int = 50) -> list:
    """Get transcripts that haven't been cleaned yet."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, raw_text FROM transcripts
        WHERE cleaned_text IS NULL
        ORDER BY id ASC
        LIMIT ?
    """, (limit,))

    results = cursor.fetchall()
    conn.close()
    return results


def get_all_transcripts(cleaned_only: bool = False) -> list:
    """Get all transcripts."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    if cleaned_only:
        cursor.execute("""
            SELECT id, timestamp, raw_text, cleaned_text
            FROM transcripts WHERE cleaned_text IS NOT NULL
            ORDER BY id ASC
        """)
    else:
        cursor.execute("""
            SELECT id, timestamp, raw_text, cleaned_text
            FROM transcripts ORDER BY id ASC
        """)

    results = cursor.fetchall()
    conn.close()
    return results


def export_corpus(output_path: str = "corpus.txt", use_cleaned: bool = True):
    """Export all transcripts to a text file."""
    transcripts = get_all_transcripts()

    with open(output_path, "w", encoding="utf-8") as f:
        for id_, timestamp, raw_text, cleaned_text in transcripts:
            text = cleaned_text if (use_cleaned and cleaned_text) else raw_text
            f.write(f"[{timestamp}] {text}\n")

    return output_path


# Initialize DB on import
init_db()
