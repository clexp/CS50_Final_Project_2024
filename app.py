import os
import sqlite3
from flask_session import Session
from datetime import datetime
from random import shuffle
from math import ceil

from flask import Flask, flash, redirect, render_template, request, session, url_for, g
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure the users directory structure exists
if not os.path.exists('users'):
    os.makedirs('users')
if not os.path.exists('users/data'):
    os.makedirs('users/data')

# Initialize the users database at startup
def init_users_db():
    """Initialize the main users database"""
    db = sqlite3.connect("users/users.db")
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    db.commit()
    db.close()

# Initialize users database at startup
init_users_db()

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    try:
        # Get total count of notes
        g.cursor.execute("SELECT COUNT(*) as count FROM notes")
        total_notes = g.cursor.fetchone()['count']
        
        # Get recent notes
        g.cursor.execute("""
            SELECT * FROM notes 
            ORDER BY date DESC 
            LIMIT 10
        """)
        notes = g.cursor.fetchall()
        
        return render_template("index.html", 
                             notes=notes, 
                             total_notes=total_notes,
                             show_import=total_notes == 0)
    except (AttributeError, sqlite3.OperationalError):
        return redirect(url_for("login"))


@app.route("/old_record_new_note", methods=["GET", "POST"])
@login_required
def create_new_note():
    """Create a new note"""
    if request.method == "GET":
        return render_template("create.html")
    
    if request.method == "POST":
        cursor.execute("""
            INSERT INTO notes (title, content, user_id) 
            VALUES (?, ?, ?)
        """, (
            request.form.get("title"),
            request.form.get("content"),
            session["user_id"]
        ))
        db.commit()
        return render_template("index.html")

    return render_template("index.html")



@app.route("/search", methods=["GET"])
@login_required
def search():
    """Search notes."""
    query = request.args.get("q", "").strip()
    selected_tags = request.args.getlist("tags")  # Get selected tag IDs
    
    # Get all available tags for the search form
    g.cursor.execute("SELECT * FROM tags ORDER BY name")
    all_tags = g.cursor.fetchall()
    
    # Build the search query
    search_query = """
        SELECT DISTINCT n.* FROM notes n
    """
    params = []
    
    # Add tag join if tags are selected
    if selected_tags:
        search_query += """
            JOIN note_tags nt ON n.id = nt.note_id
            WHERE nt.tag_id IN ({})
        """.format(','.join('?' * len(selected_tags)))
        params.extend(selected_tags)
    else:
        search_query += " WHERE 1=1"
    
    # Add text search if query exists
    if query:
        if selected_tags:
            search_query += " AND"
        else:
            search_query += " AND"
        search_query += """
            (title LIKE ? OR
             content LIKE ? OR
             subject LIKE ? OR
             topic LIKE ?)
        """
        params.extend([f"%{query}%"] * 4)
    
    search_query += " ORDER BY date DESC"
    
    g.cursor.execute(search_query, params)
    notes = g.cursor.fetchall()
    
    return render_template(
        "search.html",
        notes=notes,
        query=query,
        all_tags=all_tags,
        selected_tags=selected_tags
    )


@app.route("/display_note/<int:note_id>")
@login_required
def display_note(note_id):
    """Display a single note."""
    # Get note
    g.cursor.execute("""
        SELECT * FROM notes 
        WHERE id = ?
    """, (note_id,))
    
    note = g.cursor.fetchone()
    
    if note is None:
        flash("Note not found!")
        return redirect("/")
    
    # Get tags for this note
    g.cursor.execute("""
        SELECT tags.name 
        FROM tags 
        JOIN note_tags ON tags.id = note_tags.tag_id 
        WHERE note_tags.note_id = ?
        ORDER BY tags.name
    """, (note_id,))
    
    tags = g.cursor.fetchall()
        
    return render_template("display_note.html", note=note, tags=tags)




