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

from helpers import (
    login_required,
    get_note_tags,
    get_all_tags,
    update_note_tags,
    remove_unused_tags,
    init_users_db,
    init_user_db,
    get_users_db,
    import_test_set,
    get_user_db,
)
from config import SECRET_KEY

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
app.secret_key = SECRET_KEY


@app.before_request
def before_request():
    """Connect to the user-specific database before each request."""
    if "username" in session:
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
    """Close the database connection after each request."""
    if hasattr(g, "db") and g.db is not None:
        g.db.close()


# Ensure the users directory structure exists
if not os.path.exists("users"):
    os.makedirs("users")
if not os.path.exists("users/data"):
    os.makedirs("users/data")


# Initialize users database at startup
init_users_db()


@app.after_request
def after_request(response):
    """Ensure responses aren't cached by setting appropriate headers."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Render the index page with recent notes and total note count."""
    # Add debug prints
    print("Session state:", session)
    print("Database connection:", hasattr(g, "db") and g.db is not None)

    try:
        # Verify database connection
        if not hasattr(g, "db") or g.db is None:
            print("No database connection")
            return redirect(url_for("login"))

        # Get total count of notes
        g.cursor.execute("SELECT COUNT(*) as count FROM notes")
        count_result = g.cursor.fetchone()
        total_notes = count_result["count"] if count_result else 0
        print(f"Total notes: {total_notes}")

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
        print(f"Retrieved notes: {len(notes)}")

        # Convert tags string to list for each note
        for note in notes:
            note["tags"] = note["tags"].split(",") if note["tags"] else []

        return render_template(
            "index.html",
            notes=notes,
            total_notes=total_notes,
            show_import=(total_notes == 0),
        )
    except (AttributeError, sqlite3.OperationalError) as e:
        print(f"Error in index: {str(e)}")
        return redirect(url_for("login"))


@app.route("/record_new_note", methods=["GET", "POST"])
@login_required
def create_new_note():
    """Create a new note with optional question and tags."""
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
                    wrong_answers[2] if question else None,
                ),
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
    """Search for notes based on text query and selected tags."""
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
    """Display a single note with its details and tags."""
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
    """Edit an existing note's content and tags."""
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
            note_tags=get_note_tags(note_id),
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
        g.cursor.execute(
            """
            UPDATE notes 
            SET title = ?, content = ?, question = ?,
                correct_answer = ?, wrong_answer1 = ?,
                wrong_answer2 = ?, wrong_answer3 = ?
            WHERE id = ?
        """,
            (
                title,
                content,
                request.form.get("question", "").strip(),
                request.form.get("correct_answer", "").strip(),
                request.form.get("wrong_answer1", "").strip(),
                request.form.get("wrong_answer2", "").strip(),
                request.form.get("wrong_answer3", "").strip(),
                note_id,
            ),
        )

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
def delete_note(note_id):
    """Allow deletion of a selected note."""
    if request.method == "POST":
        g.cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        g.db.commit()
        return redirect(url_for("search"))
    g.cursor.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
    mem_note = g.cursor.fetchone()
    return render_template("delete_note.html", this_note=mem_note)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in by verifying username and password."""
    # Only clear specific keys, not the entire session
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("has_test_set", None)

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

            # Query database for username
            users_cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
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
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["has_test_set"] = bool(user["has_test_set"])

            flash("Logged in successfully!")
            return redirect(url_for("index"))

        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}")
            return render_template("index.html")

        finally:
            users_db.close()

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out by clearing the session."""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user with a unique username and password."""
    if request.method == "POST":
        # Get form information
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

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
                    (
                        username,
                        generate_password_hash(
                            password, method="pbkdf2:sha256", salt_length=8
                        ),
                        False,
                    ),
                )

                # Get the new user's ID
                users_cursor.execute(
                    "SELECT * FROM users WHERE username = ?", (username,)
                )
                user = users_cursor.fetchone()

            # Set session variables
            session.permanent = True  # Make session permanent
            session["user_id"] = user["id"]
            session["username"] = username
            session["has_test_set"] = False

            init_user_db(username)

            flash("Registered successfully!")
            return redirect(url_for("index"))  # Be explicit about the redirect

        except sqlite3.Error as e:
            flash(f"Database error: {str(e)}")
            return render_template("login.html")

    return render_template("register.html")


@app.route("/flashcards")
def flashcards():
    """Show a flashcard practice page with random questions."""
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


@app.route("/start_test", methods=["GET", "POST"])
@login_required
def start_test():
    """Start a new test with questions filtered by type."""
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
def show_test_question():
    """Display the current test question and its answers."""
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
def check_answer(question_id):
    """Check the answer for a specific question and provide feedback."""
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
    """Check the answer for the current test question and update stats."""
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
    """Show statistics of note challenges and success rates."""
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
    """Select questions for a test based on success rate."""
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


@app.route("/import_test_set")
@login_required
def handle_import_test_set():
    """Handle the import test set request for the current user."""
    if import_test_set(session["user_id"]):  # Pass user_id instead of username
        flash("Test set imported successfully!")
    else:
        flash("Error importing test set", "error")
    return redirect("/")


@app.route("/remove_test_set")
@login_required
def remove_test_set():
    """Remove all test set notes from the user's database."""
    try:
        # Start transaction
        g.cursor.execute("BEGIN TRANSACTION")

        # Get the test set tag ID
        g.cursor.execute("SELECT id FROM tags WHERE name = 'TEST SET'")
        test_set_tag = g.cursor.fetchone()

        if test_set_tag:
            test_set_tag_id = test_set_tag["id"]

            # Get all note IDs that have TEST SET tag
            g.cursor.execute(
                """
                SELECT DISTINCT note_id 
                FROM note_tags 
                WHERE tag_id = ?
            """,
                (test_set_tag_id,),
            )
            test_set_note_ids = [row["note_id"] for row in g.cursor.fetchall()]

            if test_set_note_ids:
                # Delete all note_tags entries for these notes at once
                placeholders = ",".join("?" * len(test_set_note_ids))
                g.cursor.execute(
                    f"""
                    DELETE FROM note_tags 
                    WHERE note_id IN ({placeholders})
                """,
                    test_set_note_ids,
                )

                # Delete all these notes at once
                g.cursor.execute(
                    f"""
                    DELETE FROM notes 
                    WHERE id IN ({placeholders})
                """,
                    test_set_note_ids,
                )

            # Delete the TEST SET tag
            g.cursor.execute(
                """
                DELETE FROM tags 
                WHERE id = ?
            """,
                (test_set_tag_id,),
            )

            # Clean up unused tags
            deleted_tags = remove_unused_tags()

            # Commit all changes
            g.db.commit()

            # Update users database
            users_db = sqlite3.connect("users/users.db")
            users_cursor = users_db.cursor()
            try:
                users_cursor.execute(
                    "UPDATE users SET has_test_set = 0 WHERE id = ?",
                    (session["user_id"],),
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
        return redirect("/")


@app.route("/manage_tags", methods=["GET", "POST"])
@login_required
def manage_tags():
    """Manage tags by adding, deleting, or editing them."""
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


@app.route("/api/tags/search")
@login_required
def search_tags():
    """Return all tags for autocomplete functionality."""
    g.cursor.execute("SELECT name FROM tags ORDER BY name")
    tags = [row["name"] for row in g.cursor.fetchall()]
    return jsonify(tags)
