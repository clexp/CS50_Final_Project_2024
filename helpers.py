from flask import redirect, render_template, session, url_for, g
from functools import wraps
import sqlite3


def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                        ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


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
    g.cursor.execute("""
        SELECT t.name 
        FROM tags t
        JOIN note_tags nt ON t.id = nt.tag_id
        WHERE nt.note_id = ?
    """, (note_id,))
    return [row['name'] for row in g.cursor.fetchall()]


def get_all_tags():
    """Get all available tags"""
    g.cursor.execute("SELECT name FROM tags ORDER BY name")
    return [row['name'] for row in g.cursor.fetchall()]


def update_note_tags(note_id, selected_tags):
    """Update tags for a note"""
    try:
        # Remove existing tags
        g.cursor.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        
        # Add new tags
        for tag_name in selected_tags:
            g.cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_id = g.cursor.fetchone()["id"]
            g.cursor.execute("""
                INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)
            """, (note_id, tag_id))
        
        return True
    except sqlite3.Error:
        g.db.rollback()
        return False


def remove_unused_tags():
    """Remove tags that aren't linked to any notes"""
    try:
        # Get all tag IDs that are currently in use (no transaction needed here)
        g.cursor.execute("""
            SELECT DISTINCT tag_id 
            FROM note_tags
        """)
        used_tag_ids = {row['tag_id'] for row in g.cursor.fetchall()}
        print(f"Used tag IDs: {used_tag_ids}")
        
        # Get all tag IDs from tags table
        g.cursor.execute("SELECT id FROM tags")
        all_tag_ids = {row['id'] for row in g.cursor.fetchall()}
        print(f"All tag IDs: {all_tag_ids}")
        
        # Find tags that exist but aren't used
        unused_tag_ids = all_tag_ids - used_tag_ids
        print(f"Unused tag IDs to remove: {unused_tag_ids}")
        
        if unused_tag_ids:
            # Delete unused tags
            placeholders = ','.join('?' * len(unused_tag_ids))
            g.cursor.execute(f"""
                DELETE FROM tags 
                WHERE id IN ({placeholders})
            """, list(unused_tag_ids))
            
            deleted_count = len(unused_tag_ids)
            return deleted_count
            
        return 0

    except sqlite3.Error as e:
        print(f"SQL Error in remove_unused_tags: {str(e)}")
        return None
