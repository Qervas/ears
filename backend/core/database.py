"""Async database operations for Ears."""

import aiosqlite
from pathlib import Path
from .config import DATABASE_PATH
from .languages import DEFAULT_LANGUAGE


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
                language TEXT DEFAULT 'de',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Vocabulary table - unique constraint on (word, language)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                language TEXT DEFAULT 'de',
                frequency INTEGER DEFAULT 1,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'undiscovered',
                explanation TEXT,
                explanation_json TEXT,
                -- Spaced repetition fields (SM-2 algorithm)
                srs_interval REAL DEFAULT 0,
                srs_ease REAL DEFAULT 2.5,
                srs_next_review TEXT,
                srs_review_count INTEGER DEFAULT 0,
                UNIQUE(word, language)
            )
        """)

        # Migration: Add language column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE vocabulary ADD COLUMN language TEXT DEFAULT 'de'")
            conn.commit()
            print("✓ Added language column to vocabulary table")
        except sqlite3.OperationalError:
            pass

        # Migration: Add language column to transcripts if it doesn't exist
        try:
            cursor.execute("ALTER TABLE transcripts ADD COLUMN language TEXT DEFAULT 'de'")
            conn.commit()
            print("✓ Added language column to transcripts table")
        except sqlite3.OperationalError:
            pass

        # Migration: Add explanation_json column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE vocabulary ADD COLUMN explanation_json TEXT")
            conn.commit()
            print("✓ Added explanation_json column to vocabulary table")
        except sqlite3.OperationalError:
            pass

        # Migration: Add SRS columns if they don't exist
        srs_columns = [
            ("srs_interval", "REAL DEFAULT 0"),
            ("srs_ease", "REAL DEFAULT 2.5"),
            ("srs_next_review", "TEXT"),
            ("srs_review_count", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in srs_columns:
            try:
                cursor.execute(f"ALTER TABLE vocabulary ADD COLUMN {col_name} {col_type}")
                conn.commit()
                print(f"✓ Added {col_name} column to vocabulary table")
            except sqlite3.OperationalError:
                pass

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

        # Settings table (for storing active language, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Initialize default language if not set
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('active_language', ?)", (DEFAULT_LANGUAGE,))

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_word ON vocabulary(word)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_language ON vocabulary(language)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_frequency ON vocabulary(frequency DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_word_lang ON vocabulary(word, language)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_language ON transcripts(language)")

        conn.commit()
        conn.close()

    # ============== Settings ==============

    async def get_setting(self, key: str, default: str = None) -> str:
        """Get a setting value."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_setting(self, key: str, value: str):
        """Set a setting value."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            await db.commit()

    async def get_active_language(self) -> str:
        """Get the currently active language."""
        return await self.get_setting("active_language", DEFAULT_LANGUAGE)

    async def set_active_language(self, language: str):
        """Set the active language."""
        await self.set_setting("active_language", language)

    # ============== Vocabulary ==============

    async def get_vocabulary(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str = None,
        sort: str = "frequency",
        search: str = None,
        language: str = None
    ) -> list:
        """Get vocabulary with optional filtering and search."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = "SELECT id, word, language, frequency, status, first_seen, last_seen, explanation_json FROM vocabulary"
            params = []
            conditions = ["language = ?"]
            params.append(language)

            if status:
                conditions.append("status = ?")
                params.append(status)

            if search:
                conditions.append("word LIKE ?")
                params.append(f"%{search}%")

            query += " WHERE " + " AND ".join(conditions)

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

    async def get_vocabulary_count(self, status: str = None, language: str = None) -> int:
        """Get total vocabulary count."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            if status:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM vocabulary WHERE language = ? AND status = ?",
                    (language, status)
                )
            else:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM vocabulary WHERE language = ?",
                    (language,)
                )
            row = await cursor.fetchone()
            return row[0]

    async def get_word(self, word: str, language: str = None) -> dict:
        """Get single word details."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM vocabulary WHERE word = ? AND language = ?",
                (word, language)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_word_contexts(self, word: str, limit: int = 5, language: str = None) -> list:
        """Get example contexts for a word."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT wc.context FROM word_contexts wc
                JOIN vocabulary v ON v.id = wc.word_id
                WHERE v.word = ? AND v.language = ?
                ORDER BY wc.created_at DESC
                LIMIT ?
            """, (word, language, limit))
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def set_word_status(self, word: str, status: str, language: str = None):
        """Update word status."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE vocabulary SET status = ? WHERE word = ? AND language = ?",
                (status, word, language)
            )
            await db.commit()

    async def save_explanation(self, word: str, explanation: str, language: str = None):
        """Save AI explanation for a word (legacy text field)."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE vocabulary SET explanation = ? WHERE word = ? AND language = ?",
                (explanation, word, language)
            )
            await db.commit()

    async def update_word_explanation(self, word: str, explanation_json: str, language: str = None):
        """Save structured JSON explanation for a word."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE vocabulary SET explanation_json = ? WHERE word = ? AND language = ?",
                (explanation_json, word, language)
            )
            await db.commit()

    # ============== Transcripts ==============

    async def get_transcripts(self, limit: int = 50, offset: int = 0, language: str = None) -> list:
        """Get transcript segments."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = """
                SELECT id, timestamp, raw_text, cleaned_text, confidence, duration_seconds,
                       COALESCE(language, 'de') as language
                FROM transcripts
                WHERE language = ?
                ORDER BY id DESC LIMIT ? OFFSET ?
            """
            cursor = await db.execute(query, (language, limit, offset))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_transcript_stats(self, language: str = None) -> dict:
        """Get transcript statistics for a language."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM transcripts WHERE language = ?",
                (language,)
            )
            total = (await cursor.fetchone())[0]

            return {
                "total": total,
                "language": language
            }

    async def get_transcript_count(self, language: str = None) -> int:
        """Get total transcript count."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM transcripts WHERE language = ?",
                (language,)
            )
            row = await cursor.fetchone()
            return row[0]

    # ============== Stats ==============

    async def get_stats(self, language: str = None) -> dict:
        """Get vocabulary statistics."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM vocabulary WHERE language = ?",
                (language,)
            )
            total = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM vocabulary WHERE language = ? AND status = 'undiscovered'",
                (language,)
            )
            undiscovered = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM vocabulary WHERE language = ? AND status = 'learning'",
                (language,)
            )
            learning = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM vocabulary WHERE language = ? AND status = 'known'",
                (language,)
            )
            known = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT SUM(frequency) FROM vocabulary WHERE language = ?",
                (language,)
            )
            total_occurrences = (await cursor.fetchone())[0] or 0

            return {
                "total_words": total,
                "total": total,  # alias
                "undiscovered": undiscovered,
                "learning": learning,
                "known": known,
                "total_occurrences": total_occurrences,
                "language": language
            }

    # ============== Spaced Repetition ==============

    async def get_due_words(self, count: int = 20, language: str = None) -> list:
        """Get words due for review based on SRS schedule."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT id, word, language, frequency, status, explanation_json,
                       srs_interval, srs_ease, srs_next_review, srs_review_count
                FROM vocabulary
                WHERE language = ?
                  AND status = 'learning'
                  AND (srs_next_review IS NULL OR srs_next_review <= datetime('now'))
                ORDER BY
                    CASE WHEN srs_next_review IS NULL THEN 0 ELSE 1 END,
                    srs_next_review ASC,
                    frequency DESC
                LIMIT ?
            """, (language, count))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_srs_stats(self, language: str = None) -> dict:
        """Get spaced repetition statistics."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM vocabulary
                WHERE language = ?
                  AND status = 'learning'
                  AND (srs_next_review IS NULL OR srs_next_review <= datetime('now'))
            """, (language,))
            due_now = (await cursor.fetchone())[0]

            cursor = await db.execute("""
                SELECT COUNT(*) FROM vocabulary
                WHERE language = ?
                  AND status = 'learning'
                  AND (srs_next_review IS NULL OR date(srs_next_review) <= date('now'))
            """, (language,))
            due_today = (await cursor.fetchone())[0]

            cursor = await db.execute(
                "SELECT COUNT(*) FROM vocabulary WHERE language = ? AND status = 'learning'",
                (language,)
            )
            total_learning = (await cursor.fetchone())[0]

            # Reviews completed today for this language
            cursor = await db.execute("""
                SELECT COUNT(*) FROM learning_progress lp
                JOIN vocabulary v ON v.id = lp.word_id
                WHERE v.language = ? AND date(lp.reviewed_at) = date('now')
            """, (language,))
            reviewed_today = (await cursor.fetchone())[0]

            return {
                "due_now": due_now,
                "due_today": due_today,
                "total_learning": total_learning,
                "reviewed_today": reviewed_today,
                "language": language
            }

    async def record_review(self, word: str, quality: int, language: str = None) -> dict:
        """
        Record a review and update SRS schedule using SM-2 algorithm.
        """
        from datetime import datetime, timedelta

        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                "SELECT id, srs_interval, srs_ease, srs_review_count FROM vocabulary WHERE word = ? AND language = ?",
                (word, language)
            )
            row = await cursor.fetchone()
            if not row:
                return {"error": "Word not found"}

            word_id = row['id']
            interval = row['srs_interval'] or 0
            ease = row['srs_ease'] or 2.5
            review_count = row['srs_review_count'] or 0

            # SM-2 Algorithm
            if quality < 3:
                interval = 0
                review_count = 0
            else:
                if review_count == 0:
                    interval = 1
                elif review_count == 1:
                    interval = 6
                else:
                    interval = interval * ease
                review_count += 1

            ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            ease = max(1.3, ease)

            if interval == 0:
                next_review = datetime.now() + timedelta(minutes=10)
            else:
                next_review = datetime.now() + timedelta(days=interval)

            await db.execute("""
                UPDATE vocabulary
                SET srs_interval = ?, srs_ease = ?, srs_next_review = ?, srs_review_count = ?
                WHERE word = ? AND language = ?
            """, (interval, ease, next_review.isoformat(), review_count, word, language))

            await db.execute("""
                INSERT INTO learning_progress (word_id, correct)
                VALUES (?, ?)
            """, (word_id, 1 if quality >= 3 else 0))

            await db.commit()

            return {
                "word": word,
                "quality": quality,
                "new_interval": interval,
                "new_ease": ease,
                "next_review": next_review.isoformat(),
                "review_count": review_count
            }

    # ============== Learning ==============

    async def get_learning_words(self, count: int = 10, language: str = None) -> list:
        """Get words for learning session."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT v.id, v.word, v.language, v.frequency, v.status, v.explanation_json,
                       (SELECT context FROM word_contexts wc WHERE wc.word_id = v.id LIMIT 1) as example
                FROM vocabulary v
                WHERE v.language = ? AND v.status = 'learning'
                ORDER BY v.frequency DESC
                LIMIT ?
            """, (language, count))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_learning_sentences(self, count: int = 10, language: str = None) -> list:
        """Get sentences containing learning words."""
        if language is None:
            language = await self.get_active_language()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT DISTINCT t.raw_text, t.cleaned_text
                FROM transcripts t
                WHERE t.language = ?
                ORDER BY RANDOM()
                LIMIT ?
            """, (language, count))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
