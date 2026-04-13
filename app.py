from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os

app = Flask(__name__)


patients = []
current_token = 0


account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(account_sid, auth_token)

TWILIO_NUMBER = '+17625258609'



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

    token = len(patients) + 1

    patients.append({
        'name': name,
        'phone': phone,
        'token': token
    })

    return redirect('/')



@app.route('/call/<int:token>')
def call_patient(token):
    global current_token

    for p in patients:
        if p['token'] == token:
            phone = p['phone']

            client.calls.create(
                twiml=f'<Response><Say>Hello {p["name"]}, please come, it is your turn</Say></Response>',
                to=phone,
                from_=TWILIO_NUMBER
            )

            current_token = token  

            break

    return redirect('/')



@app.route('/auto_call')
def auto_call():
    global current_token

    if current_token < len(patients):
        current_token += 1

        p = patients[current_token - 1]
        phone = p['phone']

        client.calls.create(
            twiml=f'<Response><Say>Hello {p["name"]}, please come, your turn has arrived</Say></Response>',
            to=phone,
            from_=TWILIO_NUMBER
        )

    return "done"



@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients

    patients = [p for p in patients if p['token'] != token]

    return redirect('/')



if __name__ == '__main__':
    app.run(debug=True)
