"""Check database contents."""
import sqlite3

conn = sqlite3.connect('transcripts.db')
cursor = conn.cursor()

print("=== Top 10 words by frequency ===")
cursor.execute('SELECT word, frequency, status FROM vocabulary ORDER BY frequency DESC LIMIT 10')
for row in cursor.fetchall():
    print(f"  {row[0]:20} freq={row[1]:4}  status={row[2]}")

print("\n=== Counts ===")
cursor.execute('SELECT COUNT(*) FROM vocabulary')
print(f"Total unique words in vocabulary table: {cursor.fetchone()[0]}")

cursor.execute('SELECT COUNT(*) FROM vocabulary WHERE status = "learning"')
print(f"Words with status 'learning': {cursor.fetchone()[0]}")

cursor.execute('SELECT COUNT(*) FROM vocabulary WHERE status = "known"')
print(f"Words with status 'known': {cursor.fetchone()[0]}")

cursor.execute('SELECT COUNT(*) FROM vocabulary WHERE status = "new"')
print(f"Words with status 'new' (old): {cursor.fetchone()[0]}")

cursor.execute('SELECT SUM(frequency) FROM vocabulary')
print(f"Total occurrences (sum of frequencies): {cursor.fetchone()[0]}")

cursor.execute('SELECT DISTINCT status FROM vocabulary')
print(f"\nDistinct statuses in DB: {[r[0] for r in cursor.fetchall()]}")

conn.close()
