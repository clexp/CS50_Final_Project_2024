import os
import sqlite3
import flask_session
from datetime import datetime
from random import random, shuffle
from math import ceil

from flask import Flask, flash, redirect, render_template, request, session, url_for, g
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from datetime import date

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Configure use SQLite database
try: 
    db = sqlite3.connect("mem_notes.db", check_same_thread=False)
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    print("connected to db")

    query = 'select sqlite_version();'
    cursor.execute(query)
    result = cursor.fetchall()
    print(result)
except sqlite3.Error as e:
    print(e)



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
    # Get total count of notes
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM notes 
        WHERE user_id = ?
    """, (session["user_id"],))
    total_notes = cursor.fetchone()['count']
    
    # Get recent notes
    cursor.execute("""
        SELECT * FROM notes 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 10
    """, (session["user_id"],))
    notes = cursor.fetchall()
    
    return render_template("index.html", notes=notes, total_notes=total_notes)


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



@app.route("/search")
@login_required
def search():
    # Get search parameters
    title_q = request.args.get("title", "")
    subject_q = request.args.get("subject", "")
    topic_q = request.args.get("topic", "")
    content_q = request.args.get("content", "")
    search_type = request.args.get("search_type", "OR")
    filter_type = request.args.get("filter_type", "none")
    page = int(request.args.get("page", 1))
    per_page = 10
    
    base_query = """
        FROM notes 
        WHERE user_id = ?
    """
    
    # Add filter for weakest/untested
    if filter_type == "weakest":
        base_query += """
            AND times_challenged > 0 
            ORDER BY CAST(times_correct AS FLOAT) / times_challenged ASC
        """
    elif filter_type == "untested":
        base_query += " AND times_challenged = 0"
    else:
        # Your existing search logic here
        if search_type == "AND":
            base_query += """
                AND (? = '' OR title LIKE ?)
                AND (? = '' OR subject LIKE ?)
                AND (? = '' OR topic LIKE ?)
                AND (? = '' OR content LIKE ?)
            """
        else:  # OR search
            base_query += """
                AND ((? != '' AND title LIKE ?)
                 OR (? != '' AND subject LIKE ?)
                 OR (? != '' AND topic LIKE ?)
                 OR (? != '' AND content LIKE ?))
            """
    
    # Get total count
    count_params = [session["user_id"]]
    if filter_type not in ["weakest", "untested"]:
        terms = [f"%{q}%" for q in [title_q, subject_q, topic_q, content_q]]
        count_params.extend([q for pair in zip([title_q, subject_q, topic_q, content_q], terms) for q in pair])
    
    cursor.execute(f"SELECT COUNT(*) as count {base_query}", tuple(count_params))
    total_results = cursor.fetchone()['count']
    total_pages = ceil(total_results / per_page)
    offset = (page - 1) * per_page
    
    # Get results
    query_params = count_params.copy()
    cursor.execute(
        f"""SELECT * {base_query} 
        LIMIT ? OFFSET ?""",
        tuple(query_params + [per_page, offset])
    )
    
    results = cursor.fetchall()
    
    return render_template("search.html",
                         results=results,
                         title_q=title_q,
                         subject_q=subject_q,
                         topic_q=topic_q,
                         content_q=content_q,
                         search_type=search_type,
                         filter_type=filter_type,
                         page=page,
                         total_pages=total_pages,
                         total_results=total_results)


@app.route("/display_note/<int:note_id>")
@login_required
def display_note(note_id):
    """Allow viewing of selected note"""
    cursor.execute("""
        SELECT * FROM notes 
        WHERE id = ? AND user_id = ?
    """, (note_id, session["user_id"]))
    mem_note = cursor.fetchone()
    
    if not mem_note:
        flash("Note not found or access denied")
        return redirect("/")
        
    return render_template("display_note.html", this_note=mem_note)




@app.route("/edit_note/<int:note_id>", methods= ['GET', 'POST'])
@login_required
def edit_note(note_id):
    """Allow editing of selected note"""
    if request.method == "GET":
        cursor.execute("""
            SELECT * FROM notes 
            WHERE id = ? AND user_id = ?
        """, (note_id, session["user_id"]))
        mem_note = cursor.fetchone()
        
        if not mem_note:
            flash("Note not found or access denied")
            return redirect("/")
            
        return render_template("edit_note.html", this_note=mem_note)
        
    if request.method == "POST":
        # Verify note belongs to user before updating
        cursor.execute("""
            SELECT user_id FROM notes 
            WHERE id = ?
        """, (note_id,))
        note = cursor.fetchone()
        
        if not note or note['user_id'] != session["user_id"]:
            flash("Note not found or access denied")
            return redirect("/")
            
        title = request.form.get("title")
        if not title:
            return apology("Title is required")

        content = request.form.get("content")
        if not content:
            return apology("Content is required")
            
        subject = request.form.get("subject")
        if not subject:
            return apology("Subject is required")

        topic = request.form.get("topic")
        if not topic:
            return apology("Topic is required")

        params = (title, content, subject, topic, note_id, session["user_id"])
        cursor.execute("""
            UPDATE notes 
            SET title = ?, content = ?, subject = ?, topic = ? 
            WHERE id = ? AND user_id = ?
        """, params)
        db.commit()
        
        return redirect(url_for('display_note', note_id=note_id))



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


@app.route("/test_set_up")
# @login_required
def test_set_up():
    """Enter test parameter"""
    # user_id = int(session["user_id"])
    return render_template("test_set_up.html")


@app.route("/test")
# @login_required
def test():
    """Enter test parameter"""
    # user_id = int(session["user_id"])
    return render_template("test.html")




@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        cursor.execute(
            "SELECT * FROM users WHERE username = ?", 
            (request.form.get("username"),)
        )
        rows = cursor.fetchall()

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
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
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        
        # Validate input
        if not username:
            flash("Must provide username")
            return redirect("/register")
        elif not password:
            flash("Must provide password")
            return redirect("/register")
        elif not confirmation:
            flash("Must confirm password")
            return redirect("/register")
        elif password != confirmation:
            flash("Passwords must match")
            return redirect("/register")
            
        # Check if username exists
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            flash("Username already exists")
            return redirect("/register")
            
        # Add user to database
        cursor.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            (username, generate_password_hash(password))
        )
        db.commit()
        
        # Log user in
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        session["user_id"] = user["id"]
        
        flash("Registered!")
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
    if request.method == "GET":
        return render_template("create.html")
    
    if request.method == "POST":
        cursor.execute("""
            INSERT INTO notes (
                title, content, subject, topic, 
                question, correct_answer, 
                wrong_answer1, wrong_answer2, wrong_answer3,
                user_id
            ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form.get("title"),
            request.form.get("content"),
            request.form.get("subject"),
            request.form.get("topic"),
            request.form.get("question"),
            request.form.get("correct_answer"),
            request.form.get("wrong_answer1"),
            request.form.get("wrong_answer2"),
            request.form.get("wrong_answer3"),
            session["user_id"]
        ))
        db.commit()
        return redirect("/")

    return render_template("create.html")


