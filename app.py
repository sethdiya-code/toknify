from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os
import time

app = Flask(__name__)

patients = []
current_token = 0
auto_running=False

TWILIO_NUMBER = "+17625258609"



@app.route('/')
def index():
    return render_template(
        'index.html',
        patients=patients,
        current_token=current_token
    )



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
        'token': len(patients)+1,
        'called':False,
        'retry':0,
        'last_called_time':0
    })

    return redirect('/')



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

        print("CALL SUCCESS:", phone)

    except Exception as e:
        print("CALL ERROR:", str(e))


@app.route('/start_auto')
def start_auto():
    global auto_running
    auto_running=True
    print("AUTO STARTED")
    return "started"
    

@app.route('/stop_auto')
def stop_auto():
    global auto_running
    auto_running=False
    print("AUTO STOPPED")
    return "stopped"


@app.route('/auto_call')
def auto_call():
    global current_token, auto_running

    if not auto_running:
        return "stopped"

    now= time.time()

    for p in patients:

        if p["token"] == current_token + 1 and not p["called"]:
            make_call(p["phone"], p["name"])

            current_token = p["token"]
            p["called"] = True
            p["last_called_time"] = now

            print("FIRST CALL:", p["phone"])
            return "called"

     
        if p["called"] and p["retry"] < 2:
            if now - p["last_called_time"] > 20:  
                make_call(p["phone"], p["name"])

                p["retry"] += 1
                p["last_called_time"] = now

                print("RETRY:", p["phone"])
                return "retry"

    return "done"

   
@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients
    patients = [p for p in patients if p['token'] != token]
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
