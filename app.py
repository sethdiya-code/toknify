from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os
import time

app = Flask(__name__)

# 🔐 Twilio config (ENV me hona chahiye)
TWILIO_NUMBER = "+17625258609"

patients = []
current_token = 0
auto_running = False
next_token = 1


# 🏠 HOME
@app.route('/')
def index():
    return render_template('index.html', patients=patients, current_token=current_token)


# ➕ ADD PATIENT
@app.route('/add', methods=['POST'])
def add_patient():
    global next_token

    name = request.form.get('name')
    phone = request.form.get('phone')

    if not phone.startswith('+'):
        phone = '+91' + phone

    token = next_token
    next_token += 1

    patients.append({
        'name': name,
        'phone': phone,
        'token': token,
        'called': False,
        'retry': 0,
        'last_called_time': 0
    })

    return redirect('/')


# 📞 CALL FUNCTION (TWILIO + WEBHOOK)
def make_call(phone, name):
    try:
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )

        client.calls.create(
            twiml=f'<Response><Say>Hello {name}, please come</Say></Response>',
            to=phone,
            from_=TWILIO_NUMBER,
            status_callback="https://toknify.in/call_status",  # 👈 CHANGE IF DOMAIN DIFFERENT
            status_callback_event=["completed"]
        )

        print("CALL SENT:", name)

    except Exception as e:
        print("CALL ERROR:", str(e))


# 🚀 START AUTO
@app.route('/start_auto')
def start_auto():
    global auto_running
    auto_running = True
    print("AUTO STARTED")
    return "started"


# ⛔ STOP AUTO
@app.route('/stop_auto')
def stop_auto():
    global auto_running
    auto_running = False
    print("AUTO STOPPED")
    return "stopped"


# 🤖 AUTO CALL SYSTEM
@app.route('/auto_call')
def auto_call():
    global current_token, auto_running

    if not auto_running:
        return "stopped"

    now = time.time()

    # 👉 current patient
    for p in patients:
        if p["token"] == current_token:

            # retry after 50 sec
            if p["retry"] == 1 and now - p["last_called_time"] > 50:
                make_call(p["phone"], p["name"])
                print("RETRY CALL:", p["name"])
                return "retry"

            return "waiting"

    # 👉 next patient first call
    for p in patients:
        if p["token"] == current_token + 1:

            make_call(p["phone"], p["name"])

            current_token = p["token"]
            p["called"] = True
            p["last_called_time"] = now

            print("FIRST CALL:", p["name"])
            return "called"

    return "done"


# 🔥 WEBHOOK (MOST IMPORTANT)
@app.route('/call_status', methods=['POST'])
def call_status():
    global current_token

    status = request.form.get("CallStatus")
    print("CALL STATUS:", status)

    # current patient
    current_patient = None
    for p in patients:
        if p["token"] == current_token:
            current_patient = p
            break

    if not current_patient:
        return "no patient"

    # ✅ answered
    if status == "completed":
        print("ANSWERED:", current_patient["name"])
        current_token += 1
        return "ok"

    # ❌ not answered
    else:
        print("NOT ANSWERED:", current_patient["name"])

        if current_patient["retry"] < 1:
            current_patient["retry"] += 1
            current_patient["last_called_time"] = time.time()
            print("WAITING FOR RETRY")
        else:
            print("SKIP:", current_patient["name"])
            current_token += 1

        return "ok"


# ❌ DELETE
@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients
    patients = [p for p in patients if p["token"] != token]
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