@app.route("/start_test", methods=["GET", "POST"])
@login_required
def start_test():
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
        WHERE user_id = ?
        AND question IS NOT NULL 
        AND correct_answer IS NOT NULL
    """
    
    if filter_type == "weakest":
        base_query += """
            AND times_challenged > 0 
            ORDER BY CAST(times_correct AS FLOAT) / times_challenged ASC
        """
    elif filter_type == "untested":
        base_query += " AND times_challenged = 0 ORDER BY RANDOM()"
    else:  # random
        base_query += " ORDER BY RANDOM()"
    
    base_query += " LIMIT ?"
    
    # Get questions from database
    cursor.execute(base_query, (session["user_id"], n))
    questions = cursor.fetchall()
    
    # Convert to list of dicts for session storage
    question_list = []
    for q in questions:
        question_dict = dict(q)
        question_list.append(question_dict)
    
    # Initialize test session
    session["test_questions"] = question_list
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
#@login_required
def show_stats():
    page = int(request.args.get("page", 1))
    per_page = 10
    
    # Get total count for pagination
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM notes
        WHERE times_challenged > 0
    """)
    total_results = cursor.fetchone()['count']
    total_pages = ceil(total_results / per_page)
    offset = (page - 1) * per_page
    
    # Get paginated stats
    cursor.execute("""
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
    
    stats = cursor.fetchall()
    
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
    g.db = get_db()
    g.cursor = g.db.cursor()

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()

app.secret_key = 'your_secret_key_here'  # Change this to a secure value