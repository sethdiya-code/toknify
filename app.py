
from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os
import time

app = Flask(__name__)

patients = []
current_token = 0
auto_running = False
next_token= 1

TWILIO_NUMBER = "+17625258609"


# 🏠 HOME
@app.route('/')
def index():
    return render_template(
        'index.html',
        patients=patients,
        current_token=current_token
    )


# ➕ ADD PATIENT
@app.route('/add', methods=['POST'])
def add_patient():
    global next_token
    
    name = request.form['name']
    phone = request.form['phone']

    if not phone.startswith('+'):
        phone = '+91' + phone

    token= next_token
    next_token+= 1

    patients.append({
        'name': name,
        'phone': phone,
        'token': token,
        'called': False,
        'retry': 0,
        'last_called_time': 0
    })

    print("ADDED:", name, token)

    return redirect('/')


# 📞 CALL FUNCTION (REAL CALL)
def make_call(phone, name):
    try:
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )

        client.calls.create(
            twiml=f'<Response><Say>Hello {name}, please come</Say></Response>',
            to=phone,
            from_=TWILIO_NUMBER
        )

        print("📞 CALL:", phone)

    except Exception as e:
        print("ERROR:", str(e))


# 📞 MANUAL CALL
@app.route('/call/<int:token>')
def call_patient(token):
    global current_token

    for p in patients:
        if p["token"] == token:

            current_token = token

            make_call(p["phone"], p["name"])   # 🔥 FIX

            p["called"] = True
            p["last_called_time"] = time.time()

            return redirect('/')

    return "Patient not found"


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


# 🤖 AUTO + RETRY SYSTEM
@app.route('/auto_call')
def auto_call():
    global current_token, auto_running

    if not auto_running:
        return "stopped"

    now = time.time()

    for p in patients:

        # 🔥 FIRST CALL (next patient)
        if p["token"] == current_token + 1 and not p["called"]:
            make_call(p["phone"], p["name"])

            current_token = p["token"]
            p["called"] = True
            p["last_called_time"] = now

            print("FIRST CALL:", p["name"])
            return "called"

        # 🔁 RETRY (same patient only)
        if p["token"] == current_token:
            if p["retry"] < 2 and (now - p["last_called_time"] > 20):

                make_call(p["phone"], p["name"])

                p["retry"] += 1
                p["last_called_time"] = now

                print("RETRY:", p["name"])
                return "retry"

    return "done"


# ❌ DELETE
@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients
    patients = [p for p in patients if p['token'] != token]
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
