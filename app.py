from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os
import time
from threading import Thread

app = Flask(__name__)

# 📦 DATA
patients = []
current_token = 0

# 📞 TWILIO SETUP
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

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
    name = request.form['name']
    phone = request.form['phone']

    if not phone.startswith('+'):
        phone = '+91' + phone

    token = len(patients) + 1

    patients.append({
        'name': name,
        'phone': phone,
        'token': token
    })

    return redirect('/')


# 📞 MAKE CALL
def make_call(phone, name):
    try:
        client.calls.create(
            twiml=f'<Response><Say>Hello {name}, please come, your turn has arrived</Say></Response>',
            to=phone,
            from_=TWILIO_NUMBER
        )
        print("CALL SUCCESS:", phone)

    except Exception as e:
        print("CALL ERROR:", str(e))


# 🔁 RETRY CALL (background)
def retry_call(phone, name):
    time.sleep(15)  # ⏳ retry after 15 sec
    print("Retrying call:", phone)
    make_call(phone, name)


# 🤖 AUTO CALL SYSTEM
@app.route('/auto_call')
def auto_call():
    global current_token

    if current_token < len(patients):
        current_token += 1

        # 👉 current patient
        p = patients[current_token - 1]
        phone = p['phone']
        name = p['name']

        print("Auto calling:", phone)

        # 🔥 first call
        make_call(phone, name)

        # 🔁 retry in background
        Thread(target=retry_call, args=(phone, name)).start()

    else:
        print("No more patients")

    return "done"


# ❌ DELETE PATIENT
@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients

    patients = [p for p in patients if p['token'] != token]

    return redirect('/')


# 🚀 RUN
if __name__ == '__main__':
    app.run(debug=True)
