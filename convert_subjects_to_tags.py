import sqlite3

def convert_subjects_topics_to_tags():
    """Convert subjects and topics to tags in mem_notes.db"""
    conn = sqlite3.connect("mem_notes.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create tags table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create note_tags table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (note_id, tag_id),
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    """)
    
    # Get all unique subjects and topics
    cursor.execute("SELECT DISTINCT subject FROM notes WHERE subject IS NOT NULL AND subject != ''")
    subjects = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT topic FROM notes WHERE topic IS NOT NULL AND topic != ''")
    topics = cursor.fetchall()
    
    # Insert subjects as tags with "Subject:" prefix
    for subject in subjects:
        try:
            cursor.execute("INSERT INTO tags (name) VALUES (?)", 
                         (f"Subject: {subject['subject']}",))
        except sqlite3.IntegrityError:
            pass  # Tag already exists
    
    # Insert topics as tags with "Topic:" prefix
    for topic in topics:
        try:
            cursor.execute("INSERT INTO tags (name) VALUES (?)", 
                         (f"Topic: {topic['topic']}",))
        except sqlite3.IntegrityError:
            pass  # Tag already exists
    
    # Create note_tags relationships
    # For subjects
    cursor.execute("""
        INSERT INTO note_tags (note_id, tag_id)
        SELECT n.id, t.id
        FROM notes n
        JOIN tags t ON t.name = 'Subject: ' || n.subject
        WHERE n.subject IS NOT NULL AND n.subject != ''
    """)
    
    # For topics
    cursor.execute("""
        INSERT INTO note_tags (note_id, tag_id)
        SELECT n.id, t.id
        FROM notes n
        JOIN tags t ON t.name = 'Topic: ' || n.topic
        WHERE n.topic IS NOT NULL AND n.topic != ''
    """)
    
    # Create backup of notes table
    cursor.execute("CREATE TABLE notes_backup AS SELECT * FROM notes")
    
    # Create new notes table without subject and topic
    cursor.execute("""
        CREATE TABLE notes_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            question TEXT,
            correct_answer TEXT,
            wrong_answer1 TEXT,
            wrong_answer2 TEXT,
            wrong_answer3 TEXT,
            times_challenged INTEGER DEFAULT 0,
            times_correct INTEGER DEFAULT 0,
            last_tested DATETIME
        )
    """)
    
    # Copy data to new table
    cursor.execute("""
        INSERT INTO notes_new (
            id, title, content, date, question, correct_answer,
            wrong_answer1, wrong_answer2, wrong_answer3,
            times_challenged, times_correct, last_tested
        )
        SELECT 
            id, title, content, date, question, correct_answer,
            wrong_answer1, wrong_answer2, wrong_answer3,
            times_challenged, times_correct, last_tested
        FROM notes
    """)
    
    # Drop old table and rename new one
    cursor.execute("DROP TABLE notes")
    cursor.execute("ALTER TABLE notes_new RENAME TO notes")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    convert_subjects_topics_to_tags()
    print("Conversion completed successfully!") 