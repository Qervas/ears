"""Zero-knowledge vocabulary builder from transcripts."""

import sqlite3
import re
from collections import Counter
from pathlib import Path
from config import DATABASE_PATH


def init_vocab_db():
    """Initialize vocabulary tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Words table - each unique word/token
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE NOT NULL,
            frequency INTEGER DEFAULT 1,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'learning'  -- learning, known
        )
    """)

    # Fix any words with NULL or invalid status - set them to 'learning'
    cursor.execute("""
        UPDATE vocabulary
        SET status = 'learning'
        WHERE status IS NULL OR status NOT IN ('learning', 'known')
    """)
    if cursor.rowcount > 0:
        print(f"Fixed {cursor.rowcount} words with invalid status -> 'learning'")

    # Contexts table - example sentences for each word
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_contexts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER,
            context TEXT NOT NULL,
            transcript_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES vocabulary(id),
            FOREIGN KEY (transcript_id) REFERENCES transcripts(id)
        )
    """)

    # Create index for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_word ON vocabulary(word)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_frequency ON vocabulary(frequency DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary(status)")

    conn.commit()
    conn.close()


def tokenize(text: str) -> list[str]:
    """Extract words from text. Keeps Swedish characters."""
    # Swedish alphabet includes å, ä, ö
    # Lowercase and extract words
    text = text.lower()
    words = re.findall(r"[a-zåäöéèêëàâùûîïôœç]+", text)
    # Filter very short words and numbers
    words = [w for w in words if len(w) >= 2]
    return words


def add_word(word: str, context: str, transcript_id: int = None):
    """Add or update a word in vocabulary."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Try to insert or update frequency
    # New words get status='learning', existing words keep their status
    cursor.execute("""
        INSERT INTO vocabulary (word, frequency, status, last_seen)
        VALUES (?, 1, 'learning', CURRENT_TIMESTAMP)
        ON CONFLICT(word) DO UPDATE SET
            frequency = frequency + 1,
            last_seen = CURRENT_TIMESTAMP
    """, (word,))

    # Get word id
    cursor.execute("SELECT id FROM vocabulary WHERE word = ?", (word,))
    word_id = cursor.fetchone()[0]

    # Add context (limit to 5 contexts per word to save space)
    cursor.execute("""
        SELECT COUNT(*) FROM word_contexts WHERE word_id = ?
    """, (word_id,))
    context_count = cursor.fetchone()[0]

    if context_count < 5:
        cursor.execute("""
            INSERT INTO word_contexts (word_id, context, transcript_id)
            VALUES (?, ?, ?)
        """, (word_id, context[:500], transcript_id))  # Limit context length

    conn.commit()
    conn.close()


def build_from_transcripts(swedish_only: bool = True):
    """Build vocabulary from all transcripts.

    Args:
        swedish_only: If True, only process Swedish segments (skip English)
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Get all transcripts - include language column if it exists
    try:
        cursor.execute("""
            SELECT id, raw_text, cleaned_text, language FROM transcripts
        """)
        transcripts = cursor.fetchall()
        has_language = True
    except sqlite3.OperationalError:
        # Old schema without language column
        cursor.execute("""
            SELECT id, raw_text, cleaned_text FROM transcripts
        """)
        transcripts = [(t[0], t[1], t[2], 'sv') for t in cursor.fetchall()]
        has_language = False

    conn.close()

    if not transcripts:
        print("No transcripts found. Record some audio first!")
        return

    total_segments = len(transcripts)
    sv_segments = sum(1 for t in transcripts if t[3] == 'sv')
    en_segments = total_segments - sv_segments

    print(f"Found {total_segments} transcript segments (SV: {sv_segments}, EN: {en_segments})")

    if swedish_only:
        print("Building vocabulary from Swedish segments only...")
    else:
        print("Building vocabulary from all segments...")

    word_count = 0
    skipped_segments = 0

    for transcript_id, raw_text, cleaned_text, language in transcripts:
        # Skip English segments if swedish_only
        if swedish_only and language == 'en':
            skipped_segments += 1
            continue

        # Prefer cleaned text if available
        text = cleaned_text or raw_text
        if not text:
            continue

        words = tokenize(text)
        for word in words:
            add_word(word, text, transcript_id)
            word_count += 1

    print(f"Processed {word_count} word occurrences")
    if skipped_segments > 0:
        print(f"Skipped {skipped_segments} English segments")

    # Show stats
    show_stats()


def show_stats():
    """Show vocabulary statistics."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM vocabulary")
    total_words = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(frequency) FROM vocabulary")
    total_occurrences = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM vocabulary WHERE status = 'learning'")
    learning_words = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vocabulary WHERE status = 'known'")
    known_words = cursor.fetchone()[0]

    conn.close()

    print("\n" + "=" * 50)
    print("VOCABULARY STATISTICS")
    print("=" * 50)
    print(f"  Unique words:     {total_words}")
    print(f"  Total occurrences: {total_occurrences}")
    print(f"  Learning:         {learning_words}")
    print(f"  Known:            {known_words}")
    print("=" * 50)