@app.route("/edit_note/<int:note_id>", methods=["GET", "POST"])
@login_required
def edit_note(note_id):
    """Edit an existing note."""
    if request.method == "POST":
        # Update note
        title = request.form.get("title")
        content = request.form.get("content")
        subject = request.form.get("subject")
        topic = request.form.get("topic")
        question = request.form.get("question")
        correct_answer = request.form.get("correct_answer")
        wrong_answer1 = request.form.get("wrong_answer1")
        wrong_answer2 = request.form.get("wrong_answer2")
        wrong_answer3 = request.form.get("wrong_answer3")

        if not title:
            return apology("must provide title")
        if not content:
            return apology("must provide content")

        g.cursor.execute("""
            UPDATE notes 
            SET title = ?, content = ?, subject = ?, topic = ?,
                question = ?, correct_answer = ?,
                wrong_answer1 = ?, wrong_answer2 = ?, wrong_answer3 = ?
            WHERE id = ?
        """, (
            title, content, subject, topic,
            question, correct_answer,
            wrong_answer1, wrong_answer2, wrong_answer3,
            note_id
        ))
        
        # Update tags
        selected_tags = request.form.getlist("tags")
        
        # Remove existing tag associations
        g.cursor.execute("DELETE FROM note_tags WHERE note_id = ?", (note_id,))
        
        # Add new tag associations
        for tag_id in selected_tags:
            g.cursor.execute("""
                INSERT INTO note_tags (note_id, tag_id)
                VALUES (?, ?)
            """, (note_id, tag_id))
        
        g.db.commit()
        flash("Note updated successfully!")
        return redirect(url_for("display_note", note_id=note_id))

    # GET request - show edit form with current note data
    g.cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
    note = g.cursor.fetchone()
    
    if note is None:
        flash("Note not found!")
        return redirect("/")
    
    # Get all tags, ordered alphabetically
    g.cursor.execute("SELECT * FROM tags ORDER BY name")
    tags = g.cursor.fetchall()
    
    # Get currently selected tags for this note
    g.cursor.execute("""
        SELECT tag_id FROM note_tags 
        WHERE note_id = ?
    """, (note_id,))
    selected_tag_ids = [row['tag_id'] for row in g.cursor.fetchall()]
        
    return render_template("edit_note.html", 
                         note=note, 
                         tags=tags, 
                         selected_tag_ids=selected_tag_ids)



@app.route("/delete_note/<int:note_id>", methods=['GET', 'POST'])
# @login_required
def delete_note(note_id):
    """Allow deletion of selected note"""
    # user_id = int(session["user_id"])
    if request.method == "POST":
        print("went to delete in POST") 
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        db.commit()
        return redirect(url_for('search'))
    cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
    mem_note = cursor.fetchone()
    return render_template("delete_note.html", this_note=mem_note)


@app.route("/test")
# @login_required
def test():
    """Enter test parameter"""
    # user_id = int(session["user_id"])
    return render_template("test.html")




@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        
        users_db = get_users_db()
        cursor = users_db.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        users_db.close()

        if user and check_password_hash(user["hash"], request.form.get("password")):
            session["user_id"] = user["id"]
            session["username"] = username  # Store username for database access
            return redirect("/")

        return apology("invalid username and/or password")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")




@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Input validation
        if not username:
            return apology("must provide username")
        if not password:
            return apology("must provide password")
        if not confirmation:
            return apology("must confirm password")
        if password != confirmation:
            return apology("must confirm password")

        # Connect to users database
        users_db = get_users_db()
        users_cursor = users_db.cursor()

        # Check if username exists
        users_cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if users_cursor.fetchone():
            users_db.close()
            return apology("username already exists")

        # Create new user
        hash = generate_password_hash(password)
        users_cursor.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            (username, hash)
        )
        users_db.commit()

        # Get the user id
        users_cursor.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        )
        user = users_cursor.fetchone()
        users_db.close()

        # Initialize user's database
        init_user_db(username)

        # Log user in
        session["user_id"] = user["id"]
        session["username"] = username

        # Initialize the user's database connection for this request
        g.db = get_user_db(username)
        g.cursor = g.db.cursor()
        
        return redirect("/")

    return render_template("register.html")




@app.route("/change_password", methods=["GET", "POST"])
#@login_required
def change_password():
    user_id = int(session["user_id"])
    """Change password."""
    if request.method == "GET":
        return render_template("change_password.html")

    if request.method == "POST":
        old_password = request.form.get("old_password")
        hash_record = db.execute("SELECT hash FROM users WHERE id = ?; ", user_id)[0]['hash']
        if not check_password_hash(hash_record, old_password):
            return apology("incorrect password")
        new_password_1 = request.form.get("password1")
        new_password_2 = request.form.get("password2")
        if new_password_1 != new_password_2:
            return apology("New passwords not matching")
        new_hash = generate_password_hash(new_password_1)
        if 1 == db.execute("UPDATE users SET hash = ? WHERE id = ?;",
                           new_hash,
                           user_id):
            session.clear()
            # this is non ideal, as if it updates multiple rows, this is not flagged
            print("cleared session, went to index, did not like usd?")
            return redirect("/")
    return apology("Password update error")




