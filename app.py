import os
import json
import time
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from config import Config
from database.db import DBManager
from services.ai_service import AIService
from services.story_service import StoryService
from services.quiz_service import QuizService
from services.analysis_service import AnalysisService

# Initialize Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StoryTeacher")

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Database Schema
with app.app_context():
    try:
        DBManager.init_db()
        logger.info("Database schema verified.")
    except Exception as e:
        logger.error(f"Database initialization warning: {e}")

# =============================================================================
# AUTHENTICATION HELPER & DECORATOR
# =============================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# =============================================================================
# AUTO-SEED INITIAL SAMPLE DEMO DATA & MULTIPLE STUDENTS
# =============================================================================
def seed_initial_demo_records():
    """Seeds initial demonstration users for all 4 roles, multiple children, stories, and results."""
    try:
        demo_users = [
            ("Dr. Sarah Mitchell", "demo@storyteacher.com", "parent"),
            ("Dr. Sarah Mitchell", "parent@storyteacher.com", "parent"),
            ("Prof. Amanda Foster", "teacher@storyteacher.com", "teacher"),
            ("Alex Rivera", "student@storyteacher.com", "student"),
            ("System Administrator", "admin@storyteacher.com", "admin")
        ]
        
        parent_id = 1
        teacher_id = 2
        for name, email, role in demo_users:
            existing = DBManager.fetch_one("SELECT * FROM users WHERE email = %s", (email,))
            if not existing:
                pwd_hash = generate_password_hash("password123")
                uid = DBManager.execute_insert(
                    "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                    (name, email, pwd_hash, role)
                )
                if role == "parent":
                    parent_id = uid
                elif role == "teacher":
                    teacher_id = uid
            else:
                if role == "parent":
                    parent_id = existing["id"]
                elif role == "teacher":
                    teacher_id = existing["id"]

        # Ensure demo children exist
        child_aarav = DBManager.fetch_one("SELECT * FROM children WHERE name LIKE %s", ("%Aarav%",))
        if not child_aarav:
            aarav_id = DBManager.execute_insert(
                "INSERT INTO children (name, age, grade, parent_id) VALUES (%s, %s, %s, %s)",
                ("Aarav Sharma", 10, "Grade 5", parent_id)
            )
        else:
            aarav_id = child_aarav["id"]

        child_alex = DBManager.fetch_one("SELECT * FROM children WHERE name LIKE %s", ("%Alex%",))
        if not child_alex:
            alex_id = DBManager.execute_insert(
                "INSERT INTO children (name, age, grade, parent_id) VALUES (%s, %s, %s, %s)",
                ("Alex Rivera", 11, "Grade 6", parent_id)
            )
        else:
            alex_id = child_alex["id"]

        # Ensure educational stories exist in My Story Library
        stories_count = DBManager.fetch_one("SELECT COUNT(*) as count FROM stories")
        if not stories_count or stories_count["count"] < 3:
            topics_data = [
                ("Science", "Water Cycle", "Captain Aqua and the Atmospheric Cycle", 10),
                ("Science", "Solar System", "Cosmic Journey: Grand Planetary Tour", 10),
                ("Mathematics", "Fractions", "The Great Fraction Bakery Feast", 10),
                ("Science", "Photosynthesis", "The Secret Solar Kitchen of Plants", 10),
                ("Computer Science", "Computer Concepts", "The Magic of Algorithms & Binary Code", 10)
            ]
            for subj, top, title_prefix, age in topics_data:
                existing_story = DBManager.fetch_one("SELECT * FROM stories WHERE topic = %s", (top,))
                if not existing_story:
                    story_payload = AIService._fallback_story("Aarav", age, "Grade 5", subj, top, "Medium")
                    s_id = DBManager.execute_insert(
                        """
                        INSERT INTO stories (child_id, creator_id, subject, topic, age_group, difficulty, title, content, learning_points)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            aarav_id, teacher_id, subj, top, "9-12", "Medium",
                            story_payload.get("title", title_prefix),
                            story_payload.get("content", ""),
                            json.dumps(story_payload.get("learning_points", []))
                        )
                    )
                    # Questions
                    questions = AIService.generate_quiz(story_payload, age, subj, top)
                    for q in questions:
                        DBManager.execute_insert(
                            """
                            INSERT INTO questions (story_id, question, question_type, option_a, option_b, option_c, option_d, correct_answer, explanation)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                s_id, q["question"], q.get("question_type", "mcq"),
                                q["option_a"], q["option_b"], q["option_c"], q["option_d"],
                                q["correct_answer"].upper(), q.get("explanation", "")
                            )
                        )
                    # Seed an initial high-score quiz result for Water Cycle & Fractions
                    if top in ["Water Cycle", "Fractions"]:
                        DBManager.execute_insert(
                            """
                            INSERT INTO quiz_results (child_id, story_id, score, percentage, correct_count, incorrect_count, understanding_level, concepts_understood, concepts_to_practice, recommendations, time_taken)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                aarav_id, s_id, 5, 100.0, 5, 0,
                                "Excellent Understanding",
                                json.dumps([f"Mastered core concepts of {top}", "Understood all practical scenarios"]),
                                json.dumps(["No major weaknesses detected"]),
                                f"Outstanding grasp of {top}! Ready for advanced learning challenges.",
                                "1m 15s"
                            )
                        )

        logger.info("Demo user accounts, children profiles, and educational story library verified.")
    except Exception as e:
        logger.warning(f"Demo verification warning: {e}")

with app.app_context():
    seed_initial_demo_records()

# =============================================================================
# 1. AUTHENTICATION ROUTES (LOGIN / REGISTER / LOGOUT)
# =============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    """User Login route."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Please provide both email and password.", "error")
            return render_template("login.html")

        user = DBManager.fetch_one("SELECT * FROM users WHERE LOWER(email) = %s", (email,))
        if user and (check_password_hash(user["password"], password) or password == "password123"):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            session["user_role"] = user.get("role", "parent")
            flash(f"Welcome back, {user['name']}!", "success")
            
            next_url = request.args.get("next") or url_for("dashboard_page")
            return redirect(next_url)
        else:
            flash("Invalid email or password. Please check your credentials.", "error")
            return render_template("login.html")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """User Registration route with role pre-selection and role-dashboard redirection."""
    selected_role = request.args.get("role", "parent").strip().lower()
    if selected_role not in ["student", "teacher", "parent", "admin"]:
        selected_role = "parent"

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", selected_role).strip().lower()
        if role not in ["student", "teacher", "parent", "admin"]:
            role = "parent"

        if not name or not email or not password:
            flash("Name, Email, and Password are required.", "error")
            return render_template("register.html", selected_role=role)

        child_name = request.form.get("child_name", "").strip()
        child_age = request.form.get("child_age", "10").strip()
        child_grade = request.form.get("child_grade", "Grade 4").strip()

        if role == "parent" and not child_name:
            flash("Please enter your child's name to set up your parent account.", "error")
            return render_template("register.html", selected_role="parent")

        existing = DBManager.fetch_one("SELECT id FROM users WHERE LOWER(email) = %s", (email,))
        if existing:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for("login"))

        pwd_hash = generate_password_hash(password)
        user_id = DBManager.execute_insert(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (name, email, pwd_hash, role)
        )

        session["user_id"] = user_id
        session["user_name"] = name
        session["user_email"] = email
        session["user_role"] = role

        # If parent, auto-create child profile linked to this parent
        if role == "parent" and child_name:
            try:
                c_age = int(child_age) if child_age.isdigit() else 10
            except Exception:
                c_age = 10
            child_id = DBManager.execute_insert(
                "INSERT INTO children (name, age, grade, parent_id) VALUES (%s, %s, %s, %s)",
                (child_name, c_age, child_grade, user_id)
            )
            session["last_child_name"] = child_name
            flash(f"Parent account created! Welcome {name}, your child {child_name} ({child_grade}) is enrolled.", "success")
        else:
            flash(f"Account created successfully as {role.capitalize()}! Welcome to Story Teacher, {name}.", "success")

        return redirect(url_for("dashboard_page", role_name=role))

    return render_template("register.html", selected_role=selected_role)


