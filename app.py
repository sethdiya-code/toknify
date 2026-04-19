from flask import Flask, render_template, request, redirect, session
from twilio.rest import Client
import os
import time
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

call_logs = []
current_token = 0
auto_running = False
call_before = 2

TWILIO_NUMBER = "+17625258609"


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT,
        admin_name TEXT,
        organization_name TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        token INTEGER,
        user_id INTEGER,
        called INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0,
        answered INTEGER DEFAULT 0,
        retry_done INTEGER DEFAULT 0,
        last_called_time REAL DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


init_db()


def get_db():
    return sqlite3.connect("database.db")


def get_next_token(user_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT MAX(token) FROM patients WHERE user_id = ?", (user_id,))
    last = c.fetchone()[0]

    conn.close()

    if last is None:
        return 1
    return last + 1


def get_patients(user_id):
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT name, phone, token, called, completed, answered, retry_done, last_called_time
    FROM patients
    WHERE user_id = ?
    ORDER BY token ASC
    """, (user_id,))

    rows = c.fetchall()
    conn.close()

    patients = []
    for row in rows:
        patients.append({
            "name": row[0],
            "phone": row[1],
            "token": row[2],
            "called": bool(row[3]),
            "completed": bool(row[4]),
            "answered": bool(row[5]),
            "retry_done": bool(row[6]),
            "last_called_time": row[7] or 0
        })

    return patients


def update_patient(token, user_id, **kwargs):
    if not kwargs:
        return

    conn = get_db()
    c = conn.cursor()

    fields = []
    values = []

    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(value)

    values.extend([token, user_id])

    query = f"UPDATE patients SET {', '.join(fields)} WHERE token = ? AND user_id = ?"
    c.execute(query, tuple(values))

    conn.commit()
    conn.close()


# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        admin_name = request.form['admin_name']
        organization_name = request.form['organization_name']

        conn = get_db()
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (email, password, admin_name, organization_name) VALUES (?, ?, ?, ?)",
            (email, password, admin_name, organization_name)
        )
        conn.commit()
        conn.close()

        return redirect('/login')

    return render_template('signup.html')


# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if "user_id" in session:
        return redirect('/')

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT id, email, admin_name, organization_name FROM users WHERE email = ? AND password = ?",
            (email, password)
        )
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['user_email'] = user[1]
            session['admin_name'] = user[2]
            session['organization_name'] = user[3]
            return redirect('/')

        return "Invalid login"

    return render_template('login.html')


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------------- HOME ----------------
@app.route('/', methods=['GET', 'POST'])
def index():
    global current_token

    if 'user_id' not in session:
        return redirect('/login')

    patients = get_patients(session['user_id'])

    total = len(patients)
    completed = len([p for p in patients if p['completed']])
    calling = len([p for p in patients if p['called'] and not p['completed']])
    waiting = total - completed

    return render_template(
        'index.html',
        patients=patients,
        current_token=current_token,
        call_before=call_before,
        call_logs=call_logs,
        total=total,
        completed=completed,
        calling=calling,
        waiting=waiting
    )


# ---------------- ADD PATIENT ----------------
@app.route('/add', methods=['POST'])
def add_patient():
    if 'user_id' not in session:
        return redirect('/login')

    name = request.form['name']
    phone = request.form['phone']

    if not phone.startswith('+'):
        phone = '+91' + phone

    token = get_next_token(session['user_id'])

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO patients (name, phone, token, user_id) VALUES (?, ?, ?, ?)",
        (name, phone, token, session['user_id'])
    )
    conn.commit()
    conn.close()

    return redirect('/')


# ---------------- DELETE ----------------
@app.route('/delete/<int:token>')
def delete_patient(token):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM patients WHERE token = ? AND user_id = ?", (token, session['user_id']))
    conn.commit()
    conn.close()

    return redirect('/')


# ---------------- TWILIO CALL ----------------
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

    call_logs.append({
        "name": name,
        "phone": phone,
        "time": time.strftime("%H:%M:%S"),
        "status": "Calling"
    })


# ---------------- MANUAL CALL ----------------
@app.route('/call_now/<int:token>')
def call_now(token):
    global current_token

    if 'user_id' not in session:
        return redirect('/login')

    patients = get_patients(session['user_id'])

    for p in patients:
        if p['token'] == token:
            make_call(p['phone'], p['name'])

            update_patient(
                token,
                session['user_id'],
                called=1,
                retry_done=0,
                answered=0,
                last_called_time=time.time()
            )

            current_token = token
            return redirect('/')

    return "Patient not found"


# ---------------- AUTO CONTROL ----------------
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


# ---------------- CALL BEFORE ----------------
@app.route('/set_call_before/<int:value>')
def set_call_before(value):
    global call_before
    call_before = value
    return "ok"


# ---------------- AUTO CALL ----------------
@app.route('/auto_call')
def auto_call():
    global current_token

    if 'user_id' not in session:
        return "login required"

    if not auto_running:
        return "stopped"

    patients = get_patients(session['user_id'])
    now = time.time()

    current = None
    for p in patients:
        if p['token'] == current_token:
            current = p
            break

    # first call
    if current_token == 0:
        for p in patients:
            if not p['completed']:
                make_call(p['phone'], p['name'])
                update_patient(
                    p['token'],
                    session['user_id'],
                    called=1,
                    retry_done=0,
                    answered=0,
                    last_called_time=now
                )
                current_token = p['token']
                return "next"

    # retry after 50 sec
    if current and (not current['retry_done']) and (not current['answered']):
        if now - current['last_called_time'] > 50:
            make_call(current['phone'], current['name'])
            update_patient(
                current['token'],
                session['user_id'],
                retry_done=1,
                last_called_time=now
            )
            return "retry"

    # next patient by token away
    if current and current['completed']:
        for p in patients:
            diff = p['token'] - current_token
            if (not p['completed']) and (not p['called']) and diff == call_before:
                make_call(p['phone'], p['name'])
                update_patient(
                    p['token'],
                    session['user_id'],
                    called=1,
                    last_called_time=now
                )
                current_token = p['token']
                return "next"

    return "waiting"


# ---------------- CALL STATUS ----------------
@app.route('/call_status', methods=['POST'])
def call_status():
    if 'user_id' not in session:
        return "ok"

    duration = request.form.get("CallDuration")
    patients = get_patients(session['user_id'])

    for p in patients:
        if p['token'] == current_token:
            if duration and int(duration) > 0:
                update_patient(
                    p['token'],
                    session['user_id'],
                    answered=1,
                    completed=1,
                    called=0
                )
                return "ok"

            if not p['retry_done']:
                make_call(p['phone'], p['name'])
                update_patient(
                    p['token'],
                    session['user_id'],
                    retry_done=1,
                    last_called_time=time.time()
                )
                return "ok"

            update_patient(
                p['token'],
                session['user_id'],
                completed=1,
                called=0
            )
            return "ok"

    return "ok"


if __name__ == '__main__':
    app.run(debug=True)
