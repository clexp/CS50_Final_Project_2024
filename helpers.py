from flask import redirect, render_template, session, url_for, g
from functools import wraps
import sqlite3


# Initialize the users database at startup
def init_users_db():
    """Initialize the main users database with the required tables."""
    db = sqlite3.connect("users/users.db")
    db.row_factory = sqlite3.Row
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL,
            has_test_set BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    db.commit()
    db.close()


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def get_note_tags(note_id):
    """Get all tags for a specific note"""
    g.cursor.execute(
        """
        SELECT t.name 
        FROM tags t
        JOIN note_tags nt ON t.id = nt.tag_id
        WHERE nt.note_id = ?
    """,
        (note_id,),
    )
    return [row["name"] for row in g.cursor.fetchall()]


def get_all_tags():
    """Get all available tags"""
    g.cursor.execute("SELECT name FROM tags ORDER BY name")
    return [row["name"] for row in g.cursor.fetchall()]


def update_note_tags(note_id, selected_tags):
    """Update tags for a note"""
    try:
        # Remove existing tags
        g.cursor.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))

        # Add new tags
        for tag_name in selected_tags:
            g.cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_id = g.cursor.fetchone()["id"]
            g.cursor.execute(
                """
                INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)
            """,
                (note_id, tag_id),
            )

        return True
    except sqlite3.Error:
        g.db.rollback()
        return False


def remove_unused_tags():
    """Remove tags that aren't linked to any notes"""
    try:
        # Get all tag IDs that are currently in use (no transaction needed here)
        g.cursor.execute(
            """
            SELECT DISTINCT tag_id 
            FROM note_tags
        """
        )
        used_tag_ids = {row["tag_id"] for row in g.cursor.fetchall()}
        # print(f"Used tag IDs: {used_tag_ids}")

        # Get all tag IDs from tags table
        g.cursor.execute("SELECT id FROM tags")
        all_tag_ids = {row["id"] for row in g.cursor.fetchall()}
        # print(f"All tag IDs: {all_tag_ids}")

        # Find tags that exist but aren't used
        unused_tag_ids = all_tag_ids - used_tag_ids
        # print(f"Unused tag IDs to remove: {unused_tag_ids}")

        if unused_tag_ids:
            # Delete unused tags
            placeholders = ",".join("?" * len(unused_tag_ids))
            g.cursor.execute(
                f"""
                DELETE FROM tags 
                WHERE id IN ({placeholders})
            """,
                list(unused_tag_ids),
            )

            deleted_count = len(unused_tag_ids)
            return deleted_count

        return 0

    except sqlite3.Error as e:
        print(f"SQL Error in remove_unused_tags: {str(e)}")
        return None


def init_user_db(username):
    """Initialize a new user's database with required tables."""
    db = get_user_db(username)
    cursor = db.cursor()

    # Create notes table without user_id since each DB is user-specific
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notes (
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
    """
    )

    # Create tags table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create note_tags junction table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (note_id, tag_id),
            FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )
    """
    )

    db.commit()
    db.close()


def get_user_db(username):
    """Get a connection to a user-specific database."""
    db_path = f"users/data/{username}.db"
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row  # Make sure this line is present
    return db


# Main users database
def get_users_db():
    """Get a connection to the main users database."""
    db = sqlite3.connect("users/users.db")
    db.row_factory = sqlite3.Row
    return db


def import_test_set(user_id):
    """Import test set notes and related data for a user.

    Args:
        user_id: The ID of the user to import test set for

    Returns:
        bool: True if import successful, False otherwise

    Note:
        Requires an active database connection in g.db and g.cursor
        Will modify both user's database and users.db
    """
    try:
        if not g.db or not g.cursor:
            print("No active database connection")
            return False

        # Connect to source database
        source_db = sqlite3.connect("mem_notes.db")
        if not source_db:
            print("Could not connect to source database")
            return False

        source_db.row_factory = sqlite3.Row
        source_cursor = source_db.cursor()

        # First import all tags
        source_cursor.execute("SELECT name FROM tags")
        source_tags = source_cursor.fetchall()
        for tag in source_tags:
            g.cursor.execute(
                """
                INSERT OR IGNORE INTO tags (name, created_at) 
                VALUES (?, CURRENT_TIMESTAMP)
            """,
                (tag["name"],),
            )

        # Add TEST SET tag
        g.cursor.execute(
            """
            INSERT OR IGNORE INTO tags (name, created_at) 
            VALUES ('TEST SET', CURRENT_TIMESTAMP)
        """
        )

        # Get all notes from source
        source_cursor.execute(
            """
            SELECT id, title, content, question, correct_answer,
                   wrong_answer1, wrong_answer2, wrong_answer3
            FROM notes
        """
        )
        notes = source_cursor.fetchall()

        for note in notes:
            # For each note, get its tags
            source_cursor.execute(
                """
                SELECT t.name 
                FROM tags t
                JOIN note_tags nt ON t.id = nt.tag_id
                WHERE nt.note_id = ?
            """,
                (note["id"],),
            )
            note_tags = [row["name"] for row in source_cursor.fetchall()]

            # Add TEST SET tag to the list
            note_tags.append("TEST SET")

            try:
                # Use create_new_note logic
                g.cursor.execute(
                    """
                    INSERT INTO notes (
                        title, content, date, question, correct_answer,
                        wrong_answer1, wrong_answer2, wrong_answer3
                    ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
                """,
                    (
                        note["title"],
                        note["content"],
                        note["question"],
                        note["correct_answer"],
                        note["wrong_answer1"],
                        note["wrong_answer2"],
                        note["wrong_answer3"],
                    ),
                )
                new_note_id = g.cursor.lastrowid

                # Link tags to note
                for tag_name in note_tags:
                    g.cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                    tag_id = g.cursor.fetchone()["id"]
                    g.cursor.execute(
                        """
                        INSERT INTO note_tags (note_id, tag_id, created_at) 
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """,
                        (new_note_id, tag_id),
                    )

            except sqlite3.Error as e:
                print(f"Error importing note {note['title']}: {str(e)}")
                continue

        g.db.commit()

        # Update user's has_test_set flag
        users_db = sqlite3.connect("users/users.db")
        users_cursor = users_db.cursor()
        try:
            users_cursor.execute(
                "UPDATE users SET has_test_set = 1 WHERE id = ?", (user_id,)
            )
            users_db.commit()
            session["has_test_set"] = True
        finally:
            users_db.close()

        source_db.close()
        return True

    except sqlite3.Error as e:
        g.db.rollback()
        if "source_db" in locals():
            source_db.close()
        print(f"Error importing test set: {str(e)}")
        return False