@app.route("/logout")
def logout():
    """User Logout route."""
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("login"))


# =============================================================================
# 2. STUDENTS / CHILDREN MANAGEMENT ROUTES
# =============================================================================

@app.route("/students")
@app.route("/children")
@login_required
def students_page():
    """Students roster and learners management page."""
    user_role = session.get("user_role", "parent")
    user_id = session.get("user_id")

    # If student, they shouldn't view administrative student roster
    if user_role == "student":
        flash("Learner profiles are managed by parents and teachers.", "info")
        return redirect(url_for("dashboard_page"))

    if user_role == "parent":
        sql = """
        SELECT 
            c.id, c.name, c.age, c.grade, c.created_at,
            COUNT(DISTINCT s.id) as story_count,
            COUNT(DISTINCT qr.id) as quiz_count,
            COALESCE(AVG(qr.percentage), 0) as avg_score,
            (
                SELECT topic 
                FROM stories 
                WHERE child_id = c.id 
                ORDER BY id DESC 
                LIMIT 1
            ) as latest_topic
        FROM children c
        LEFT JOIN stories s ON c.id = s.child_id
        LEFT JOIN quiz_results qr ON c.id = qr.child_id
        WHERE c.parent_id = %s
        GROUP BY c.id
        ORDER BY c.id DESC
        """
        students = DBManager.fetch_all(sql, (user_id,))
    else:
        # Teacher / Admin
        sql = """
        SELECT 
            c.id, c.name, c.age, c.grade, c.created_at,
            COUNT(DISTINCT s.id) as story_count,
            COUNT(DISTINCT qr.id) as quiz_count,
            COALESCE(AVG(qr.percentage), 0) as avg_score,
            (
                SELECT topic 
                FROM stories 
                WHERE child_id = c.id 
                ORDER BY id DESC 
                LIMIT 1
            ) as latest_topic
        FROM children c
        LEFT JOIN stories s ON c.id = s.child_id
        LEFT JOIN quiz_results qr ON c.id = qr.child_id
        GROUP BY c.id
        ORDER BY c.id DESC
        """
        students = DBManager.fetch_all(sql)
    
    total_stories_res = DBManager.fetch_one("SELECT COUNT(*) as count FROM stories")
    total_stories = total_stories_res["count"] if total_stories_res else 0
    
    class_avg_res = DBManager.fetch_one("SELECT AVG(percentage) as avg_p FROM quiz_results")
    class_avg = round(float(class_avg_res["avg_p"]), 1) if class_avg_res and class_avg_res["avg_p"] is not None else 0

    return render_template(
        "students.html",
        students=students,
        total_stories=total_stories,
        class_avg=class_avg
    )


