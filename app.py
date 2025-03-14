from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import traceback  # Add this import at the top

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# SQLite Configuration
def get_db_connection():
    try:
        conn = sqlite3.connect('placement_preparation.db', timeout=20)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        raise

# Home/Login Page
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('base/login.html')  # Serve the login page

    # Handle POST login logic here
    email = request.form.get('email').strip()
    password = request.form.get('password').strip()
    role = request.form.get('role')

    try:
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM users WHERE email = ? AND role = ?", (email, role))
        user = cursor.fetchone()

        cursor.close()
        db.close()

        if not user:
            flash("No user found with that email and role!", "danger")
            return redirect(url_for('home'))

        if check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['role'] = user['role']

            if role == "student":
                return redirect(url_for('student_dashboard'))
            elif role == "company":
                return redirect(url_for('company_dashboard'))
            elif role == "admin":
                return redirect(url_for('admin_dashboard'))
        else:
            flash("Incorrect password!", "danger")
            return redirect(url_for('home'))
    except Exception as err:
        flash(f"Database Error: {err}", "danger")
        return redirect(url_for('home'))

# Register User
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = None
        try:
            # Get form data
            name = request.form['name']
            email = request.form['email']
            password = request.form['password']
            role = request.form['role']
            phone = request.form.get('phone')  # Capture phone number

            # Print form data for debugging
            print("Form data:", request.form)

            db = get_db_connection()
            cursor = db.cursor()

            # First create user with name
            cursor.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (?, ?, ?, ?)
            """, (name, email, generate_password_hash(password), role))
            
            user_id = cursor.lastrowid

            if role == 'student':
                # Include phone and graduation_year in the student insertion
                cursor.execute("""
                    INSERT INTO students (user_id, name, email, phone, department, graduation_year)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    name,
                    email,
                    phone,
                    request.form.get('department'),
                    request.form.get('graduation_year')
                ))
            
            elif role == 'company':
                company_name = request.form.get('company_name')
                cursor.execute("""
                    INSERT INTO companies (user_id, company_name, email, industry)
                    VALUES (?, ?, ?, ?)
                """, (
                    user_id,
                    company_name,
                    email,
                    request.form.get('industry')
                ))

            db.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            if db:
                db.rollback()
            print("Registration error:", str(e))
            flash('Registration failed: ' + str(e), 'error')
            return redirect(url_for('register'))

        finally:
            if db:
                db.close()

    return render_template('base/register.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()  # Remove all session data
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))  # Redirect to homepage after logout

