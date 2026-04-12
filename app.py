from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os

app = Flask(__name__)

patients = []
current_token = 0

@app.route('/')
def index():
    return render_template('index.html', patients=patients, current_token=current_token)


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


@app.route('/next')
def next_token():
    global current_token

    current_token += 1


    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    print("SID:", account_sid)
    print("TOKEN:", auth_token)

    client = Client(account_sid, auth_token)

    try:
        if current_token <= len(patients):
            phone = patients[current_token - 1]['phone']
            print("Calling:", phone)

            call = client.calls.create(
                twiml='<Response><Say>Hello, your token number has come</Say></Response>',
                to=phone,
                from_='+17625258609'
            )

            print("CALL SID:", call.sid)

        else:
            print("No patient left")

    except Exception as e:
        print("ERROR:", str(e))

    return redirect('/')


@app.route('/delete/<token>')
def delete_patient(token):
    global patients
    patients = [p for p in patients if str(p['token']) != str(token)]
    return redirect('/')


if __name__ == "__main__":
    app.run(debug=True)