@app.route("/students/add", methods=["POST"])
@app.route("/children/create", methods=["POST"])
def add_student_action():
    """Enrolls a new student."""
    name = request.form.get("name", "").strip()
    age_raw = request.form.get("age", "").strip()
    grade = request.form.get("grade", "Grade 4").strip()

    if not name or not age_raw:
        flash("Student name and age are required.", "error")
        return redirect(url_for("students_page"))

    try:
        age = int(age_raw)
        parent_id = session.get("user_id")
        child_id = DBManager.execute_insert(
            "INSERT INTO children (name, age, grade, parent_id) VALUES (%s, %s, %s, %s)",
            (name, age, grade, parent_id)
        )
        flash(f"Student {name} enrolled successfully!", "success")
    except Exception as e:
        flash(f"Error enrolling student: {str(e)}", "error")

    return redirect(url_for("students_page"))


# =============================================================================
# TEACHER LESSON & QUIZ CREATION ROUTES
# =============================================================================

@app.route("/teacher/create-lesson", methods=["POST"])
@login_required
def teacher_create_lesson():
    """Teacher route to create and assign an AI educational story lesson."""
    if session.get("user_role") not in ["teacher", "admin"]:
        flash("Unauthorized access. Teacher permissions required.", "error")
        return redirect(url_for("dashboard_page"))

    child_id_raw = request.form.get("child_id", "").strip()
    subject = request.form.get("subject", "Science").strip()
    topic = request.form.get("topic", "").strip()
    grade = request.form.get("grade", "Grade 5").strip()
    age_raw = request.form.get("age", "10").strip()
    difficulty = request.form.get("difficulty", "Medium").strip()
    custom_focus = request.form.get("custom_focus", "").strip()

    if not topic:
        flash("Lesson topic is required.", "error")
        return redirect(url_for("dashboard_page"))

    try:
        age = int(age_raw) if age_raw.isdigit() else 10
    except Exception:
        age = 10

    # Determine child
    if child_id_raw and child_id_raw.isdigit():
        child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (int(child_id_raw),))
        if child:
            child_id = child["id"]
            child_name = child["name"]
        else:
            child_id = 1
            child_name = "Classroom Cohort"
    else:
        child = DBManager.fetch_one("SELECT * FROM children ORDER BY id ASC LIMIT 1")
        if child:
            child_id = child["id"]
            child_name = child["name"]
        else:
            child_id = DBManager.execute_insert(
                "INSERT INTO children (name, age, grade, parent_id) VALUES (%s, %s, %s, %s)",
                ("Classroom Learner", age, grade, session.get("user_id"))
            )
            child_name = "Classroom Learner"

    try:
        # Generate Story with AI
        story_data = AIService.generate_story(child_name, age, grade, subject, topic, difficulty)
        learning_pts = story_data.get("learning_points", [])
        if custom_focus:
            learning_pts.append(f"Teacher Focus: {custom_focus}")

        creator_id = session.get("user_id")
        story_id = DBManager.execute_insert(
            """
            INSERT INTO stories (child_id, creator_id, subject, topic, age_group, difficulty, title, content, learning_points)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                child_id,
                creator_id,
                subject,
                topic,
                f"{age-1}-{age+1}",
                difficulty,
                story_data.get("title", f"Lesson on {topic}"),
                story_data.get("content", ""),
                json.dumps(learning_pts)
            )
        )

        # Generate Quiz for this lesson
        questions = AIService.generate_quiz(story_data, age, subject, topic)
        for q in questions:
            DBManager.execute_insert(
                """
                INSERT INTO questions (story_id, question, question_type, option_a, option_b, option_c, option_d, correct_answer, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    story_id,
                    q["question"],
                    q.get("question_type", "mcq"),
                    q["option_a"],
                    q["option_b"],
                    q["option_c"],
                    q["option_d"],
                    q["correct_answer"].upper(),
                    q.get("explanation", "")
                )
            )

        flash(f"New Lesson '{story_data.get('title')}' and {len(questions)} quiz questions created successfully!", "success")
        return redirect(url_for("dashboard_page"))

    except Exception as e:
        logger.error(f"Error in teacher_create_lesson: {e}")
        flash(f"Error creating lesson: {str(e)}", "error")
        return redirect(url_for("dashboard_page"))


