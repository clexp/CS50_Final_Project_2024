import os
import sqlite3
from flask_session import Session
from datetime import datetime, timedelta
from random import shuffle
from math import ceil

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    g,
    jsonify,
)
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, get_note_tags, get_all_tags, update_note_tags, remove_unused_tags

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Ensure the users directory structure exists
if not os.path.exists("users"):
    os.makedirs("users")
if not os.path.exists("users/data"):
    os.makedirs("users/data")


# Initialize the users database at startup
def init_users_db():
    """Initialize the main users database"""
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
        total_notes = g.cursor.fetchone()["count"]

        # Get recent notes with their tags
        g.cursor.execute(
            """
            SELECT n.*, GROUP_CONCAT(t.name) as tags
            FROM notes n
            LEFT JOIN note_tags nt ON n.id = nt.note_id
            LEFT JOIN tags t ON nt.tag_id = t.id
            GROUP BY n.id
            ORDER BY n.date DESC 
            LIMIT 10
        """
        )
        notes = [dict(row) for row in g.cursor.fetchall()]

        # Convert tags string to list for each note
        for note in notes:
            note["tags"] = note["tags"].split(",") if note["tags"] else []

        return render_template(
            "index.html",
            notes=notes,
            total_notes=total_notes,
            show_import=total_notes == 0,
        )
    except (AttributeError, sqlite3.OperationalError):
        return redirect(url_for("login"))


@app.route("/record_new_note", methods=["GET", "POST"])
@login_required
def create_new_note():
    """Create a new note"""
    if request.method == "GET":
        # Get all available tags for the autocomplete
        g.cursor.execute("SELECT name FROM tags ORDER BY name")
        all_tags = [row["name"] for row in g.cursor.fetchall()]
        return render_template("create.html", all_tags=all_tags)

    if request.method == "POST":
        # Get form data
        # strips whitespace from the beginning and end of the string
        # if no value is provided, it defaults to an empty string
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        selected_tags = request.form.getlist("tags")
        question = request.form.get("question", "").strip()
        correct_answer = request.form.get("correct_answer", "").strip()
        wrong_answers = [
            request.form.get("wrong_answer1", "").strip(),
            request.form.get("wrong_answer2", "").strip(),
            request.form.get("wrong_answer3", "").strip(),
        ]

        # Validate required fields
        errors = []
        if not title:
            errors.append("Title is required")
        if not content:
            errors.append("Content is required")
        if not selected_tags:
            errors.append("At least one tag is required")

        # If question is provided, validate its components
        if question:
            if not correct_answer:
                errors.append("Correct answer is required when question is provided")
            if not all(wrong_answers):
                errors.append(
                    "All three wrong answers are required when question is provided"
                )

        # If there are errors, flash them and return to form
        if errors:
            for error in errors:
                flash(error)
            return render_template(
                "create.html",
                title=title,
                content=content,
                question=question,
                correct_answer=correct_answer,
                wrong_answers=wrong_answers,
                selected_tags=selected_tags,
            )

        try:
            # Insert the note with question fields
            g.cursor.execute(
                """
                INSERT INTO notes (
                    title, content, date,
                    question, correct_answer,
                    wrong_answer1, wrong_answer2, wrong_answer3
                ) 
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
            """,
                (
                    title, 
                    content,
                    question if question else None,
                    correct_answer if correct_answer else None,
                    wrong_answers[0] if question else None,
                    wrong_answers[1] if question else None,
                    wrong_answers[2] if question else None
                )
            )
            note_id = g.cursor.lastrowid

            # Link tags to note
            for tag_name in selected_tags:
                g.cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                tag_id = g.cursor.fetchone()["id"]
                g.cursor.execute(
                    """
                    INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)
                """,
                    (note_id, tag_id),
                )

            g.db.commit()
            flash("Note created successfully!")
            # change this so it redirects to the display this new note
            return redirect(url_for("display_note", note_id=note_id))

        except sqlite3.Error as e:
            g.db.rollback()
            flash(f"Database error: {str(e)}")
            return render_template(
                "create.html",
                title=title,
                content=content,
                question=question,
                correct_answer=correct_answer,
                wrong_answers=wrong_answers,
                selected_tags=selected_tags,
            )
    # if there are no errors, redirect to the index page
    return redirect(url_for("index"))


