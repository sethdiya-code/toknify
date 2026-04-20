from flask import Flask, render_template, request, redirect, session
from twilio.rest import Client
import sqlite3
import os
import time

app = Flask(__name__)
app.secret_key = "secret123"

TWILIO_NUMBER = "+17625258609"

auto_running = False
current_token = 0


# ================= DATABASE =================
def get_db():
    return sqlite3.connect("database.db")


def init_db():
    conn = get_db()
    c = conn.cursor()

    # USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        admin_name TEXT,
        organization_name TEXT
    )
    """)

    # PATIENTS
    c.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        phone TEXT,
        visit_purpose TEXT,
        token INTEGER,
        called INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        answered INTEGER DEFAULT 0,
        retry_done INTEGER DEFAULT 0,
        last_called_time REAL DEFAULT 0
    )
    """)

    # CALL HISTORY
    c.execute("""
    CREATE TABLE IF NOT EXISTS call_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        patient_name TEXT,
        phone TEXT,
        token INTEGER,
        call_type TEXT,
        call_status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # NOTIFICATIONS
    c.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # SUPPORT
    c.execute("""
    CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # TOKEN SETTINGS
    c.execute("""
    CREATE TABLE IF NOT EXISTS token_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        call_before INTEGER DEFAULT 2,
        auto_call_enabled INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


init_db()


# ================= HELPERS =================
def get_call_before(user_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT call_before FROM token_settings WHERE user_id=?", (user_id,))
    row = c.fetchone()

    conn.close()

    if row:
        return row[0]
    return 2


def get_next_token(user_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT MAX(token) FROM patients WHERE user_id=?", (user_id,))
    row = c.fetchone()[0]

    conn.close()

    if row is None:
        return 1
    return row + 1


def save_notification(user_id, message):
    conn = get_db()
    c = conn.cursor()

    c.execute(
        "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
        (user_id, message)
    )

    conn.commit()
    conn.close()


def save_call_log(user_id, name, phone, token, call_type, status):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    INSERT INTO call_logs
    (user_id, patient_name, phone, token, call_type, call_status)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, name, phone, token, call_type, status))

    conn.commit()
    conn.close()


# ================= AUTH =================

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            email = request.form['email']
            password = request.form['password']
            admin_name = request.form['admin_name']
            organization_name = request.form['organization_name']

            conn = get_db()
            c = conn.cursor()

            c.execute("""
                INSERT INTO users
                (email, password, admin_name, organization_name)
                VALUES (?, ?, ?, ?)
            """, (email, password, admin_name, organization_name))

            conn.commit()
            conn.close()

            return redirect('/login')

        except Exception as e:
            return f"Signup Error: {str(e)}"

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT id, admin_name, organization_name FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['email'] = email
            session['admin_name'] = user[1]
            session['organization_name'] = user[2]
            return redirect('/')

        return "Invalid login"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    conn = get_db()
    c = conn.cursor()

    # current logged in user
    email = session['email']

    if request.method == 'POST':
        organization_name = request.form['organization_name']
        admin_name = request.form['admin_name']
        new_email = request.form['email']
        password = request.form['password']

        c.execute("""
            UPDATE users
            SET organization_name = ?, admin_name = ?, email = ?, password = ?
            WHERE email = ?
        """, (organization_name, admin_name, new_email, password, email))

        conn.commit()

        # session bhi update hoga
        session['organization_name'] = organization_name
        session['admin_name'] = admin_name
        session['email'] = new_email

        conn.close()
        return redirect('/')

    # GET request → old data show karega
    c.execute("SELECT organization_name, admin_name, email, password FROM users WHERE email = ?", (email,))
    user = c.fetchone()

    conn.close()

    return render_template(
        'signup.html',
        edit_mode=True,
        organization_name=user[0],
        admin_name=user[1],
        email=user[2],
        password=user[3]
    )


# ================= DASHBOARD =================
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    call_before = get_call_before(user_id)

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT name, phone, visit_purpose, token, called, completed FROM patients WHERE user_id=? ORDER BY token ASC", (user_id,))
    rows = c.fetchall()

    patients = []
    for row in rows:
        patients.append({
            'name': row[0],
            'phone': row[1],
            'visit_purpose': row[2],
            'token': row[3],
            'called': row[4],
            'completed': row[5]
        })

    total = len(patients)
    completed = len([p for p in patients if p['completed']])
    calling = len([p for p in patients if p['called'] and not p['completed']])
    waiting = total - completed

    conn.close()

    return render_template(
        'index.html',
        patients=patients,
        total=total,
        completed=completed,
        calling=calling,
        waiting=waiting,
        current_token=current_token,
        call_before=call_before,
        admin_name=session.get('admin_name'),
        organization=session.get('organization_name'),
        email=session.get('email')
    )


# ================= ADD PATIENT =================
@app.route('/add', methods=['POST'])
def add_patient():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    name = request.form['name']
    phone = request.form['phone']
    visit_purpose= request.form['visit_purpose']

    if not phone.startswith('+'):
        phone = '+91' + phone

    token = get_next_token(user_id)

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO patients (user_id, name, phone, visit_purpose, token) VALUES (?, ?, ?, ?, ? )",
        (user_id, name, phone, visit_purpose, token)
    )
    conn.commit()
    conn.close()

    save_notification(user_id, f"Patient {name} added")

    return redirect('/')


# ================= DELETE =================
@app.route('/delete/<int:token>')
def delete_patient(token):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM patients WHERE token=? AND user_id=?", (token, session['user_id']))
    conn.commit()
    conn.close()

    return redirect('/')


# ================= TWILIO =================
def make_call(phone, name):
    client = Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )

    client.calls.create(
        twiml=f'<Response><Say>Hello {name}, please come</Say></Response>',
        to=phone,
        from_=TWILIO_NUMBER,
        status_callback="https://toknify.in/call_status",
        status_callback_event=["completed"],
        status_callback_method="POST"
    )


# ================= MANUAL CALL =================
@app.route('/call_now/<int:token>')
def call_now(token):
    global current_token

    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, phone FROM patients WHERE token=? AND user_id=?", (token, user_id))
    row = c.fetchone()

    if row:
        name, phone = row
        make_call(phone, name)

        c.execute("""
        UPDATE patients
        SET called=1, retry_done=0, answered=0, last_called_time=?
        WHERE token=? AND user_id=?
        """, (time.time(), token, user_id))

        conn.commit()
        conn.close()

        current_token = token
        save_call_log(user_id, name, phone, token, "manual", "Calling")
        return redirect('/')

    conn.close()
    return "Patient not found"


# ================= AUTO START/STOP =================
@app.route('/start_auto')
def start_auto():
    global auto_running
    auto_running = True
    return "started"


@app.route('/stop_auto')
def stop_auto():
    global auto_running
    auto_running = False
    return "stopped"





# ================= TOKEN SETTING =================
@app.route('/set_call_before/<int:value>')
def set_call_before(value):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM token_settings WHERE user_id=?", (user_id,))
    c.execute(
        "INSERT INTO token_settings (user_id, call_before) VALUES (?, ?)",
        (user_id, value)
    )
    conn.commit()
    conn.close()

    return redirect('/')

# ================= TODAY REPORT =================
@app.route('/today_report')
def today_report():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM patients WHERE user_id=?", (user_id,))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM patients WHERE user_id=? AND completed=1", (user_id,))
    completed = c.fetchone()[0]

    waiting = total - completed

    conn.close()

    return render_template(
        "today_report.html",
        total=total,
        completed=completed,
        waiting=waiting
    )


# ================= CALL HISTORY =================
@app.route('/call_history')
def call_history():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT patient_name, phone, token, call_type, call_status, created_at
        FROM call_logs
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,))

    history = c.fetchall()
    conn.close()

    return render_template("call_history.html", history=history)


# ================= PATIENT RECORDS =================
@app.route('/patient_records')
def patient_records():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT name, phone, token, called, completed
        FROM patients
        WHERE user_id=?
        ORDER BY token ASC
    """, (user_id,))

    patients = c.fetchall()
    conn.close()

    return render_template("patient_records.html", patients=patients)


# ================= NOTIFICATIONS =================
@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,))

    notifications = c.fetchall()
    conn.close()

    return render_template("notifications.html", notifications=notifications)


# ================= SUPPORT =================
@app.route('/support', methods=['GET', 'POST'])
def support():
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']

    if request.method == 'POST':
        subject = request.form['subject']
        message = request.form['message']

        conn = get_db()
        c = conn.cursor()

        c.execute("""
            INSERT INTO support_tickets (user_id, subject, message)
            VALUES (?, ?, ?)
        """, (user_id, subject, message))

        conn.commit()
        conn.close()

        return redirect('/support')

    conn = get_db()
    c = conn.cursor()

    c.execute("""
        SELECT subject, message, status, created_at
        FROM support_tickets
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,))

    tickets = c.fetchall()
    conn.close()

    return render_template("support.html", tickets=tickets)


if __name__ == '__main__':
    app.run(debug=True)