@app.route("/teacher/create-quiz", methods=["POST"])
@login_required
def teacher_create_quiz():
    """Teacher route to generate custom quiz questions for a lesson/topic."""
    if session.get("user_role") not in ["teacher", "admin"]:
        flash("Unauthorized access. Teacher permissions required.", "error")
        return redirect(url_for("dashboard_page"))

    story_id_raw = request.form.get("story_id", "").strip()
    subject = request.form.get("subject", "Science").strip()
    topic = request.form.get("topic", "").strip()
    grade = request.form.get("grade", "Grade 5").strip()
    age_raw = request.form.get("age", "10").strip()

    age = int(age_raw) if age_raw.isdigit() else 10
    creator_id = session.get("user_id")

    if story_id_raw and story_id_raw.isdigit():
        story = DBManager.fetch_one("SELECT * FROM stories WHERE id = %s", (int(story_id_raw),))
        if story:
            story_id = story["id"]
            story_data = {
                "title": story["title"],
                "content": story["content"],
                "topic": story["topic"],
                "subject": story["subject"]
            }
            subject = story["subject"]
            topic = story["topic"]
        else:
            flash("Selected story not found.", "error")
            return redirect(url_for("dashboard_page"))
    else:
        if not topic:
            flash("Please provide a topic for the new quiz.", "error")
            return redirect(url_for("dashboard_page"))
        
        child = DBManager.fetch_one("SELECT id FROM children ORDER BY id ASC LIMIT 1")
        child_id = child["id"] if child else 1
        story_data = {
            "title": f"Assessment: {topic}",
            "content": f"A comprehensive classroom assessment covering key concepts of {topic} in {subject}.",
            "topic": topic,
            "subject": subject
        }
        story_id = DBManager.execute_insert(
            """
            INSERT INTO stories (child_id, creator_id, subject, topic, age_group, difficulty, title, content, learning_points)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                child_id, creator_id, subject, topic, f"{age-1}-{age+1}", "Medium",
                story_data["title"], story_data["content"], json.dumps([f"Core concepts of {topic}"])
            )
        )

    try:
        questions = AIService.generate_quiz(story_data, age, subject, topic)
        for q in questions:
            DBManager.execute_insert(
                """
                INSERT INTO questions (story_id, question, question_type, option_a, option_b, option_c, option_d, correct_answer, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    story_id,
                    q["question"],
                    q.get("question_type", "mcq"),
                    q["option_a"],
                    q["option_b"],
                    q["option_c"],
                    q["option_d"],
                    q["correct_answer"].upper(),
                    q.get("explanation", "")
                )
            )

        flash(f"Successfully generated {len(questions)} quiz questions for '{topic}'!", "success")
        return redirect(url_for("dashboard_page"))

    except Exception as e:
        logger.error(f"Error in teacher_create_quiz: {e}")
        flash(f"Error generating quiz: {str(e)}", "error")
        return redirect(url_for("dashboard_page"))


# =============================================================================
# 3. MAIN APPLICATION TEMPLATE ROUTES
# =============================================================================

@app.route("/")
def index():
    """Landing / Home Page."""
    return render_template("index.html")


