# 📖 STORY TEACHER – AI-Powered Learning Through Stories

> *"Learn it. Live it. Remember it."*

**Story Teacher** is a full-stack educational web application that teaches school concepts to children (ages 6–15) through engaging, age-adapted AI stories, tests their true comprehension via multi-type interactive quizzes, and provides comprehensive pedagogical progress analytics for parents and educators.

---

## 🌟 Application Architecture (10 Main Pages)

1. **Landing / Home Page (`/`)**: Hero section (*"Learn Through Stories"*), 4 educational feature cards, 5-step interactive workflow, and CTA buttons.
2. **Learn / Input Page (`/learn` / `/setup`)**: Customizer form with Child Name, Grade (Grade 1–10), Age (6–15), Age Tier (6–8, 9–12, 13–15), Academic Subject, Educational Topic, and Difficulty selector.
3. **Story Reading Page (`/story/<id>`)**: Story chapters/sections, key concept takeaways, **SpeechSynthesis Read-Aloud (Play, Pause, Stop)**, and font size scaling.
4. **Quiz / Understanding Check (`/quiz/<id>`)**: Multi-format comprehension quiz (MCQ, True/False, Real-World Scenario, Fill-in-the-Blank), live animated progress bar, and answer validation.
5. **Result & Comprehension Page (`/result/<id>`)**: Circular score gauge, percentage, comprehension level, *Concepts Understood*, *Concepts That Need Practice*, pedagogical recommendations, and retry/next-topic actions.
6. **Parent & Teacher Dashboard (`/dashboard`)**: Sidebar control center, 4 metric KPI cards, **Chart.js topic-wise performance bar chart & score distribution doughnut chart**, recent activities table, and weak vs. strong topics.
7. **Child Profile Page (`/child/<id>`)**: Child details, learning history, average scores, and past topic explorations.
8. **Stories Archive (`/stories`)**: Card grid library of previously created stories with subject filters, difficulty, and quick reading buttons.
9. **Academic Learning Report (`/reports` / `/reports/<child_id>`)**: Parent and teacher friendly printable report with `window.print()` support.
10. **Settings & Preferences (`/settings`)**: Profile info, language preferences, speech synthesis speed, story font size, and notification toggles.

---

## 🛠️ Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3.3, Bootstrap Icons 1.11.3, Chart.js 4.4.2, Google Fonts (`Fredoka`, `Plus Jakarta Sans`, `Outfit`).
- **Backend**: Python 3.10+, Flask 3.0.3, Jinja2 template engine.
- **Database**: MySQL (`story_teacher` database) with automated seamless local SQLite fallback (`database/story_teacher.db`).
- **AI Service**: Multi-provider generative AI (Google Gemini / OpenAI compatible REST APIs) with a smart offline pedagogical fallback engine.
- **Environment**: `python-dotenv`.

---

## 📁 Project Folder Structure

```
story-teacher/
│
├── app.py                      # Main Flask Application, 10 Template Routes & REST APIs
├── config.py                   # Environment & Database Configuration
├── requirements.txt            # Python Dependencies
├── .env.example                # Sample Environment Variables
├── .env                        # Active Environment Settings
├── database.sql                # Complete MySQL Schema DDL Script
├── schema.sql                  # Alternate Schema Compatibility DDL
├── README.md                   # Full System Documentation
├── test_app.py                 # Automated Test Suite for All Pages & REST Endpoints
│
├── services/
│   ├── __init__.py             # Modular Services Initializer
│   ├── ai_service.py           # Multi-Provider AI Engine & 5 Offline Demo Fallback Datasets
│   ├── story_service.py        # Story Retrieval & Database Operations
│   ├── quiz_service.py         # Multi-Format Quiz Evaluator
│   └── analysis_service.py     # Pedagogical Diagnostics & Chart.js Aggregations
│
├── templates/
│   ├── base.html               # Master Layout, Navigation & Chart.js Script
│   ├── index.html              # 1. Landing / Home Page
│   ├── learn.html              # 2. Learn / Input Setup Page
│   ├── story.html              # 3. Story Reader with SpeechSynthesis Controls
│   ├── quiz.html               # 4. Multi-Format Interactive Quiz Page
│   ├── result.html             # 5. Result & Pedagogical Recommendations Page
│   ├── dashboard.html          # 6. Parent/Teacher Dashboard with Chart.js
│   ├── child.html              # 7. Child Profile & Learning History Page
│   ├── stories.html            # 8. Stories Archive & Library Page
│   ├── reports.html            # 9. Printable Academic Report Page
│   └── settings.html           # 10. Settings & Reading Preferences Page
│
├── static/
│   ├── css/
│   │   └── style.css           # Modern Educational Design System & Color Palette
│   └── js/
│       └── app.js              # SpeechSynthesis, Quiz Stepper & Form Validation
│
└── database/
    ├── README.md               # Database Configuration Guide
    ├── db.py                   # Universal Database Abstraction Layer (MySQL + SQLite)
    └── story_teacher.db        # Ready-to-Use Local Database
```

---

## 🗄️ Database Schema (`database.sql`)

The database consists of 6 relational tables:

1. `users` (id, name, email, password, role, created_at)
2. `children` (id, name, age, grade, parent_id, created_at)
3. `stories` (id, child_id, subject, topic, age_group, difficulty, title, content, learning_points, created_at)
4. `questions` (id, story_id, question, question_type, option_a, option_b, option_c, option_d, correct_answer, explanation)
5. `quiz_results` (id, child_id, story_id, score, percentage, correct_count, incorrect_count, understanding_level, concepts_understood, concepts_to_practice, recommendations, time_taken, created_at)
6. `learning_progress` (id, child_id, topic, subject, score, understanding_level, created_at)

---

## 🔌 REST API Documentation

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/generate-story` | Generates a structured educational story from parameters. |
| `POST` | `/api/generate-quiz` | Generates 5 multi-type questions for a given story. |
| `POST` | `/api/quiz/submit` | Evaluates submitted answers, calculating score & diagnostic recommendations. |
| `GET` | `/api/dashboard` | Returns aggregated metrics, KPI totals, and Chart.js datasets. |
| `GET` | `/api/children` | Returns all registered child profiles. |
| `GET` | `/api/children/<id>` | Returns specific child details with their complete story history. |
| `GET` | `/api/stories` | Returns a list of all created educational stories. |
| `GET` | `/api/stories/<id>` | Returns full story content and its associated quiz questions. |
| `GET` | `/api/results` | Returns recent quiz evaluation records. |
| `GET` | `/api/reports/<child_id>` | Returns comprehensive academic report data for a child. |

---

## 🚀 Installation & Setup Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (`.env`)
```env
FLASK_SECRET_KEY=story_teacher_secret_key_2026_secure
FLASK_ENV=development
FLASK_DEBUG=1
PORT=5000

# MySQL Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=story_teacher

# AI Configuration (Optional: leave blank for offline Demo Mode)
AI_PROVIDER=gemini
AI_API_KEY=
AI_MODEL=gemini-1.5-flash
```

### 3. Setup MySQL (Optional)
```bash
mysql -u root -p < database.sql
```
*(If MySQL is not running, the application automatically uses the local `database/story_teacher.db` fallback engine).*

### 4. Start the Application
```bash
python app.py
```

### 5. Open in Browser
👉 **`http://127.0.0.1:5000`**

### 6. Run Test Suite
```bash
python test_app.py
```
*(All 6 unit & integration test suites verify all 10 pages and REST APIs with 100% pass rate).*
