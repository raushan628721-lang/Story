import unittest
import json
from werkzeug.security import generate_password_hash
from app import app
from database.db import DBManager

class TestStoryTeacherFullSuite(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_00_auth_flow(self):
        """Test Login, Register, and Logout routes."""
        # 1. GET /login
        res_login_get = self.client.get('/login')
        self.assertEqual(res_login_get.status_code, 200)
        self.assertIn(b'Welcome Back', res_login_get.data)

        # 2. POST /login with demo credentials
        res_login_post = self.client.post('/login', data={
            'email': 'demo@storyteacher.com',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_login_post.status_code, 200)
        self.assertIn(b'PARENT PORTAL', res_login_post.data)

        # 3. GET /logout
        res_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)
        self.assertIn(b'signed out', res_logout.data)

        # 4. POST /register (Teacher)
        import time
        t_stamp = int(time.time())
        res_reg = self.client.post('/register', data={
            'name': 'Prof. John Doe',
            'email': f'teacher_{t_stamp}@testedu.com',
            'password': 'password123',
            'role': 'teacher'
        }, follow_redirects=True)
        self.assertEqual(res_reg.status_code, 200)

        # 5. POST /register (Parent with own Child Name)
        res_parent_reg = self.client.post('/register', data={
            'name': 'Pooja Sharma',
            'email': f'parent_{t_stamp}@familytest.com',
            'password': 'password123',
            'role': 'parent',
            'child_name': 'Rohan Sharma',
            'child_age': '9',
            'child_grade': 'Grade 4'
        }, follow_redirects=True)
        self.assertEqual(res_parent_reg.status_code, 200)
        self.assertIn(b'Rohan Sharma', res_parent_reg.data)
        print("[PASS] 0. Authentication (Login, Logout, Teacher Register, Parent Register with Child) succeeded.")

    def test_01_home_page(self):
        """Test GET / landing page."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Story Teacher', res.data)
        self.assertIn(b'Learn Through Stories', res.data)
        print("[PASS] 1. Landing Home page loaded successfully.")

    def test_02_learn_page_and_generation(self):
        """Test GET /learn and POST /learn story & quiz generation."""
        res_get = self.client.get('/learn')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b'Create Your Child', res_get.data)

        # POST /learn
        res_post = self.client.post('/learn', data={
            'name': 'Aarav Sharma',
            'grade': 'Grade 5',
            'age': '10',
            'age_group': '9-12',
            'subject': 'Science',
            'topic': 'Photosynthesis',
            'difficulty': 'Medium'
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)
        self.assertIn(b'Section 1', res_post.data)
        self.assertIn(b'SpeechSynthesis Read-Aloud Assistant', res_post.data)
        print("[PASS] 2. Learn page & AI Story creation succeeded.")

    def test_03_story_and_quiz_flow(self):
        """Test GET /story/<id>, GET /quiz/<id>, and POST /submit-quiz."""
        story = DBManager.fetch_one("SELECT id FROM stories ORDER BY id DESC LIMIT 1")
        self.assertIsNotNone(story)
        story_id = story['id']

        # View story
        res_story = self.client.get(f'/story/{story_id}')
        self.assertEqual(res_story.status_code, 200)

        # View quiz
        res_quiz = self.client.get(f'/quiz/{story_id}')
        self.assertEqual(res_quiz.status_code, 200)
        self.assertIn(b'Question 1 of', res_quiz.data)

        # Submit quiz answers
        questions = DBManager.fetch_all("SELECT * FROM questions WHERE story_id = %s", (story_id,))
        self.assertGreaterEqual(len(questions), 5)
        
        child = DBManager.fetch_one("SELECT child_id FROM stories WHERE id = %s", (story_id,))
        submit_data = {
            'story_id': str(story_id),
            'child_id': str(child['child_id']),
            'start_time': '1000'
        }
        for q in questions:
            submit_data[f"question_{q['id']}"] = q['correct_answer']

        res_submit = self.client.post('/submit-quiz', data=submit_data, follow_redirects=True)
        self.assertEqual(res_submit.status_code, 200)
        self.assertIn(b'Comprehension Report for', res_submit.data)
        self.assertIn(b'100%', res_submit.data)
        self.assertIn(b'Excellent Understanding', res_submit.data)
        print("[PASS] 3. Story, Quiz, and Result evaluation flow succeeded.")

    def test_04_dashboard_and_analytics(self):
        """Test GET /dashboard strictly isolated per role: Student, Teacher, Parent, Admin."""
        # 1. Teacher Dashboard
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Prof. Amanda Foster'
            sess['user_role'] = 'teacher'
        res_teacher = self.client.get('/dashboard')
        self.assertEqual(res_teacher.status_code, 200)
        self.assertIn(b'Classroom Command Center', res_teacher.data)

        # 2. Student Dashboard
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_name'] = 'Alex Rivera'
            sess['user_role'] = 'student'
        res_student = self.client.get('/dashboard')
        self.assertEqual(res_student.status_code, 200)
        self.assertIn(b'STUDENT PORTAL', res_student.data)
        self.assertIn(b'Subject Mastery', res_student.data)
        self.assertIn(b'My Quiz Results', res_student.data)

        # 3. Parent Dashboard
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['user_name'] = 'Dr. Sarah Mitchell'
            sess['user_role'] = 'parent'
        res_parent = self.client.get('/dashboard')
        self.assertEqual(res_parent.status_code, 200)
        self.assertIn(b'Parental Growth &amp; Insights', res_parent.data)

        # 4. Admin Dashboard
        with self.client.session_transaction() as sess:
            sess['user_id'] = 4
            sess['user_name'] = 'System Administrator'
            sess['user_role'] = 'admin'
        res_admin = self.client.get('/dashboard')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'System Governance &amp; Platform Health', res_admin.data)

        print("[PASS] 4. Role-isolated dashboards (Student, Teacher, Parent, Admin) strictly verified.")

    def test_05_child_stories_reports_settings(self):
        """Test /students, /child/<id>, /stories, /reports, /settings."""
        # Unauthenticated /students redirects to login
        res_unauth = self.client.get('/students')
        self.assertEqual(res_unauth.status_code, 302)

        # Authenticated as Teacher
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_name'] = 'Prof. Amanda Foster'
            sess['user_role'] = 'teacher'

        # Students roster page
        res_students = self.client.get('/students')
        self.assertEqual(res_students.status_code, 200)
        self.assertIn(b'Student Profiles', res_students.data)

        # Add new student
        res_add_student = self.client.post('/students/add', data={
            'name': 'Kavya Reddy',
            'age': '11',
            'grade': 'Grade 6'
        }, follow_redirects=True)
        self.assertEqual(res_add_student.status_code, 200)
        self.assertIn(b'Kavya Reddy', res_add_student.data)

        child = DBManager.fetch_one("SELECT id FROM children LIMIT 1")
        self.assertIsNotNone(child)

        # Child profile
        res_child = self.client.get(f'/child/{child["id"]}')
        self.assertEqual(res_child.status_code, 200)
        self.assertIn(b'Learning Journey', res_child.data)

        # Stories archive
        res_stories = self.client.get('/stories')
        self.assertEqual(res_stories.status_code, 200)
        self.assertIn(b'Generated Educational Stories', res_stories.data)

        # Reports
        res_reports = self.client.get('/reports')
        self.assertEqual(res_reports.status_code, 200)
        self.assertIn(b'Academic Comprehension Reports', res_reports.data)

        # Settings
        res_settings = self.client.get('/settings')
        self.assertEqual(res_settings.status_code, 200)
        self.assertIn(b'Settings &amp; Preferences', res_settings.data)
        print("[PASS] 5. Students Roster, Child Profile, Stories Library, Reports, and Settings loaded.")

    def test_06_rest_apis(self):
        """Test all REST API endpoints."""
        # 1. API Generate Story
        res1 = self.client.post('/api/generate-story', json={
            'name': 'Maya', 'age': 8, 'grade': 'Grade 3', 'subject': 'Mathematics', 'topic': 'Fractions'
        })
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.data)
        self.assertTrue(data1['success'])
        self.assertIn('title', data1['story'])

        # 2. API Generate Quiz
        res2 = self.client.post('/api/generate-quiz', json={
            'story': data1['story'], 'age': 8, 'subject': 'Mathematics', 'topic': 'Fractions'
        })
        self.assertEqual(res2.status_code, 200)
        data2 = json.loads(res2.data)
        self.assertTrue(data2['success'])
        self.assertGreaterEqual(len(data2['quiz']), 5)

        # 3. API Dashboard
        res3 = self.client.get('/api/dashboard')
        self.assertEqual(res3.status_code, 200)
        data3 = json.loads(res3.data)
        self.assertTrue(data3['success'])

        # 4. API Children & Stories
        res4 = self.client.get('/api/children')
        self.assertEqual(res4.status_code, 200)
        res5 = self.client.get('/api/stories')
        self.assertEqual(res5.status_code, 200)
        print("[PASS] 6. REST API Endpoints verified successfully.")

    def test_07_admin_user_edit_delete(self):
        """Test Admin ability to edit user details and delete users."""
        import time
        ts = int(time.time() * 1000)
        # Create a temporary user to edit and delete
        pwd_hash = generate_password_hash("testpass")
        target_uid = DBManager.execute_insert(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ("Temp User", f"temp_user_{ts}@storyteacher.com", pwd_hash, "student")
        )
        self.assertIsNotNone(target_uid)

        # Set active session as Admin
        with self.client.session_transaction() as sess:
            sess['user_id'] = 4
            sess['user_name'] = 'System Administrator'
            sess['user_role'] = 'admin'

        # 1. Edit User
        res_edit = self.client.post(f'/admin/users/edit/{target_uid}', data={
            'name': 'Updated Temp User',
            'email': f'updated_user_{ts}@storyteacher.com',
            'role': 'teacher',
            'new_password': ''
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'updated successfully', res_edit.data)

        updated_user = DBManager.fetch_one("SELECT * FROM users WHERE id = %s", (target_uid,))
        self.assertEqual(updated_user['name'], 'Updated Temp User')
        self.assertEqual(updated_user['role'], 'teacher')

        # 2. Delete User
        res_delete = self.client.post(f'/admin/users/delete/{target_uid}', follow_redirects=True)
        self.assertEqual(res_delete.status_code, 200)
        self.assertIn(b'has been removed', res_delete.data)

        deleted_check = DBManager.fetch_one("SELECT * FROM users WHERE id = %s", (target_uid,))
        self.assertIsNone(deleted_check)

        print("[PASS] 7. Admin User Edit and Delete capabilities successfully verified.")

    def test_08_teacher_create_lesson_and_quiz(self):
        """Test Teacher creating new lessons and quizzes from Teacher Dashboard."""
        # Set active session as Teacher
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_name'] = 'Prof. Amanda Foster'
            sess['user_role'] = 'teacher'

        # 1. Teacher Create Lesson
        res_lesson = self.client.post('/teacher/create-lesson', data={
            'subject': 'Science',
            'topic': 'Photosynthesis & Sunlight',
            'grade': 'Grade 5',
            'age': '10',
            'difficulty': 'Medium',
            'custom_focus': 'Why leaves appear green'
        }, follow_redirects=True)
        self.assertEqual(res_lesson.status_code, 200)
        self.assertIn(b'created successfully', res_lesson.data)

        story = DBManager.fetch_one("SELECT * FROM stories WHERE topic LIKE %s ORDER BY id DESC LIMIT 1", ("%Photosynthesis & Sunlight%",))
        self.assertIsNotNone(story)

        # 2. Teacher Create Quiz
        res_quiz = self.client.post('/teacher/create-quiz', data={
            'story_id': str(story['id']),
            'subject': 'Science',
            'topic': 'Photosynthesis & Sunlight',
            'grade': 'Grade 5',
            'age': '10'
        }, follow_redirects=True)
        self.assertEqual(res_quiz.status_code, 200)
        self.assertIn(b'Successfully generated', res_quiz.data)

        questions = DBManager.fetch_all("SELECT * FROM questions WHERE story_id = %s", (story['id'],))
        self.assertGreaterEqual(len(questions), 5)

        print("[PASS] 8. Teacher Create Lesson & Create Quiz actions successfully verified.")

    def test_09_user_profile_edit(self):
        """Test universal profile editing (/profile/edit)."""
        import time
        ts = int(time.time() * 1000)
        pwd_hash = generate_password_hash("testpass")
        user_id = DBManager.execute_insert(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            (f'User Test {ts}', f'user_{ts}@test.com', pwd_hash, 'student')
        )

        # Login as this temporary user
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['user_name'] = f'User Test {ts}'
            sess['user_email'] = f'user_{ts}@test.com'
            sess['user_role'] = 'student'

        res_edit = self.client.post('/profile/edit', data={
            'name': f'User Renamed {ts}',
            'email': f'user_renamed_{ts}@test.com',
            'new_password': 'newpassword123'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'successfully updated', res_edit.data)

        # Verify DB updated
        user = DBManager.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
        self.assertEqual(user['name'], f'User Renamed {ts}')
        self.assertEqual(user['email'], f'user_renamed_{ts}@test.com')

        # Clean up
        DBManager.execute_update("DELETE FROM users WHERE id = %s", (user_id,))
        print("[PASS] 9. Universal Profile Edit successfully verified across dashboards.")

if __name__ == '__main__':
    unittest.main()