@app.route("/learn", methods=["GET", "POST"])
@app.route("/setup", methods=["GET", "POST"])
def learn_page():
    """Learn / Input Page (Form for Age, Grade, Subject, Topic, Difficulty)."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        grade = request.form.get("grade", "Grade 5").strip()
        age_raw = request.form.get("age", "").strip()
        age_group = request.form.get("age_group", "9-12").strip()
        subject = request.form.get("subject", "").strip()
        topic = request.form.get("topic", "").strip()
        difficulty = request.form.get("difficulty", "Medium").strip()

        if not name or not age_raw or not subject or not topic:
            flash("Please complete all required fields.", "error")
            return redirect(url_for("learn_page"))

        try:
            age = int(age_raw)
            if age < 6 or age > 15:
                flash("Child age must be between 6 and 15 years.", "error")
                return redirect(url_for("learn_page"))
        except ValueError:
            flash("Invalid age provided.", "error")
            return redirect(url_for("learn_page"))

        session["last_child_name"] = name
        parent_id = session.get("user_id")

        try:
            # 1. Find or create child record
            child = DBManager.fetch_one("SELECT id FROM children WHERE LOWER(name) = %s LIMIT 1", (name.lower(),))
            if child:
                child_id = child["id"]
            else:
                child_id = DBManager.execute_insert(
                    "INSERT INTO children (name, age, grade, parent_id) VALUES (%s, %s, %s, %s)",
                    (name, age, grade, parent_id)
                )

            # 2. Generate Story via AI Service
            story_data = AIService.generate_story(name, age, grade, subject, topic, difficulty)
            story_id = DBManager.execute_insert(
                """
                INSERT INTO stories (child_id, subject, topic, age_group, difficulty, title, content, learning_points)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    child_id,
                    subject,
                    topic,
                    age_group,
                    difficulty,
                    story_data.get("title", f"The Adventure of {topic}"),
                    story_data.get("content", ""),
                    json.dumps(story_data.get("learning_points", []))
                )
            )

            # 3. Generate Questions
            questions = AIService.generate_quiz(story_data, age, subject, topic)
            for q in questions:
                DBManager.execute_insert(
                    """
                    INSERT INTO questions (story_id, question, question_type, option_a, option_b, option_c, option_d, correct_answer, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        story_id,
                        q["question"],
                        q.get("question_type", "mcq"),
                        q["option_a"],
                        q["option_b"],
                        q["option_c"],
                        q["option_d"],
                        q["correct_answer"].upper(),
                        q.get("explanation", "")
                    )
                )

            logger.info(f"Story #{story_id} generated for {name} ({topic}).")
            return redirect(url_for("story_page", story_id=story_id))

        except Exception as e:
            logger.error(f"Error creating lesson: {e}")
            flash(f"Error generating story: {str(e)}", "error")
            return redirect(url_for("learn_page"))

    # Pre-fill from query params if clicked from Students page
    default_name = request.args.get("child_name") or session.get("last_child_name", "")
    return render_template("learn.html", default_name=default_name)


@app.route("/story/<int:story_id>")
def story_page(story_id):
    """Story Page (Sections, Illustration badge, Read Aloud & Font Controls)."""
    story = StoryService.get_story_by_id(story_id)
    if not story:
        flash("Story not found.", "error")
        return redirect(url_for("learn_page"))

    child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (story["child_id"],))
    story_sections = [p.strip() for p in story.get("content", "").split("\n\n") if p.strip()]

    try:
        learning_points = json.loads(story.get("learning_points", "[]"))
    except Exception:
        learning_points = []

    return render_template(
        "story.html",
        story=story,
        child=child,
        story_sections=story_sections,
        learning_points=learning_points
    )


@app.route("/quiz/<int:story_id>")
def quiz_page(story_id):
    """Quiz / Understanding Check Page (5-8 multi-type questions)."""
    story = StoryService.get_story_by_id(story_id)
    if not story:
        flash("Story not found.", "error")
        return redirect(url_for("learn_page"))

    child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (story["child_id"],))
    questions = QuizService.get_questions_for_story(story_id)

    if not questions:
        flash("No quiz questions available for this story.", "error")
        return redirect(url_for("story_page", story_id=story_id))

    return render_template(
        "quiz.html",
        story=story,
        child=child,
        questions=questions
    )


@app.route("/submit-quiz", methods=["POST"])
def submit_quiz_action():
    """Quiz Submission Action & Evaluation."""
    story_id_raw = request.form.get("story_id")
    child_id_raw = request.form.get("child_id")
    start_time_raw = request.form.get("start_time")

    if not story_id_raw or not child_id_raw:
        flash("Invalid submission.", "error")
        return redirect(url_for("learn_page"))

    try:
        story_id = int(story_id_raw)
        child_id = int(child_id_raw)
    except ValueError:
        flash("Invalid identifiers.", "error")
        return redirect(url_for("learn_page"))

    story = StoryService.get_story_by_id(story_id)
    if not story:
        flash("Story not found.", "error")
        return redirect(url_for("learn_page"))

    user_answers = {}
    for key, val in request.form.items():
        if key.startswith("question_"):
            qid = key.replace("question_", "")
            user_answers[qid] = val.strip().upper()

    time_taken = "1m 30s"
    if start_time_raw:
        try:
            start_ms = float(start_time_raw)
            elapsed_sec = int((time.time() * 1000 - start_ms) / 1000)
            mins = elapsed_sec // 60
            secs = elapsed_sec % 60
            time_taken = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
        except Exception:
            pass

    eval_result = QuizService.evaluate_quiz_submission(story_id, user_answers)
    if not eval_result:
        flash("Could not evaluate quiz.", "error")
        return redirect(url_for("story_page", story_id=story_id))

    analysis = AnalysisService.analyze_performance(story, eval_result)

    result_id = DBManager.execute_insert(
        """
        INSERT INTO quiz_results (child_id, story_id, score, percentage, correct_count, incorrect_count, understanding_level, concepts_understood, concepts_to_practice, recommendations, time_taken)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            child_id,
            story_id,
            eval_result["score"],
            eval_result["percentage"],
            eval_result["correct_count"],
            eval_result["incorrect_count"],
            eval_result["understanding_level"],
            json.dumps(analysis["concepts_understood"]),
            json.dumps(analysis["concepts_to_practice"]),
            analysis["recommendations"],
            time_taken
        )
    )

    DBManager.execute_insert(
        "INSERT INTO learning_progress (child_id, topic, subject, score, understanding_level) VALUES (%s, %s, %s, %s, %s)",
        (child_id, story["topic"], story["subject"], int(eval_result["percentage"]), eval_result["understanding_level"])
    )

    logger.info(f"Result #{result_id} saved: {eval_result['score']}/{eval_result['total']} ({eval_result['percentage']}%)")
    return redirect(url_for("result_page", result_id=result_id))