def get_student_progress():
    if 'user_id' not in session:
        return {}

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # Get student ID from session
        cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
        result = cursor.fetchone()
        if not result:
            return {}

        student_id = result[0]

        # Get DSA progress
        cursor.execute("""
            SELECT COUNT(*) as completed
            FROM student_answers sa
            JOIN progress_topics pt ON sa.topic_id = pt.topic_id
            WHERE sa.student_id = ? AND pt.parent_topic = 'DSA'
        """, (student_id,))
        dsa_completed = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT SUM(total_questions) as total
            FROM progress_topics
            WHERE parent_topic = 'DSA'
        """)
        dsa_total = cursor.fetchone()[0] or 0

        # Get Communication progress
        cursor.execute("""
            SELECT COUNT(*) as completed
            FROM student_answers sa
            JOIN progress_topics pt ON sa.topic_id = pt.topic_id
            WHERE sa.student_id = ? AND pt.parent_topic = 'Communication'
        """, (student_id,))
        comm_completed = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT SUM(total_questions) as total
            FROM progress_topics
            WHERE parent_topic = 'Communication'
        """)
        comm_total = cursor.fetchone()[0] or 0

        # Get Aptitude progress
        cursor.execute("""
            SELECT COUNT(*) as completed
            FROM student_answers sa
            JOIN progress_topics pt ON sa.topic_id = pt.topic_id
            WHERE sa.student_id = ? AND pt.parent_topic = 'Aptitude'
        """, (student_id,))
        apti_completed = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT SUM(total_questions) as total
            FROM progress_topics
            WHERE parent_topic = 'Aptitude'
        """)
        apti_total = cursor.fetchone()[0] or 0

        progress_dict = {
            "DSA": (dsa_completed / dsa_total * 100) if dsa_total > 0 else 0,
            "Communication": (comm_completed / comm_total * 100) if comm_total > 0 else 0,
            "Aptitude": (apti_completed / apti_total * 100) if apti_total > 0 else 0
        }

        print("Progress Data:", progress_dict)  # Debug print
        return progress_dict

    except Exception as e:
        print(f"Error in get_student_progress: {e}")
        return {}
    finally:
        if 'db' in locals():
            db.close()

@app.route('/get_progress', methods=['GET'])
def get_progress():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    progress_data = get_student_progress()
    if not progress_data:
        return jsonify({'success': False, 'message': 'No progress found'})

    return jsonify({
        'success': True,
        'DSA': progress_data.get('DSA', 0),
        'Communication': progress_data.get('Communication', 0),
        'Aptitude': progress_data.get('Aptitude', 0)
    })

@app.route('/update_progress', methods=['POST'])
def update_progress():
    print("🔎 Received POST request to /update_progress")

    if 'user_id' not in session:
        print("🚨 User not logged in")
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        print(f"✅ Request Data: {data}")

        if not data:
            print("🚨 Request data is empty")
            return jsonify({'success': False, 'message': 'Invalid request body'}), 400

        question_id = data.get('question_id')
        topic_id = data.get('topic_id')
        print(f"✅ Extracted Data - Question ID: {question_id}, Topic ID: {topic_id}")

        db = get_db_connection()
        cursor = db.cursor()

        # Get student ID from user_id
        cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
        result = cursor.fetchone()
        if not result:
            print("🚨 No student found for user_id")
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        student_id = result[0]
        print(f"✅ Found student ID: {student_id}")

        # Check if this question is already completed
        cursor.execute("""
            SELECT * FROM student_answers 
            WHERE student_id = ? AND question_id = ? AND topic_id = ?
        """, (student_id, question_id, topic_id))
        
        if cursor.fetchone():
            print("🚨 Question already completed!")
            return jsonify({'success': False, 'message': 'Question already completed!'})

        # Mark question as completed
        cursor.execute("""
            INSERT INTO student_answers 
            (student_id, question_id, topic_id, given_answer, is_correct) 
            VALUES (?, ?, ?, '', 1)
        """, (student_id, question_id, topic_id))

        # Get total questions for current topic
        cursor.execute("""
            SELECT total_questions FROM progress_topics 
            WHERE topic_id = ?
        """, (topic_id,))
        topic_total = cursor.fetchone()[0]

        # Get current completed questions count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM student_answers 
            WHERE student_id = ? AND topic_id = ?
        """, (student_id, topic_id))
        completed_questions = cursor.fetchone()[0]

        # Update progress for the specific topic
        cursor.execute("""
            INSERT OR REPLACE INTO student_progress 
            (student_id, topic_id, completed_questions, total_questions, is_completed) 
            VALUES (?, ?, ?, ?, ?)
        """, (
            student_id, 
            topic_id, 
            completed_questions, 
            topic_total, 
            1 if completed_questions >= topic_total else 0
        ))

        # Update overall DSA progress
        cursor.execute("""
            SELECT SUM(total_questions) 
            FROM progress_topics 
            WHERE parent_topic = 'DSA'
        """)
        total_dsa_questions = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) 
            FROM student_answers sa
            JOIN progress_topics pt ON sa.topic_id = pt.topic_id
            WHERE sa.student_id = ? AND pt.parent_topic = 'DSA'
        """, (student_id,))
        completed_dsa_questions = cursor.fetchone()[0]

        # Update or insert overall DSA progress
        cursor.execute("""
            INSERT OR REPLACE INTO dsa_overall_progress 
            (student_id, completed_questions, total_questions, is_completed, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            student_id, 
            completed_dsa_questions, 
            total_dsa_questions,
            1 if completed_dsa_questions >= total_dsa_questions else 0
        ))

        db.commit()
        print("✅ Successfully updated progress!")
        return jsonify({
            'success': True,
            'topic_progress': completed_questions,
            'total_topic_questions': topic_total,
            'dsa_progress': completed_dsa_questions,
            'total_dsa_questions': total_dsa_questions
        })

    except Exception as e:
        print(f"🚨 Error updating progress: {e}")
        if db:
            db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if db:
            db.close()