@app.route("/flashcards")
#@login_required
def flashcards():
    """Show flashcard practice page"""
    cursor.execute("""
        SELECT id, title, subject, topic, question, correct_answer, 
               wrong_answer1, wrong_answer2, wrong_answer3 
        FROM notes 
        WHERE question IS NOT NULL 
        AND correct_answer IS NOT NULL
        ORDER BY RANDOM() 
        LIMIT 1
    """)
    card = cursor.fetchone()
    
    if card:
        # Create list of all answers and shuffle them
        answers = [
            card['correct_answer'],
            card['wrong_answer1'],
            card['wrong_answer2'],
            card['wrong_answer3']
        ]
        random.shuffle(answers)
        
        return render_template("flashcards.html", card=card, shuffled_answers=answers)
    
    return render_template("flashcards.html", card=None)

@app.route("/record_new_note", methods=["GET", "POST"])
@login_required
def record_new_note():
    """Record a new note."""
    if request.method == "POST":
        # Get form data
        title = request.form.get("title")
        content = request.form.get("content")
        subject = request.form.get("subject")
        topic = request.form.get("topic")
        question = request.form.get("question")
        correct_answer = request.form.get("correct_answer")
        wrong_answer1 = request.form.get("wrong_answer1")
        wrong_answer2 = request.form.get("wrong_answer2")
        wrong_answer3 = request.form.get("wrong_answer3")
        # Get selected tags as list
        selected_tags = request.form.getlist("tags")

        if not title:
            return apology("must provide title")
        if not content:
            return apology("must provide content")

        # Insert note
        g.cursor.execute("""
            INSERT INTO notes (
                title, content, subject, topic,
                question, correct_answer,
                wrong_answer1, wrong_answer2, wrong_answer3
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, content, subject, topic,
            question, correct_answer,
            wrong_answer1, wrong_answer2, wrong_answer3
        ))
        
        # Get the id of the newly inserted note
        note_id = g.cursor.lastrowid
        
        # Insert tag relationships
        if selected_tags:
            for tag_id in selected_tags:
                g.cursor.execute("""
                    INSERT INTO note_tags (note_id, tag_id)
                    VALUES (?, ?)
                """, (note_id, tag_id))
        
        g.db.commit()
        flash("Note saved successfully!")
        return redirect("/")

    # GET request - show the form
    # Get all available tags
    g.cursor.execute("SELECT * FROM tags ORDER BY name")
    tags = g.cursor.fetchall()
    #print(f"Debug - Found tags: {tags}")  # Debug output
    
    return render_template("create.html", tags=tags)


@app.route("/start_test", methods=["GET", "POST"])
@login_required
def start_test():
    """Start a new test."""
    if request.method == "GET":
        return render_template("test_setup.html")

    # Get test parameters
    n = int(request.form.get("question_count", 10))
    filter_type = request.form.get("filter_type", "random")
    
    # Build query based on filter type
    base_query = """
        SELECT id, title, subject, topic, question, correct_answer, 
               wrong_answer1, wrong_answer2, wrong_answer3 
        FROM notes 
        WHERE question IS NOT NULL 
        AND correct_answer IS NOT NULL
    """
    
    if filter_type == "weakest":
        base_query += """
            AND times_challenged > 0 
            ORDER BY CAST(times_correct AS FLOAT) / times_challenged ASC
            LIMIT ?
        """
    elif filter_type == "untested":
        base_query += """
            AND times_challenged = 0 
            ORDER BY RANDOM()
            LIMIT ?
        """
    else:  # random
        base_query += """
            ORDER BY RANDOM()
            LIMIT ?
        """
    
    # Get questions
    g.cursor.execute(base_query, (n,))
    questions = g.cursor.fetchall()
    
    if not questions:
        flash("No suitable questions found for testing!")
        return redirect(url_for("start_test"))
    
    # Store test data in session
    session["test_questions"] = [dict(q) for q in questions]
    session["current_question"] = 0
    session["score"] = 0
    
    return redirect(url_for("show_test_question"))

@app.route("/show_test_question")
#@login_required
def show_test_question():
    if "test_questions" not in session:
        return redirect(url_for("test_setup"))
    
    questions = session["test_questions"]
    current = session["current_question"]
    
    if current >= len(questions):
        # Test is complete
        return render_template("test_complete.html", 
                             score=session["score"],
                             total=len(questions))
    
    question = questions[current]
    answers = [
        question["correct_answer"],
        question["wrong_answer1"],
        question["wrong_answer2"],
        question["wrong_answer3"]
    ]
    shuffle(answers)
    
    return render_template("test_question.html", 
                         question=question,
                         shuffled_answers=answers,
                         progress={"current": current + 1, 
                                 "total": len(questions)})

@app.route("/check_answer/<int:question_id>", methods=["POST"])
#@login_required
def check_answer(question_id):
    selected_answer = request.form.get("answer")
    
    # Get correct answer from database
    cursor.execute("""
        SELECT correct_answer 
        FROM notes 
        WHERE id = ?
    """, (question_id,))
    correct_answer = cursor.fetchone()["correct_answer"]
    
    if selected_answer == correct_answer:
        session["score"] = session.get("score", 0) + 1
    
    session["current_question"] = session.get("current_question", 0) + 1
    
    return render_template("answer_feedback.html",
                         correct_answer=correct_answer,
                         selected_answer=selected_answer,
                         is_correct=(selected_answer == correct_answer))

@app.route("/check_test_answer", methods=["POST"])
#@login_required
def check_test_answer():
    if "test_questions" not in session:
        return redirect(url_for("test_setup"))
    
    questions = session["test_questions"]
    current = session["current_question"]
    question = questions[current]
    
    selected_answer = request.form.get("answer")
    is_correct = selected_answer == question["correct_answer"]
    
    # Update statistics in database
    cursor.execute("""
        UPDATE notes 
        SET times_challenged = times_challenged + 1,
            times_correct = times_correct + ?,
            last_tested = DATETIME('now')
        WHERE id = ?
    """, (1 if is_correct else 0, question["id"]))
    db.commit()
    
    if is_correct:
        session["score"] = session.get("score", 0) + 1
    
    session["current_question"] = current + 1
    
    return render_template("test_feedback.html",
                         is_correct=is_correct,
                         correct_answer=question["correct_answer"],
                         selected_answer=selected_answer)

@app.route("/stats")
@login_required
def show_stats():
    page = int(request.args.get("page", 1))
    per_page = 10
    
    # Get total count for pagination
    g.cursor.execute("""
        SELECT COUNT(*) as count
        FROM notes
        WHERE times_challenged > 0
    """)
    total_results = g.cursor.fetchone()['count']
    total_pages = ceil(total_results / per_page)
    offset = (page - 1) * per_page
    
    # Get paginated stats
    g.cursor.execute("""
        SELECT title, subject, topic, 
               times_challenged, times_correct,
               CASE 
                   WHEN times_challenged > 0 
                   THEN ROUND(CAST(times_correct AS FLOAT) / times_challenged * 100, 1)
                   ELSE 0 
               END as success_rate,
               last_tested
        FROM notes
        WHERE times_challenged > 0
        ORDER BY success_rate ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    
    stats = g.cursor.fetchall()
    
    return render_template("stats.html", 
                         stats=stats,
                         page=page,
                         total_pages=total_pages,
                         total_results=total_results)

@app.route("/select_test_questions", methods=["POST"])
#@login_required
def select_test_questions():
    n = int(request.form.get("question_count", 10))
    
    # Prioritize questions with lower success rates
    cursor.execute("""
        SELECT id, question, correct_answer, 
               wrong_answer1, wrong_answer2, wrong_answer3,
               CASE 
                   WHEN times_challenged > 0 
                   THEN CAST(times_correct AS FLOAT) / times_challenged
                   ELSE 0 
               END as success_rate
        FROM notes 
        WHERE question IS NOT NULL 
        AND correct_answer IS NOT NULL
        ORDER BY success_rate ASC, 
                 RANDOM()
        LIMIT ?
    """, (n,))
    
    questions = cursor.fetchall()
    # ... rest of start_test logic ...

def get_db():
    db = sqlite3.connect("notes.db")
    db.row_factory = sqlite3.Row
    return db

@app.before_request
def before_request():
    """Connect to user's database before each request"""
    if "username" in session:
        try:
            g.db = get_user_db(session["username"])
            g.cursor = g.db.cursor()
            
            # Ensure tags table exists for existing users
            g.cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Ensure note_tags table exists for existing users
            g.cursor.execute("""
                CREATE TABLE IF NOT EXISTS note_tags (
                    note_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (note_id, tag_id),
                    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
                )
            """)
            
            g.db.commit()
            
        except sqlite3.Error:
            session.clear()
            return redirect(url_for('login'))
    else:
        g.db = None
        g.cursor = None

@app.teardown_request
def teardown_request(exception):
    """Close database connection after each request"""
    if hasattr(g, 'db') and g.db is not None:
        g.db.close()

app.secret_key = 'your_secret_key_here'  # Change this to a secure value

def get_user_db(username):
    """Get connection to user-specific database"""
    db_path = f"users/data/{username}.db"
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db

def init_user_db(username):
    """Initialize a new user's database with required tables"""
    db = get_user_db(username)
    cursor = db.cursor()
    
    # Create notes table without user_id since each DB is user-specific
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            subject TEXT,
            topic TEXT,
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
    
    # Create tags table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create note_tags junction table
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
    
    db.commit()
    db.close()

# Main users database
def get_users_db():
    """Get connection to main users database"""
    db = sqlite3.connect("users/users.db")
    db.row_factory = sqlite3.Row
    return db

def import_test_set(username):
    """Import test set from mem_notes.db to user's database"""
    # Connect to test set database
    test_db = sqlite3.connect("mem_notes.db")
    test_db.row_factory = sqlite3.Row
    test_cursor = test_db.cursor()
    
    # Get user's database
    user_db = get_user_db(username)
    user_cursor = user_db.cursor()
    
    # Get test set data
    test_cursor.execute("""
        SELECT 
            title,
            content,
            subject,
            topic,
            question,
            correct_answer,
            wrong_answer1,
            wrong_answer2,
            wrong_answer3
        FROM notes
    """)
    test_data = test_cursor.fetchall()
    
    # Insert each row into user's database
    for row in test_data:
        user_cursor.execute("""
            INSERT INTO notes (
                title, content, subject, topic,
                question, correct_answer,
                wrong_answer1, wrong_answer2, wrong_answer3,
                times_challenged, times_correct
            )
            VALUES (?, 'TEST_SET: ' || ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        """, (
            row['title'], row['content'], row['subject'], 
            row['topic'], row['question'], row['correct_answer'],
            row['wrong_answer1'], row['wrong_answer2'], row['wrong_answer3']
        ))
    
    user_db.commit()
    test_db.close()
    user_db.close()

@app.route("/import_test_set")
@login_required
def handle_import_test_set():
    """Handle the import test set request"""
    import_test_set(session["username"])
    flash("Test set imported successfully!")
    return redirect("/")

@app.route("/remove_test_set")
@login_required
def remove_test_set():
    """Remove all test set notes"""
    g.cursor.execute("DELETE FROM notes WHERE content LIKE 'TEST_SET: %'")
    g.db.commit()
    flash("Test set removed successfully!")
    return redirect("/")

@app.route("/manage_tags", methods=["GET", "POST"])
@login_required
def manage_tags():
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            tag_name = request.form.get("tag_name").strip()
            if tag_name:
                try:
                    g.cursor.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
                    g.db.commit()
                    flash(f"Tag '{tag_name}' added successfully!")
                except sqlite3.IntegrityError:
                    flash(f"Tag '{tag_name}' already exists!")
        
        elif action == "delete":
            tag_id = request.form.get("tag_id")
            g.cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            g.db.commit()
            flash("Tag deleted successfully!")
        
        elif action == "edit":
            tag_id = request.form.get("tag_id")
            new_name = request.form.get("new_name").strip()
            if new_name:
                try:
                    g.cursor.execute("UPDATE tags SET name = ? WHERE id = ?", 
                                   (new_name, tag_id))
                    g.db.commit()
                    flash("Tag updated successfully!")
                except sqlite3.IntegrityError:
                    flash(f"Tag '{new_name}' already exists!")
        
        return redirect(url_for('manage_tags'))

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 30
    search = request.args.get('search', '').strip()
    
    # Build base query
    base_query = "FROM tags"
    params = []
    
    if search:
        base_query += " WHERE name LIKE ?"
        params.append(f"%{search}%")
    
    base_query += " ORDER BY name"
    
    # Get total count for pagination
    g.cursor.execute(f"SELECT COUNT(*) as count {base_query}", params)
    total_tags = g.cursor.fetchone()['count']
    total_pages = ceil(total_tags / per_page)
    
    # Get paginated results
    offset = (page - 1) * per_page
    g.cursor.execute(
        f"SELECT * {base_query} LIMIT ? OFFSET ?", 
        params + [per_page, offset]
    )
    tags = g.cursor.fetchall()
    
    return render_template(
        "tags.html",
        tags=tags,
        page=page,
        total_pages=total_pages,
        search=search,
        total_tags=total_tags
    )