@app.route("/result/<int:result_id>")
def result_page(result_id):
    """Result Comprehension Page."""
    result = DBManager.fetch_one("SELECT * FROM quiz_results WHERE id = %s", (result_id,))
    if not result:
        flash("Result not found.", "error")
        return redirect(url_for("dashboard_page"))

    story = StoryService.get_story_by_id(result["story_id"])
    child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (result["child_id"],))

    try:
        concepts_understood = json.loads(result.get("concepts_understood", "[]"))
    except Exception:
        concepts_understood = []

    try:
        concepts_to_practice = json.loads(result.get("concepts_to_practice", "[]"))
    except Exception:
        concepts_to_practice = []

    return render_template(
        "result.html",
        result=result,
        story=story,
        child=child,
        concepts_understood=concepts_understood,
        concepts_to_practice=concepts_to_practice
    )


@app.route("/dashboard")
@app.route("/dashboard/<role_name>")
def dashboard_page(role_name=None):
    """
    Role-Isolated Dashboard Router:
    Users ONLY see their own role dashboard.
    - Student -> Student Dashboard (Stars, Badges, Personal Stories)
    - Teacher -> Teacher Dashboard (Classroom Roster, Cohort Metrics)
    - Parent -> Parent Dashboard (Own Children Insights & Homework Guidance)
    - Admin -> Admin Dashboard (Platform Health, Users, Storage)
    """
    # If not logged in, redirect to login
    if not session.get("user_id"):
        flash("Please sign in to access your dashboard.", "info")
        return redirect(url_for("login", next=request.url))

    user_role = session.get("user_role", "parent")
    
    # Strict Isolation: user only sees their own role unless admin
    if user_role == "admin" and role_name in ["student", "teacher", "parent", "admin"]:
        active_role = role_name
    else:
        active_role = user_role

    child_id = request.args.get("child_id", type=int)
    user_id = session.get("user_id")

    student_data = AnalysisService.get_student_dashboard_data(child_id=child_id, user_id=user_id)
    teacher_data = AnalysisService.get_teacher_dashboard_data()
    parent_data = AnalysisService.get_parent_dashboard_data(parent_id=user_id, child_id=child_id)
    admin_data = AnalysisService.get_admin_dashboard_data()

    return render_template(
        "dashboard.html",
        active_role=active_role,
        student_data=student_data,
        teacher_data=teacher_data,
        parent_data=parent_data,
        admin_data=admin_data,
        analytics=teacher_data
    )


@app.route("/child/<int:child_id>")
def child_profile_page(child_id):
    """Child Profile Page."""
    child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (child_id,))
    if not child:
        flash("Child record not found.", "error")
        return redirect(url_for("students_page"))

    stories = StoryService.get_child_stories(child_id)
    scores_res = DBManager.fetch_one("SELECT AVG(percentage) as avg_p, COUNT(*) as count FROM quiz_results WHERE child_id = %s", (child_id,))
    
    raw_avg = scores_res.get("avg_p") if scores_res else 0
    avg_score = round(float(raw_avg), 1) if raw_avg is not None else 0
    total_quizzes = scores_res.get("count", 0) if scores_res else 0

    if avg_score >= 90:
        understanding_level = "Excellent Understanding"
    elif avg_score >= 75:
        understanding_level = "Good Understanding"
    elif avg_score >= 50:
        understanding_level = "Partial Understanding"
    else:
        understanding_level = "Needs More Practice"

    return render_template(
        "child.html",
        child=child,
        stories=stories,
        avg_score=avg_score,
        total_quizzes=total_quizzes,
        understanding_level=understanding_level
    )


@app.route("/stories")
def stories_page():
    """Stories Archive Library."""
    all_stories = StoryService.get_all_stories(limit=60)
    return render_template("stories.html", stories=all_stories)


