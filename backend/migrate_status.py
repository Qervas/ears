"""Migrate old 'new' status to 'learning'."""
import sqlite3

conn = sqlite3.connect('transcripts.db')
cursor = conn.cursor()

# Update all 'new' status to 'learning'
cursor.execute("UPDATE vocabulary SET status = 'learning' WHERE status = 'new'")
updated = cursor.rowcount

conn.commit()
conn.close()

print(f"Migrated {updated} words from 'new' to 'learning'")
