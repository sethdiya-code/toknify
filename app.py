from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os

app = Flask(__name__)


patients = []
current_token = 0


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
        "name": name,
        "phone": phone,
        "token": token
    })

    return redirect('/')



@app.route('/call/<int:token>')
def call_patient(token):
    global current_token

    
    current_token = token

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    client = Client(account_sid, auth_token)

    for p in patients:
        if p['token'] == token:
            phone = p['phone']

            print("Calling:", phone)

            call = client.calls.create(
                twiml="<Response><Say>Hello, your token number has come</Say></Response>",
                to=phone,
                from_="+17625258609"
            )

            print("CALL SID:", call.sid)
            break

    return redirect('/')



@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients

    patients = [p for p in patients if p['token'] != token]

    return redirect('/')
    
if __name__ == '__main__':
    app.run(debug=True)