@app.route("/search", methods=["GET", "POST"])
@login_required
def search():
    # Get user's test set status from session
    has_test_set = session.get("has_test_set", False)

    # Get all available tags for the autocomplete (used by both GET and POST)
    g.cursor.execute("SELECT name FROM tags ORDER BY name")
    all_tags = [row["name"] for row in g.cursor.fetchall()]

    if request.method == "GET":
        # On GET, just show recent notes (top 15)
        g.cursor.execute(
            """
            SELECT n.*, GROUP_CONCAT(t.name) as tags
            FROM notes n
            LEFT JOIN note_tags nt ON n.id = nt.note_id
            LEFT JOIN tags t ON nt.tag_id = t.id
            GROUP BY n.id
            ORDER BY n.date DESC
            LIMIT 15
        """
        )
        notes = [dict(row) for row in g.cursor.fetchall()]
        for note in notes:
            note["tags"] = note["tags"].split(",") if note["tags"] else []

        return render_template(
            "search.html", notes=notes, all_tags=all_tags, has_test_set=has_test_set
        )

    # Handle POST request (actual search)
    query = request.form.get("q", "").strip()
    selected_tags = request.form.getlist("tags")

    # Build search query
    search_query = """
        SELECT DISTINCT n.*, GROUP_CONCAT(t2.name) as tags
        FROM notes n
        LEFT JOIN note_tags nt2 ON n.id = nt2.note_id
        LEFT JOIN tags t2 ON nt2.tag_id = t2.id
    """
    params = []
    where_clauses = []

    # Add tag filtering
    if selected_tags:
        search_query += """
            JOIN note_tags nt ON n.id = nt.note_id
            JOIN tags t ON nt.tag_id = t.id
            AND t.name IN ({})
        """.format(
            ",".join("?" * len(selected_tags))
        )
        params.extend(selected_tags)
        where_clauses.append(
            f"(SELECT COUNT(DISTINCT t.name) FROM tags t JOIN note_tags nt ON t.id = nt.tag_id WHERE nt.note_id = n.id AND t.name IN ({','.join(['?'] * len(selected_tags))})) = ?"
        )
        params.extend(selected_tags)
        params.append(len(selected_tags))

    # Add text search
    if query:
        where_clauses.append("(title LIKE ? OR content LIKE ?)")
        params.extend([f"%{query}%"] * 2)

    # If no search criteria, show recent notes
    if not where_clauses:
        where_clauses.append("1=1")

    search_query += " WHERE " + " AND ".join(where_clauses)
    search_query += " GROUP BY n.id ORDER BY n.date DESC"

    g.cursor.execute(search_query, params)
    notes = [dict(row) for row in g.cursor.fetchall()]
    for note in notes:
        note["tags"] = note["tags"].split(",") if note["tags"] else []

    return render_template(
        "search.html",
        notes=notes,
        query=query,
        all_tags=all_tags,
        selected_tags=selected_tags,
        has_test_set=has_test_set,
    )


@app.route("/display_note/<int:note_id>")
@login_required
def display_note(note_id):
    """Display a single note."""
    g.cursor.execute(
        """
        SELECT n.*, GROUP_CONCAT(t.name) as tags
        FROM notes n
        LEFT JOIN note_tags nt ON n.id = nt.note_id
        LEFT JOIN tags t ON nt.tag_id = t.id
        WHERE n.id = ?
        GROUP BY n.id
    """,
        (note_id,),
    )
    note = g.cursor.fetchone()

    if note is None:
        flash("Note not found!")
        return redirect(url_for("index"))

    # Get tags for the note
    g.cursor.execute(
        """
        SELECT t.* 
        FROM tags t
        JOIN note_tags nt ON t.id = nt.tag_id
        WHERE nt.note_id = ?
        ORDER BY t.name
    """,
        (note_id,),
    )
    note_tags = g.cursor.fetchall()

    return render_template("display_note.html", note=note, note_tags=note_tags)