# Update Student Progress
@app.route('/student_progress', methods=['GET'])
def student_progress():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    try:
        topic_id = request.args.get('topic_id')
        if not topic_id:
            return jsonify({'success': False, 'message': 'Topic ID is required'}), 400

        db = get_db_connection()
        cursor = db.cursor()

        # Get student ID from user_id
        cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': 'Student not found'}), 404

        student_id = result[0]

        # Get topic-specific progress
        cursor.execute("""
            SELECT COUNT(*) as completed_count
            FROM student_answers
            WHERE student_id = ? AND topic_id = ?
        """, (student_id, topic_id))
        topic_result = cursor.fetchone()
        topic_completed = topic_result[0] if topic_result else 0

        # Get overall DSA progress
        cursor.execute("""
            SELECT completed_questions, total_questions
            FROM dsa_overall_progress
            WHERE student_id = ?
        """, (student_id,))
        dsa_progress = cursor.fetchone()

        return jsonify({
            'success': True,
            'completed_questions': topic_completed,
            'dsa_completed': dsa_progress[0] if dsa_progress else 0,
            'dsa_total': dsa_progress[1] if dsa_progress else 0
        })

    except Exception as e:
        print(f"Error fetching progress: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if db:
            db.close()

# Unified Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'role' not in session:
        return redirect(url_for('home'))
    if session['role'] == 'student':
        return redirect(url_for('student_dashboard'))
    elif session['role'] == 'company':
        return redirect(url_for('company_dashboard'))
    elif session['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('home'))

# Student Dashboard with Progress Tracking
@app.route('/student_dashboard')
def student_dashboard():
    if 'role' not in session or session['role'] != 'student':
        print("🚨 User not logged in or incorrect role")
        return redirect(url_for('home'))
    
    db = get_db_connection()
    cursor = db.cursor()
    
    # ✅ Get student_id instead of usn
    cursor.execute("SELECT id FROM students WHERE user_id = ?", (session['user_id'],))
    result = cursor.fetchone()
    if not result:
        print("🚨 Student not found")
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    student_id = result[0]
    print(f"✅ Found student ID: {student_id}")

    # ✅ Replace usn with student_id
    cursor.execute("""
        SELECT topic_id, COUNT(*) as completed 
        FROM student_progress 
        WHERE student_id = ?
        GROUP BY topic_id
    """, (student_id,))
    
    progress_data = cursor.fetchall()
    db.close()

    print(f"✅ Progress Data: {progress_data}")

    progress_summary = {row['topic_id']: row['completed'] for row in progress_data}
    print(f"✅ Progress Summary: {progress_summary}")
    
    # ✅ Return the template directly to debug if it's loading
    return render_template(
        'student/student_dashboard.html',
        username=session.get('email'),
        progress_summary=progress_summary
    )

# Company Dashboard
@app.route('/company_dashboard')
def company_dashboard():
    if 'role' not in session or session['role'] != 'company':
        return redirect(url_for('home'))
    return render_template('company_dashboard.html', username=session.get('email'), progress_summary={})

# Admin Dashboard
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('home'))
    return render_template('admin_dashboard.html', username=session.get('email'), progress_summary={})

# Profile Page
@app.route('/profile')
def profile():
    if 'email' not in session:
        return redirect(url_for('home'))
    return render_template('profile.html', username=session.get('email'))

@app.route('/user_profile')
def user_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    print("User ID from session:", session['user_id'])  # Debugging

    user_id = session['user_id']
    
    conn = sqlite3.connect("placement_preparation.db")
    conn.row_factory = sqlite3.Row  
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM students WHERE user_id = ?", (user_id,))
    student = cursor.fetchone()
    
    conn.close()
    
    if not student:
        return "Student profile not found", 404  

    return render_template('student/user.html', student=student)

def get_topic_id(topic_name):
    topic_map = {
        'basic_programming': 1,
        'dsa': 2,
        'aptitude': 3,
        'communication': 4
    }
    return topic_map.get(topic_name, 1)

@app.route('/debug_db')
def debug_db():
    conn = sqlite3.connect("placement_preparation.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    conn.close()
    
    return {"tables": [table[0] for table in tables]}  # Check if 'students' exists

@app.route('/update_aptitude_progress', methods=['POST'])
def update_aptitude_progress():
    if 'user_id' not in session:
        print("User not logged in")
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    db = None
    try:
        data = request.get_json()
        print("Received data:", data)  # Debug print
        
        problem_id = data.get('problem_id')
        is_completed = data.get('status', True)
        user_id = session['user_id']

        print(f"Processing: user_id={user_id}, problem_id={problem_id}, is_completed={is_completed}")  # Debug print

        db = sqlite3.connect('placement_preparation.db')
        cursor = db.cursor()

        # Simple insert or replace operation
        cursor.execute("""
            INSERT OR REPLACE INTO aptitude_progress 
            (student_id, problem_id, is_completed) 
            VALUES (?, ?, ?)
        """, (user_id, problem_id, is_completed))

        db.commit()
        print("Successfully updated progress")  # Debug print
        return jsonify({'success': True})

    except Exception as e:
        print("Error in update_aptitude_progress:")
        print(traceback.format_exc())  # This will print the full error traceback
        if db:
            db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

    finally:
        if db:
            db.close()

@app.route('/get_aptitude_progress')
def get_aptitude_progress():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT problem_id, is_completed 
            FROM aptitude_progress 
            WHERE student_id = ?
        """, (session['user_id'],))
        
        progress = {row['problem_id']: row['is_completed'] for row in cursor.fetchall()}
        return jsonify({'success': True, 'progress': progress})
        
    except Exception as e:
        print(f"Error fetching progress: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()

@app.route('/user')
def user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # Get all student details including graduation_year
        cursor.execute("""
            SELECT s.*, u.email 
            FROM students s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.user_id = ?
        """, (session['user_id'],))
        
        student = cursor.fetchone()
        if student:
            student_dict = {
                'name': student['name'],
                'email': student['email'],
                'phone': student['phone'],
                'department': student['department'],
                'graduation_year': student['graduation_year']  # Make sure this is included
            }
            return render_template('student/user.html', student=student_dict)
        
        return redirect(url_for('login'))
        
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('login'))
    finally:
        db.close()

@app.route('/aptitude')
def aptitude():
    return render_template('apti/aptitude.html')

@app.route('/communication')
def communication():
    return render_template('communication/communication.html')

@app.route('/dsa')
def dsa():
    return render_template('dsa/dsa.html')

@app.route('/interview')
def interview():
    return render_template('interview/interview.html')

@app.route('/aptitude_quantative')
def aptitude_quantative():
    return render_template('apti/aptitude_quantative.html')

@app.route('/aptitude_numbers')
def aptitude_numbers():
    return render_template('apti/aptitude_numbers.html')

@app.route('/communication_basics')
def communication_basics():
    return render_template('communication/communication_basics.html')

@app.route('/communication_intermediate')
def communication_intermediate():
    return render_template('communication/communication_intermediate.html')

@app.route('/communication_advanced')
def communication_advanced():
    return render_template('communication/communication_advanced.html')

@app.route('/dsa_basic_program')
def dsa_basic_program():
    return render_template('dsa/dsa_basic_program.html')

@app.route('/dsa_arrays_and_strings')
def dsa_arrays_and_strings():
    return render_template('dsa/dsa_arrays_and_strings.html')

@app.route('/dsa/linked-lists')
def dsa_linked_lists():
    return render_template('dsa/dsa_linked_lists.html')

@app.route('/dsa/stacks-and-queues')
def dsa_stacks_and_queues():
    return render_template('dsa/dsa_stacks_and_queues.html')

@app.route('/dsa/trees-and-graphs')
def dsa_trees_and_graphs():
    return render_template('dsa/dsa_trees_and_graphs.html')

@app.route('/dsa/searching-and-sorting')
def dsa_searching_and_sorting():
    return render_template('dsa/dsa_searching_and_sorting.html')

@app.route('/dsa/dp-problems')
def dsa_dp_problems():
    return render_template('dsa/dsa_dp_problems.html')

@app.route('/dsa/recursion-and-backtracking')
def dsa_recursion_and_backtracking():
    return render_template('dsa/dsa_recursion_and_backtracking.html')

@app.route('/dsa/greedy-algorithms')
def dsa_greedy_algorithms():
    return render_template('dsa/dsa_Greedy_Algrothms.html')

@app.route('/dsa/bit-manipulation')
def dsa_bit_manipulation():
    return render_template('dsa/dsa_BitManipulation.html')

@app.route('/notifications')
def notifications():
    return render_template('base/notifications.html')

if __name__ == '__main__':
    app.run(debug=True)
#if this works out i'll ask you to do the same to apti