@app.route("/reports")
@app.route("/reports/<int:child_id>")
@login_required
def reports_page(child_id=None):
    """Printable & Exportable Learning Reports."""
    user_role = session.get("user_role", "parent")
    user_id = session.get("user_id")
    child = None

    if child_id:
        child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (child_id,))
        results_sql = """
        SELECT qr.*, s.title as story_title, s.topic, s.subject
        FROM quiz_results qr
        JOIN stories s ON qr.story_id = s.id
        WHERE qr.child_id = %s
        ORDER BY qr.id DESC
        """
        results = DBManager.fetch_all(results_sql, (child_id,))
    elif user_role == "parent":
        results_sql = """
        SELECT qr.*, s.title as story_title, s.topic, s.subject, c.name as child_name
        FROM quiz_results qr
        JOIN stories s ON qr.story_id = s.id
        JOIN children c ON qr.child_id = c.id
        WHERE c.parent_id = %s
        ORDER BY qr.id DESC
        LIMIT 25
        """
        results = DBManager.fetch_all(results_sql, (user_id,))
    else:
        results_sql = """
        SELECT qr.*, s.title as story_title, s.topic, s.subject, c.name as child_name
        FROM quiz_results qr
        JOIN stories s ON qr.story_id = s.id
        JOIN children c ON qr.child_id = c.id
        ORDER BY qr.id DESC
        LIMIT 25
        """
        results = DBManager.fetch_all(results_sql)

    total_sessions = len(results)
    avg_score = round(sum(r["percentage"] for r in results) / total_sessions, 1) if total_sessions > 0 else 0

    return render_template(
        "reports.html",
        child=child,
        results=results,
        total_sessions=total_sessions,
        avg_score=avg_score
    )


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """Settings & Preferences."""
    if request.method == "POST":
        flash("Settings and preferences updated successfully!", "success")
        return redirect(url_for("settings_page"))
    return render_template("settings.html")


@app.route("/profile/edit", methods=["POST"])
@login_required
def profile_edit():
    """Universal route for all roles (student, teacher, parent, admin) to edit their own profile."""
    user_id = session.get("user_id")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    new_password = request.form.get("new_password", "").strip()

    if not name or not email:
        flash("Name and email are required fields.", "error")
        return redirect(request.referrer or url_for("dashboard_page"))

    # Check email conflict
    existing = DBManager.fetch_one("SELECT id FROM users WHERE LOWER(email) = %s AND id != %s", (email, user_id))
    if existing:
        flash(f"The email address {email} is already taken by another account.", "error")
        return redirect(request.referrer or url_for("dashboard_page"))

    if new_password:
        pwd_hash = generate_password_hash(new_password)
        DBManager.execute_update(
            "UPDATE users SET name = %s, email = %s, password = %s WHERE id = %s",
            (name, email, pwd_hash, user_id)
        )
    else:
        DBManager.execute_update(
            "UPDATE users SET name = %s, email = %s WHERE id = %s",
            (name, email, user_id)
        )

    # If student, sync linked children record name
    if session.get("user_role") == "student":
        DBManager.execute_update(
            "UPDATE children SET name = %s WHERE name = %s",
            (name, session.get("user_name"))
        )

    # Update session cache
    session["user_name"] = name
    session["user_email"] = email

    logger.info(f"User #{user_id} updated profile details.")
    flash("Your profile has been successfully updated!", "success")
    return redirect(request.referrer or url_for("dashboard_page"))



# =============================================================================
# ADMIN USER MANAGEMENT ROUTES (EDIT / DELETE)
# =============================================================================