@app.route("/edit_note/<int:note_id>", methods=["GET", "POST"])
@login_required
def edit_note(note_id):
    if request.method == "GET":
        g.cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        note = g.cursor.fetchone()

        if note is None:
            flash("Note not found!")
            return redirect(url_for("index"))

        return render_template(
            "edit_note.html",
            note=note,
            all_tags=get_all_tags(),
            note_tags=get_note_tags(note_id)
        )

    # Handle POST request
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    selected_tags = request.form.getlist("tags")

    if not title or not content or not selected_tags:
        flash("Title, content, and at least one tag are required!")
        return redirect(url_for("edit_note", note_id=note_id))

    try:
        # Update note content
        g.cursor.execute("""
            UPDATE notes 
            SET title = ?, content = ?, question = ?,
                correct_answer = ?, wrong_answer1 = ?,
                wrong_answer2 = ?, wrong_answer3 = ?
            WHERE id = ?
        """, (
            title, content,
            request.form.get("question", "").strip(),
            request.form.get("correct_answer", "").strip(),
            request.form.get("wrong_answer1", "").strip(),
            request.form.get("wrong_answer2", "").strip(),
            request.form.get("wrong_answer3", "").strip(),
            note_id
        ))

        # Update tags using helper function
        if update_note_tags(note_id, selected_tags):
            g.db.commit()
            flash("Note updated successfully!")
        else:
            flash("Error updating tags!")
            
        return redirect(url_for("display_note", note_id=note_id))

    except sqlite3.Error as e:
        g.db.rollback()
        flash(f"Database error: {str(e)}")
        return redirect(url_for("edit_note", note_id=note_id))


@app.route("/delete_note/<int:note_id>", methods=["GET", "POST"])
# @login_required
def delete_note(note_id):
    """Allow deletion of selected note"""
    # user_id = int(session["user_id"])
    if request.method == "POST":
        print("went to delete in POST")
        g.cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        g.db.commit()
        return redirect(url_for("search"))
    g.cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
    mem_note = g.cursor.fetchone()
    return render_template("delete_note.html", this_note=mem_note)


# removed old code. 


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    print(f"Starting login route, session: {session}")  # Debug print
    
    # Only clear specific keys, not the entire session
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('has_test_set', None)

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Must provide username")
            return render_template("login.html")

        # Ensure password was submitted
        if not request.form.get("password"):
            flash("Must provide password")
            return render_template("login.html")

        # Connect to users database
        users_db = sqlite3.connect("users/users.db")
        users_db.row_factory = sqlite3.Row
        users_cursor = users_db.cursor()

        try:
            username = request.form.get("username")
            password = request.form.get("password")
            print(f"Login attempt for user: {username}")  # Debug print

            # Query database for username
            users_cursor.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            )
            user = users_cursor.fetchone()

            # Ensure username exists and password is correct
            if user is None:
                flash("Invalid username")
                return render_template("login.html")
            
            if not check_password_hash(user["hash"], password):
                flash("Invalid password")
                return render_template("login.html")

            # Remember which user has logged in
            session.permanent = True  # Make session permanent
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['has_test_set'] = bool(user['has_test_set'])
            print(f"Login successful. Session: {session}")  # Debug print

            flash("Logged in successfully!")
            return render_template("index.html")  # Return index template directly

        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            flash(f"Database error: {str(e)}")
            return render_template("index.html")

        finally:
            users_db.close()

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
    """Register user"""
    print(f"Starting register route, session: {session}")  # Debug print
    
    if request.method == "POST":
        # Get form information
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        print(f"Registration attempt for user: {username}")  # Debug print

        # Ensure username was submitted
        if not username:
            flash("Must provide username")
            return render_template("register.html")

        # Ensure password was submitted
        if not password:
            flash("Must provide password")
            return render_template("register.html")

        # Ensure confirmation was submitted
        if not confirmation:
            flash("Must confirm password")
            return render_template("register.html")

        # Ensure password and confirmation match
        if password != confirmation:
            flash("Passwords must match")
            return render_template("register.html")

        try:
            with sqlite3.connect("users/users.db") as users_db:
                users_db.row_factory = sqlite3.Row
                users_cursor = users_db.cursor()
                
                # Check if username already exists
                users_cursor.execute(
                    "SELECT * FROM users WHERE username = ?", (username,)
                )
                if users_cursor.fetchone() is not None:
                    flash("Username already exists")
                    return render_template("register.html")

                # Add new user to database
                users_cursor.execute(
                    "INSERT INTO users (username, hash, has_test_set) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password), False)
                )
                
                # Get the new user's ID
                users_cursor.execute(
                    "SELECT * FROM users WHERE username = ?", (username,)
                )
                user = users_cursor.fetchone()

            # Set session variables
            session.permanent = True  # Make session permanent
            session['user_id'] = user['id']
            session['username'] = username
            session['has_test_set'] = False

            init_user_db(username)
            
            print(f"Registration successful. Session: {session}")
            
            flash("Registered successfully!")
            return redirect(url_for('index'))  # Be explicit about the redirect

        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            flash(f"Database error: {str(e)}")
            return render_template("login.html")

    return render_template("register.html")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    user_id = int(session["user_id"])
    """Change password."""
    if request.method == "GET":
        return render_template("change_password.html")

    if request.method == "POST":
        old_password = request.form.get("old_password")
        hash_record = g.db.execute("SELECT hash FROM users WHERE id = ?; ", user_id)[0][
            "hash"
        ]
        if not check_password_hash(hash_record, old_password):
            return apology("incorrect password")
        new_password_1 = request.form.get("password1")
        new_password_2 = request.form.get("password2")
        if new_password_1 != new_password_2:
            return apology("New passwords not matching")
        new_hash = generate_password_hash(new_password_1)
        if 1 == g.db.execute(
            "UPDATE users SET hash = ? WHERE id = ?;", new_hash, user_id
        ):
            session.clear()
            # this is non ideal, as if it updates multiple rows, this is not flagged
            print("cleared session, went to index, did not like usd?")
            return redirect("/")
    return apology("Password update error")


