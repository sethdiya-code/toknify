from flask import Flask, render_template, request, redirect, session
from twilio.rest import Client
import os
import time
import sqlite3

call_logs= []

app = Flask(__name__)
app.secret_key= "secret123"

patients = []
current_token = 0
auto_running = False
call_before= 2

TWILIO_NUMBER = "+17625258609"

# 🔥 ADDED DATABASE INIT
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT, password TEXT)")

    conn.commit()
    conn.close()

init_db()


# 🔥 ADDED SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))

        conn.commit()
        conn.close()

        return redirect('/')

    return render_template('signup.html')

# 🔥 ADD THIS LOGIN ROUTE
@app.route('/login')
def login_page():
    return render_template('login.html')

# ================= LOGIN  =================
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()

        conn.close()

        if user:
            session["user_id"] = user[0]   # 🔥 SESSION SET
            return redirect('/')           # dashboard
        else:
            return "Invalid login"

    return render_template("login.html")


# ---------------- HOME ------------

@app.route('/', methods=['GET', 'POST'])  # 🔥 UPDATED
def index():

    if "user_id" not in session:
        return redirect('/login')

    # 🔥 ADDED LOGIN LOGIC
    if request.method == "POST":
        return redirect('/login')
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()

        conn.close()

        if user:
            session["user_id"] = user[0]
            return redirect('/')
        else:
            return "Invalid login"

    # 🔥 ADDED PROTECTION
    if "user_id" not in session:
        return render_template("login.html")

    total= len(patients)
    completed = len([p for p in patients if p.get("completed")])
    calling = len([p for p in patients if p.get("called") and not p.get("completed")])
    waiting = len([p for p in patients if not p.get("called")])
    
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
    

# 🔥 ADDED LOGOUT
@app.route('/logout')
def logout():
    print("LOGOUT HIT")
    session.clear()
    return redirect('/login')
    
    
# ---------------- SET CALL BEFORE ----------------
@app.route('/set_call_before/<int:value>')
def set_call_before(value):
    global call_before

    call_before = value
    print("CALL BEFORE SET:", call_before)

    return "ok"

# ---------------- ADD PATIENT ----------------
@app.route('/add', methods=['POST'])
def add_patient():
    name = request.form['name']
    phone = request.form['phone']

    if not phone.startswith('+'):
        phone = '+91' + phone

    patients.append({
        'name': name,
        'phone': phone,
        'token': len(patients) + 1,
        'called': False,
        'answered': False,
        'retry_done': False,
        'last_called_time': 0,
        'completed': False
    })

    return redirect('/')


# ---------------- MAKE CALL ----------------
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
        status_callback_method= "POST"
    )
    
    call_logs.append({
        "name": name,
        "phone": phone,
        "time": time.strftime("%H:%M:%S"),
        "status": "Calling"
    })
    
    print("📞 CALL:", name)


# ---------------- AUTO CONTROL ----------------
@app.route('/start_auto')
def start_auto():
    global auto_running
    auto_running = True
    print("AUTO STARTED")
    return "started"


@app.route('/stop_auto')
def stop_auto():
    global auto_running
    auto_running = False
    print("AUTO STOPPED")
    return "stopped"


# ---------------- AUTO CALL LOGIC ----------------
@app.route('/auto_call')
def auto_call():
    global current_token

    if not auto_running:
        return "stopped"

    now = time.time()

    # 👉 current patient
    current = None
    for p in patients:
        if p["token"] == current_token:
            current = p
            break

    # ---------------- FIRST CALL ----------------
    if current_token == 0:
        for p in patients:
            if not p["completed"]:
                make_call(p["phone"], p["name"])
                p["called"] = True
                p["last_called_time"] = now
                p["retry_done"]= False
                p["answered"]= False
                current_token = p["token"]
                print("NEXT CALL:", p["name"])
                return "next"

    # ---------------- RETRY ----------------
    if current and not current["retry_done"] and not current["answered"]:
        if now - current["last_called_time"] > 50:
            make_call(current["phone"], current["name"])
            current["retry_done"] = True
            current["last_called_time"] = now
            print("RETRY:", current["name"])
            return "retry"

    # ---------------- NEXT PATIENT ----------------
    if current and current["completed"]:
        for p in patients:
            diff= p["token"]-current_token

            if not p["completed"] and not p["called"] and diff== call_before:
                make_call(p["phone"], p["name"])
                p["called"] = True
                p["last_called_time"] = now
                current_token = p["token"]
                print("NEXT CALL:", p["name"])
                return "next"

    return "waiting"


# ---------------- WEBHOOK ----------------

@app.route('/call_status', methods=['POST'])
def call_status():
    global current_token

    status = request.form.get("CallStatus")
    duration = request.form.get("CallDuration")

    print("STATUS:", status, "DURATION:", duration)

    for p in patients:
        if p["token"] == current_token:

            # ✅ find the latest log for this patient
            for log in reversed(call_logs):
                if log["phone"] == p["phone"]:

                    # =========================
                    # ✅ CALL ANSWERED
                    # =========================
                    if duration and int(duration) > 0:
                        log["status"] = "Answered"

                        p["answered"] = True
                        p["completed"] = True
                        p["called"] = False

                        print("✅ ANSWERED:", p["name"])
                        return "ok"

                    # =========================
                    # ❌ NOT ANSWERED → RETRY
                    # =========================
                    if not p.get("retry_done"):
                        log["status"] = "Retry"

                        p["retry_done"] = True
                        print("🔁 RETRY:", p["name"])

                        make_call(p["phone"], p["name"])
                        return "ok"

                    # =========================
                    # ❌ RETRY FAILED → MISSED
                    # =========================
                    log["status"] = "Missed"

                    p["completed"] = True
                    p["called"] = False

                    print("❌ MISSED:", p["name"])
                    return "ok"

    return "ok"
           

# ---------------- MANUAL CALL ----------------
@app.route('/call_now/<int:token>')
def call_now(token):
    global patients, current_token

    for p in patients:
        if p["token"] == token:

            make_call(p["phone"], p["name"])

            p["called"] = True
            p["retry_done"] = False
            p["answered"] = False
            p["last_called_time"] = time.time()

            current_token = p["token"]

            print("📞 MANUAL CALL:", p["name"])
            return redirect('/')

    return "Patient not found"
    
# ---------------- DELETE ----------------

@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients, current_token

    try:
        new_list = []
        for p in patients:
            if int(p['token']) != int(token):
                new_list.append(p)

        patients = new_list

        if len(patients) == 0:
            current_token = 0

        print("DELETED TOKEN:", token)
        return redirect('/')

    except Exception as e:
        print("DELETE ERROR:", str(e))
        return "Error deleting patient"

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