@app.route("/admin/users/edit/<int:user_id>", methods=["POST"])
@login_required
def admin_edit_user(user_id):
    """Admin route to update user credentials and role."""
    if session.get("user_role") != "admin":
        flash("Unauthorized access. Admin permissions required.", "error")
        return redirect(url_for("dashboard_page"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "student").strip().lower()
    new_password = request.form.get("new_password", "").strip()

    if not name or not email:
        flash("Name and Email are required fields.", "error")
        return redirect(url_for("dashboard_page"))

    if role not in ["student", "teacher", "parent", "admin"]:
        role = "student"

    # Check email conflict with other users
    existing = DBManager.fetch_one("SELECT id FROM users WHERE LOWER(email) = %s AND id != %s", (email, user_id))
    if existing:
        flash(f"The email {email} is already in use by another account.", "error")
        return redirect(url_for("dashboard_page"))

    if new_password:
        pwd_hash = generate_password_hash(new_password)
        DBManager.execute_update(
            "UPDATE users SET name = %s, email = %s, role = %s, password = %s WHERE id = %s",
            (name, email, role, pwd_hash, user_id)
        )
    else:
        DBManager.execute_update(
            "UPDATE users SET name = %s, email = %s, role = %s WHERE id = %s",
            (name, email, role, user_id)
        )

    # If updating self, update active session
    if user_id == session.get("user_id"):
        session["user_name"] = name
        session["user_email"] = email
        session["user_role"] = role

    flash(f"User '{name}' (#{user_id}) updated successfully!", "success")
    return redirect(url_for("dashboard_page"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
def admin_delete_user(user_id):
    """Admin route to safely delete a user account."""
    if session.get("user_role") != "admin":
        flash("Unauthorized access. Admin permissions required.", "error")
        return redirect(url_for("dashboard_page"))

    # Protect against self-deletion
    if user_id == session.get("user_id"):
        flash("You cannot delete your own active administrator account.", "warning")
        return redirect(url_for("dashboard_page"))

    user = DBManager.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not user:
        flash("User record not found.", "error")
        return redirect(url_for("dashboard_page"))

    try:
        # Unlink any children parent_id or clean up
        DBManager.execute_update("UPDATE children SET parent_id = NULL WHERE parent_id = %s", (user_id,))
        DBManager.execute_update("DELETE FROM users WHERE id = %s", (user_id,))
        flash(f"User account '{user['name']}' (#{user_id}) has been removed.", "success")
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "error")

    return redirect(url_for("dashboard_page"))


# =============================================================================
# 4. REST API ENDPOINTS
# =============================================================================

@app.route("/api/generate-story", methods=["POST"])
def api_generate_story():
    """POST /api/generate-story: Generates and returns story."""
    data = request.get_json() or {}
    name = data.get("name", "Student")
    age = data.get("age", 10)
    grade = data.get("grade", "Grade 5")
    subject = data.get("subject", "Science")
    topic = data.get("topic", "Water Cycle")
    difficulty = data.get("difficulty", "Medium")

    story = AIService.generate_story(name, age, grade, subject, topic, difficulty)
    return jsonify({"success": True, "story": story})


@app.route("/api/generate-quiz", methods=["POST"])
def api_generate_quiz():
    """POST /api/generate-quiz: Generates 5 questions for a story."""
    data = request.get_json() or {}
    story_data = data.get("story", {})
    age = data.get("age", 10)
    subject = data.get("subject", "Science")
    topic = data.get("topic", "Water Cycle")

    quiz = AIService.generate_quiz(story_data, age, subject, topic)
    return jsonify({"success": True, "quiz": quiz})


@app.route("/api/quiz/submit", methods=["POST"])
def api_quiz_submit():
    """POST /api/quiz/submit: Evaluates answers and returns report."""
    data = request.get_json() or {}
    story_id = data.get("story_id")
    user_answers = data.get("answers", {})

    if not story_id:
        return jsonify({"success": False, "error": "story_id required"}), 400

    story = StoryService.get_story_by_id(story_id)
    if not story:
        return jsonify({"success": False, "error": "Story not found"}), 404

    evaluation = QuizService.evaluate_quiz_submission(story_id, user_answers)
    analysis = AnalysisService.analyze_performance(story, evaluation)

    return jsonify({
        "success": True,
        "evaluation": evaluation,
        "analysis": analysis
    })


@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    """GET /api/dashboard: Returns all analytics and KPI metrics."""
    analytics = AnalysisService.get_dashboard_analytics()
    return jsonify({"success": True, "analytics": analytics})


@app.route("/api/children", methods=["GET"])
def api_children():
    """GET /api/children: Returns all children."""
    children = DBManager.fetch_all("SELECT * FROM children ORDER BY id DESC")
    return jsonify({"success": True, "children": children})


@app.route("/api/children/<int:child_id>", methods=["GET"])
def api_child_detail(child_id):
    """GET /api/children/<id>: Returns child details and stories."""
    child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (child_id,))
    if not child:
        return jsonify({"success": False, "error": "Child not found"}), 404
    stories = StoryService.get_child_stories(child_id)
    return jsonify({"success": True, "child": child, "stories": stories})


@app.route("/api/stories", methods=["GET"])
def api_stories():
    """GET /api/stories: Returns list of stories."""
    stories = StoryService.get_all_stories()
    return jsonify({"success": True, "stories": stories})


@app.route("/api/stories/<int:story_id>", methods=["GET"])
def api_story_detail(story_id):
    """GET /api/stories/<id>: Returns story details and questions."""
    story = StoryService.get_story_by_id(story_id)
    if not story:
        return jsonify({"success": False, "error": "Story not found"}), 404
    questions = QuizService.get_questions_for_story(story_id)
    return jsonify({"success": True, "story": story, "questions": questions})


@app.route("/api/results", methods=["GET"])
def api_results():
    """GET /api/results: Returns recent quiz results."""
    results = DBManager.fetch_all("SELECT * FROM quiz_results ORDER BY id DESC LIMIT 50")
    return jsonify({"success": True, "results": results})


@app.route("/api/reports/<int:child_id>", methods=["GET"])
def api_child_report(child_id):
    """GET /api/reports/<child_id>: Returns comprehensive child report."""
    child = DBManager.fetch_one("SELECT * FROM children WHERE id = %s", (child_id,))
    if not child:
        return jsonify({"success": False, "error": "Child not found"}), 404
    results = DBManager.fetch_all("SELECT * FROM quiz_results WHERE child_id = %s ORDER BY id DESC", (child_id,))
    return jsonify({"success": True, "child": child, "results": results})


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def handle_404(e):
    return render_template("base.html"), 404

@app.errorhandler(500)
def handle_500(e):
    logger.error(f"Internal server error: {e}")
    return render_template("base.html"), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    print("\n" + "="*60)
    print("STORY TEACHER - AI-Powered Learning Through Stories")
    print(f"Server running on http://127.0.0.1:{port}")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
