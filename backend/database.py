"""Async database operations for Ears."""

import aiosqlite
from pathlib import Path
from config import DATABASE_PATH


class Database:
    """Async database wrapper."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure all tables exist (sync, called once on init)."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Transcripts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                cleaned_text TEXT,
                confidence REAL,
                duration_seconds REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Vocabulary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE NOT NULL,
                frequency INTEGER DEFAULT 1,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'learning',
                explanation TEXT
            )
        """)

        # Word contexts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER,
                context TEXT NOT NULL,
                transcript_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (word_id) REFERENCES vocabulary(id)
            )
        """)

        # Learning progress table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER,
                reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                correct INTEGER DEFAULT 0,
                FOREIGN KEY (word_id) REFERENCES vocabulary(id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_word ON vocabulary(word)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_frequency ON vocabulary(frequency DESC)")

        conn.commit()
        conn.close()

    # ============== Vocabulary ==============

    async def get_vocabulary(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str = None,
        sort: str = "frequency"
    ) -> list:
        """Get vocabulary with optional filtering."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = "SELECT id, word, frequency, status, first_seen, last_seen FROM vocabulary"
            params = []

            if status:
                query += " WHERE status = ?"
                params.append(status)

            if sort == "frequency":
                query += " ORDER BY frequency DESC"
            elif sort == "alphabetical":
                query += " ORDER BY word ASC"
            elif sort == "recent":
                query += " ORDER BY last_seen DESC"
            elif sort == "random":
                query += " ORDER BY RANDOM()"

            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_vocabulary_count(self, status: str = None) -> int:
        """Get total vocabulary count."""
        async with aiosqlite.connect(self.db_path) as db:
            if status:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM vocabulary WHERE status = ?", (status,)
                )
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM vocabulary")
            row = await cursor.fetchone()
            return row[0]

    async def get_word(self, word: str) -> dict:
        """Get single word details."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM vocabulary WHERE word = ?", (word,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_word_contexts(self, word: str, limit: int = 5) -> list:
        """Get example contexts for a word."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT wc.context FROM word_contexts wc
                JOIN vocabulary v ON v.id = wc.word_id
                WHERE v.word = ?
                ORDER BY wc.created_at DESC
                LIMIT ?
            """, (word, limit))
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def set_word_status(self, word: str, status: str):
        """Update word status."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE vocabulary SET status = ? WHERE word = ?",
                (status, word)
            )
            await db.commit()

    async def save_explanation(self, word: str, explanation: str):
        """Save AI explanation for a word (legacy text field)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE vocabulary SET explanation = ? WHERE word = ?",
                (explanation, word)
            )
            await db.commit()

    async def update_word_explanation(self, word: str, explanation_json: str):
        """Save structured JSON explanation for a word."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE vocabulary SET explanation_json = ? WHERE word = ?",
                (explanation_json, word)
            )
            await db.commit()

    # ============== Transcripts ==============

    async def get_transcripts(self, limit: int = 50, offset: int = 0, language: str = None) -> list:
        """Get transcript segments."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT id, timestamp, raw_text, cleaned_text, confidence, duration_seconds,
                       COALESCE(language, 'sv') as language
                FROM transcripts
            """
            params = []
            if language:
                query += " WHERE language = ?"
                params.append(language)
            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_transcript_stats(self) -> dict:
        """Get transcript statistics by language."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM transcripts")
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM transcripts WHERE COALESCE(language, 'sv') = 'sv'"
            )
            swedish = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM transcripts WHERE language = 'en'"
            )
            english = (await cursor.fetchone())[0]

            return {
                "total": total,
                "swedish": swedish,
                "english": english
            }

    async def get_transcript_count(self) -> int:
        """Get total transcript count."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM transcripts")
            row = await cursor.fetchone()
            return row[0]

    # ============== Stats ==============

    async def get_stats(self) -> dict:
        """Get vocabulary statistics."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM vocabulary")
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM vocabulary WHERE status = 'learning'"
            )
            learning = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM vocabulary WHERE status = 'known'"
            )
            known = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT SUM(frequency) FROM vocabulary")
            total_occurrences = (await cursor.fetchone())[0] or 0

            return {
                "total_words": total,
                "learning": learning,
                "known": known,
                "total_occurrences": total_occurrences
            }

    # ============== Learning ==============

    async def get_learning_words(self, count: int = 10) -> list:
        """Get words for learning session."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Get learning words sorted by frequency
            cursor = await db.execute("""
                SELECT v.id, v.word, v.frequency, v.status, v.explanation_json,
                       (SELECT context FROM word_contexts wc WHERE wc.word_id = v.id LIMIT 1) as example
                FROM vocabulary v
                WHERE v.status = 'learning'
                ORDER BY v.frequency DESC
                LIMIT ?
            """, (count,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_learning_sentences(self, count: int = 10) -> list:
        """Get sentences containing learning words."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT DISTINCT t.raw_text, t.cleaned_text
                FROM transcripts t
                ORDER BY RANDOM()
                LIMIT ?
            """, (count,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