@app.route("/flashcards")
# @login_required
def flashcards():
    """Show flashcard practice page"""
    g.cursor.execute(
        """
        SELECT id, title, subject, topic, question, correct_answer, 
               wrong_answer1, wrong_answer2, wrong_answer3 
        FROM notes 
        WHERE question IS NOT NULL 
        AND correct_answer IS NOT NULL
        ORDER BY RANDOM() 
        LIMIT 1
    """
    )
    card = g.cursor.fetchone()

    if card:
        # Create list of all answers and shuffle them
        answers = [
            card["correct_answer"],
            card["wrong_answer1"],
            card["wrong_answer2"],
            card["wrong_answer3"],
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
        g.cursor.execute(
            """
            INSERT INTO notes (
                title, content, subject, topic,
                question, correct_answer,
                wrong_answer1, wrong_answer2, wrong_answer3
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                title,
                content,
                subject,
                topic,
                question,
                correct_answer,
                wrong_answer1,
                wrong_answer2,
                wrong_answer3,
            ),
        )

        # Get the id of the newly inserted note
        note_id = g.cursor.lastrowid

        # Insert tag relationships
        if selected_tags:
            for tag_id in selected_tags:
                g.cursor.execute(
                    """
                    INSERT INTO note_tags (note_id, tag_id)
                    VALUES (?, ?)
                """,
                    (note_id, tag_id),
                )

        g.db.commit()
        flash("Note saved successfully!")
        return redirect("/")

    # GET request - show the form
    # Get all available tags
    g.cursor.execute("SELECT * FROM tags ORDER BY name")
    tags = g.cursor.fetchall()
    # print(f"Debug - Found tags: {tags}")  # Debug output

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
        SELECT id, title, question, correct_answer, 
               wrong_answer1, wrong_answer2, wrong_answer3 
        FROM notes 
        WHERE question IS NOT NULL 
        AND correct_answer IS NOT NULL
    """

    if filter_type == "weakest":
        base_query += """
            AND times_challenged > 0 
            ORDER BY 
                CAST(times_correct AS FLOAT) / NULLIF(times_challenged, 0) ASC,
                times_challenged ASC,
                RANDOM()
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
# @login_required
def show_test_question():
    if "test_questions" not in session:
        return redirect(url_for("test_setup"))

    questions = session["test_questions"]
    current = session["current_question"]

    if current >= len(questions):
        # Test is complete
        return render_template(
            "test_complete.html", score=session["score"], total=len(questions)
        )

    question = questions[current]
    answers = [
        question["correct_answer"],
        question["wrong_answer1"],
        question["wrong_answer2"],
        question["wrong_answer3"],
    ]
    shuffle(answers)

    return render_template(
        "test_question.html",
        question=question,
        shuffled_answers=answers,
        progress={"current": current + 1, "total": len(questions)},
    )


@app.route("/check_answer/<int:question_id>", methods=["POST"])
# @login_required
def check_answer(question_id):
    selected_answer = request.form.get("answer")

    # Get correct answer from database
    g.cursor.execute(
        """
        SELECT correct_answer 
        FROM notes 
        WHERE id = ?
    """,
        (question_id,),
    )
    correct_answer = g.cursor.fetchone()["correct_answer"]

    if selected_answer == correct_answer:
        session["score"] = session.get("score", 0) + 1

    session["current_question"] = session.get("current_question", 0) + 1

    return render_template(
        "answer_feedback.html",
        correct_answer=correct_answer,
        selected_answer=selected_answer,
        is_correct=(selected_answer == correct_answer),
    )


@app.route("/check_test_answer", methods=["POST"])
@login_required
def check_test_answer():
    if "test_questions" not in session:
        return redirect(url_for("test_setup"))

    current = session["current_question"]
    question = session["test_questions"][current]

    # Update question stats
    g.cursor.execute(
        """
        UPDATE notes 
        SET times_challenged = times_challenged + 1,
            times_correct = times_correct + ?,
            last_tested = CURRENT_TIMESTAMP
        WHERE id = ?
    """,
        (
            1 if request.form.get("answer") == question["correct_answer"] else 0,
            question["id"],
        ),
    )
    g.db.commit()

    if request.form.get("answer") == question["correct_answer"]:
        session["score"] = session.get("score", 0) + 1

    session["current_question"] = current + 1

    return render_template(
        "test_feedback.html",
        is_correct=request.form.get("answer") == question["correct_answer"],
        correct_answer=question["correct_answer"],
        selected_answer=request.form.get("answer"),
    )


@app.route("/stats")
@login_required
def show_stats():
    page = int(request.args.get("page", 1))
    per_page = 10

    # Get total count for pagination
    g.cursor.execute(
        """
        SELECT COUNT(*) as count
        FROM notes
        WHERE times_challenged > 0
    """
    )
    total_results = g.cursor.fetchone()["count"]
    total_pages = ceil(total_results / per_page)
    offset = (page - 1) * per_page

    # Get paginated stats
    g.cursor.execute(
        """
        SELECT title,   
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
    """,
        (per_page, offset),
    )

    stats = g.cursor.fetchall()

    return render_template(
        "stats.html",
        stats=stats,
        page=page,
        total_pages=total_pages,
        total_results=total_results,
    )


@app.route("/select_test_questions", methods=["POST"])
@login_required
def select_test_questions():
    n = int(request.form.get("question_count", 10))

    g.cursor.execute(
        """
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
    """,
        (n,),
    )

    questions = g.cursor.fetchall()

    if questions:
        session["test_questions"] = [dict(q) for q in questions]
        session["current_question"] = 0
        session["correct_answers"] = 0
        return redirect(url_for("test_question"))
    else:
        flash("No questions available for testing!")
        return redirect(url_for("index"))


def get_db():
    db = sqlite3.connect("notes.db")
    db.row_factory = sqlite3.Row
    return db


@app.before_request
def before_request():
    """Connect to user-specific database before each request"""
    if 'username' in session:
        try:
            # Connect to user's database
            db_path = f"users/data/{session['username']}.db"
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
            g.cursor = g.db.cursor()
        except sqlite3.Error as e:
            print(f"Database connection error: {str(e)}")
            g.db = None
            g.cursor = None



@app.teardown_request
def teardown_request(exception):
    """Close database connection after each request"""
    if hasattr(g, "db") and g.db is not None:
        g.db.close()


app.secret_key = "your_secret_key_here"  # Change this to a secure value


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


# Main users database
def get_users_db():
    """Get connection to main users database"""
    db = sqlite3.connect("users/users.db")
    db.row_factory = sqlite3.Row
    return db


def import_test_set(user_id):
    """Import test set notes and related data for a user"""
    try:
        # Connect to source database
        source_db = sqlite3.connect("mem_notes.db")
        source_db.row_factory = sqlite3.Row
        source_cursor = source_db.cursor()

        # First import all tags
        source_cursor.execute("SELECT name FROM tags")
        source_tags = source_cursor.fetchall()
        for tag in source_tags:
            g.cursor.execute("""
                INSERT OR IGNORE INTO tags (name, created_at) 
                VALUES (?, CURRENT_TIMESTAMP)
            """, (tag['name'],))

        # Add TEST SET tag
        g.cursor.execute("""
            INSERT OR IGNORE INTO tags (name, created_at) 
            VALUES ('TEST SET', CURRENT_TIMESTAMP)
        """)

        # Get all notes from source
        source_cursor.execute("""
            SELECT id, title, content, question, correct_answer,
                   wrong_answer1, wrong_answer2, wrong_answer3
            FROM notes
        """)
        notes = source_cursor.fetchall()

        for note in notes:
            # For each note, get its tags
            source_cursor.execute("""
                SELECT t.name 
                FROM tags t
                JOIN note_tags nt ON t.id = nt.tag_id
                WHERE nt.note_id = ?
            """, (note['id'],))
            note_tags = [row['name'] for row in source_cursor.fetchall()]
            
            # Add TEST SET tag to the list
            note_tags.append('TEST SET')

            try:
                # Use create_new_note logic
                g.cursor.execute("""
                    INSERT INTO notes (
                        title, content, date, question, correct_answer,
                        wrong_answer1, wrong_answer2, wrong_answer3
                    ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
                """, (
                    note['title'], 
                    note['content'],
                    note['question'], 
                    note['correct_answer'],
                    note['wrong_answer1'], 
                    note['wrong_answer2'], 
                    note['wrong_answer3']
                ))
                new_note_id = g.cursor.lastrowid

                # Link tags to note
                for tag_name in note_tags:
                    g.cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                    tag_id = g.cursor.fetchone()["id"]
                    g.cursor.execute("""
                        INSERT INTO note_tags (note_id, tag_id, created_at) 
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """, (new_note_id, tag_id))

            except sqlite3.Error as e:
                print(f"Error importing note {note['title']}: {str(e)}")
                continue

        g.db.commit()

        # Update user's has_test_set flag
        users_db = sqlite3.connect("users/users.db")
        users_cursor = users_db.cursor()
        try:
            users_cursor.execute(
                "UPDATE users SET has_test_set = 1 WHERE id = ?",
                (user_id,)
            )
            users_db.commit()
            session["has_test_set"] = True
        finally:
            users_db.close()

        source_db.close()
        return True

    except sqlite3.Error as e:
        g.db.rollback()
        if 'source_db' in locals():
            source_db.close()
        print(f"Error importing test set: {str(e)}")
        return False


@app.route("/import_test_set")
@login_required
def handle_import_test_set():
    """Handle the import test set request"""
    import_test_set(session["username"])

    # Update users.db
    users_db = sqlite3.connect("users/users.db")
    users_cursor = users_db.cursor()

    try:
        users_cursor.execute(
            """
            UPDATE users 
            SET has_test_set = 1 
            WHERE id = ?
        """,
            (session["user_id"],),
        )
        users_db.commit()
        session["has_test_set"] = True  # Update session
    finally:
        users_db.close()

    flash("Test set imported successfully!")
    return redirect("/")


@app.route("/remove_test_set")
@login_required
def remove_test_set():
    """Remove all test set notes"""
    try:
        # Start transaction
        g.cursor.execute("BEGIN TRANSACTION")
        
        # Get the test set tag ID
        g.cursor.execute("SELECT id FROM tags WHERE name = 'TEST SET'")
        test_set_tag = g.cursor.fetchone()
        
        if test_set_tag:
            test_set_tag_id = test_set_tag['id']
            print(f"Found TEST SET tag ID: {test_set_tag_id}")
            
            # Get all note IDs that have TEST SET tag
            g.cursor.execute("""
                SELECT DISTINCT note_id 
                FROM note_tags 
                WHERE tag_id = ?
            """, (test_set_tag_id,))
            test_set_note_ids = [row['note_id'] for row in g.cursor.fetchall()]
            print(f"Found {len(test_set_note_ids)} notes to remove")
            
            if test_set_note_ids:
                # Delete all note_tags entries for these notes at once
                placeholders = ','.join('?' * len(test_set_note_ids))
                g.cursor.execute(f"""
                    DELETE FROM note_tags 
                    WHERE note_id IN ({placeholders})
                """, test_set_note_ids)
                print(f"Removed note_tags entries")
                
                # Delete all these notes at once
                g.cursor.execute(f"""
                    DELETE FROM notes 
                    WHERE id IN ({placeholders})
                """, test_set_note_ids)
                print(f"Removed notes")
            
            # Delete the TEST SET tag
            g.cursor.execute("""
                DELETE FROM tags 
                WHERE id = ?
            """, (test_set_tag_id,))
            print("Removed TEST SET tag")

            # Clean up unused tags
            deleted_tags = remove_unused_tags()
            print(f"Removed {deleted_tags} unused tags")

        # Commit all changes
        g.db.commit()

        # Update users database
        users_db = sqlite3.connect("users/users.db")
        users_cursor = users_db.cursor()
        try:
            users_cursor.execute(
                "UPDATE users SET has_test_set = 0 WHERE id = ?",
                (session["user_id"],)
            )
            users_db.commit()
            session["has_test_set"] = False
        finally:
            users_db.close()

        flash("Test set removed successfully!")
        return redirect("/")

    except sqlite3.Error as e:
        g.db.rollback()
        flash(f"Error removing test set: {str(e)}")
        print(f"Error: {str(e)}")
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
            try:
                # Start a transaction
                g.cursor.execute("BEGIN TRANSACTION")
                
                # First delete from note_tags table
                g.cursor.execute("DELETE FROM note_tags WHERE tag_id = ?", (tag_id,))
                
                # Then delete from tags table
                g.cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
                
                # Commit the transaction
                g.db.commit()
                flash("Tag and all its references deleted successfully!")
                
            except sqlite3.Error as e:
                # If anything goes wrong, roll back the transaction
                g.db.rollback()
                flash(f"Error deleting tag: {str(e)}")

        elif action == "edit":
            tag_id = request.form.get("tag_id")
            new_name = request.form.get("new_name").strip()
            if new_name:
                try:
                    g.cursor.execute(
                        "UPDATE tags SET name = ? WHERE id = ?", (new_name, tag_id)
                    )
                    g.db.commit()
                    flash("Tag updated successfully!")
                except sqlite3.IntegrityError:
                    flash(f"Tag '{new_name}' already exists!")

        return redirect(url_for("manage_tags"))

    # GET request handling
    page = request.args.get("page", 1, type=int)
    per_page = 15  # Number of tags shown per page
    search = request.args.get("search", "").strip()

    # Build base query
    base_query = "FROM tags"
    params = []

    if search:
        base_query += " WHERE name LIKE ?"
        params.append(f"%{search}%")

    base_query += " ORDER BY LOWER(name)"

    # Get total count for pagination
    g.cursor.execute(f"SELECT COUNT(*) as count {base_query}", params)
    total_tags = g.cursor.fetchone()["count"]
    total_pages = (total_tags + per_page - 1) // per_page

    # Get paginated results
    offset = (page - 1) * per_page
    g.cursor.execute(
        f"SELECT * {base_query} LIMIT ? OFFSET ?", params + [per_page, offset]
    )
    tags = g.cursor.fetchall()

    return render_template(
        "tags.html",
        tags=tags,
        page=page,
        total_pages=total_pages,
        search=search,
        total_tags=total_tags,
        max=max,  # Add the max function
        min=min,  # Add the min function too
    )


@app.route("/tags", methods=["GET"])
def get_tags():
    conn = sqlite3.connect("your_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT tag FROM tags")
    tags = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(tags)


@app.route("/tags/search")
@login_required
def search_tags():
    """Return all tags for autocomplete"""
    g.cursor.execute("SELECT name FROM tags ORDER BY name")
    tags = [row["name"] for row in g.cursor.fetchall()]
    return jsonify(tags)


def clean_tags():
    """Clean up orphaned tags and note_tag relationships"""
    try:
        # Start transaction
        g.cursor.execute("BEGIN TRANSACTION")

        # 1. Clean up note_tags entries where note doesn't exist
        g.cursor.execute("""
            DELETE FROM note_tags 
            WHERE note_id NOT IN (SELECT id FROM notes)
        """)
        
        # 2. Get all existing tags
        g.cursor.execute("SELECT id FROM tags")
        all_tags = {row['id'] for row in g.cursor.fetchall()}

        # 3. Find all tags that are actually used in notes
        g.cursor.execute("""
            SELECT DISTINCT tag_id 
            FROM note_tags
        """)
        used_tag_ids = {row['tag_id'] for row in g.cursor.fetchall()}

        # 4. Find and delete unused tags
        unused_tag_ids = all_tags - used_tag_ids
        
        if unused_tag_ids:
            placeholders = ','.join('?' * len(unused_tag_ids))
            g.cursor.execute(f"""
                DELETE FROM tags 
                WHERE id IN ({placeholders})
            """, list(unused_tag_ids))

        # Commit changes
        g.db.commit()
        
        # Return statistics
        return {
            'orphaned_tags_removed': len(unused_tag_ids),
        }

    except sqlite3.Error as e:
        g.db.rollback()
        print(f"Error cleaning tags: {str(e)}")
        return None