def get_top_words(limit: int = 50, status: str = None) -> list:
    """Get most frequent words."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    if status:
        cursor.execute("""
            SELECT word, frequency, status FROM vocabulary
            WHERE status = ?
            ORDER BY frequency DESC
            LIMIT ?
        """, (status, limit))
    else:
        cursor.execute("""
            SELECT word, frequency, status FROM vocabulary
            ORDER BY frequency DESC
            LIMIT ?
        """, (limit,))

    results = cursor.fetchall()
    conn.close()
    return results


def get_word_contexts(word: str) -> list:
    """Get example contexts for a word."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT wc.context FROM word_contexts wc
        JOIN vocabulary v ON v.id = wc.word_id
        WHERE v.word = ?
        ORDER BY wc.created_at DESC
        LIMIT 5
    """, (word,))

    results = [row[0] for row in cursor.fetchall()]
    conn.close()
    return results


def set_word_status(word: str, status: str):
    """Set the learning status of a word."""
    if status not in ('learning', 'known'):
        print(f"Invalid status: {status}. Use 'learning' or 'known'.")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE vocabulary SET status = ? WHERE word = ?
    """, (status, word))

    conn.commit()
    conn.close()
    print(f"'{word}' marked as {status}")


def export_vocabulary(output_path: str = "vocabulary.txt", min_frequency: int = 1):
    """Export vocabulary to text file."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT word, frequency, status FROM vocabulary
        WHERE frequency >= ?
        ORDER BY frequency DESC
    """, (min_frequency,))

    results = cursor.fetchall()
    conn.close()

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("word\tfrequency\tstatus\n")
        for word, freq, status in results:
            f.write(f"{word}\t{freq}\t{status}\n")

    print(f"Exported {len(results)} words to {output_path}")


def interactive_review():
    """Interactive vocabulary review session."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Get learning words sorted by frequency (learn common words first)
    cursor.execute("""
        SELECT word, frequency FROM vocabulary
        WHERE status = 'learning'
        ORDER BY frequency DESC
        LIMIT 20
    """)
    words = cursor.fetchall()
    conn.close()

    if not words:
        print("No words to review!")
        return

    print("\n" + "=" * 50)
    print("VOCABULARY REVIEW")
    print("Commands: [k]nown, [s]kip, [q]uit")
    print("=" * 50)

    for word, freq in words:
        contexts = get_word_contexts(word)

        print(f"\n>>> {word.upper()} (seen {freq}x)")
        if contexts:
            print("Example:", contexts[0][:100])

        action = input("[k/s/q]: ").strip().lower()

        if action == 'k':
            set_word_status(word, 'known')
        elif action == 'q':
            break
        # 's' or anything else = skip

    print("\nReview session ended.")
    show_stats()


def main():
    import sys

    init_vocab_db()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python vocabulary.py build     - Build vocab from transcripts")
        print("  python vocabulary.py stats     - Show statistics")
        print("  python vocabulary.py top [N]   - Show top N words")
        print("  python vocabulary.py review    - Interactive review session")
        print("  python vocabulary.py lookup <word>  - Look up a word")
        print("  python vocabulary.py export    - Export to vocabulary.txt")
        return

    cmd = sys.argv[1]

    if cmd == "build":
        build_from_transcripts()

    elif cmd == "stats":
        show_stats()

    elif cmd == "top":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        words = get_top_words(limit)
        print(f"\nTop {limit} words by frequency:")
        print("-" * 40)
        for i, (word, freq, status) in enumerate(words, 1):
            status_mark = {"learning": "→", "known": "✓"}.get(status, "?")
            print(f"{i:3}. {word:20} {freq:5}x  {status_mark}")

    elif cmd == "review":
        interactive_review()

    elif cmd == "lookup":
        if len(sys.argv) < 3:
            print("Usage: python vocabulary.py lookup <word>")
            return
        word = sys.argv[2].lower()
        contexts = get_word_contexts(word)
        if contexts:
            print(f"\n'{word}' - Example contexts:")
            for i, ctx in enumerate(contexts, 1):
                print(f"  {i}. {ctx}")
        else:
            print(f"Word '{word}' not found in vocabulary")

    elif cmd == "export":
        export_vocabulary()

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
