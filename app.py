from flask import Flask, render_template, request, redirect
from twilio.rest import Client
import os

app = Flask(__name__)

patients = []
current_token = 0

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
        'token': token
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



@app.route('/auto_call')
def auto_call():
    global current_token

    if current_token < len(patients):
        current_token += 1

        p = patients[current_token - 1]

        make_call(p['phone'], p['name'])

    return "done"



@app.route('/call/<int:token>')
def call_patient(token):
    global current_token

    for p in patients:
        if p['token'] == token:
            current_token = token
            make_call(p['phone'], p['name'])
            break

    return redirect('/')



@app.route('/delete/<int:token>')
def delete_patient(token):
    global patients
    patients = [p for p in patients if p['token'] != token]
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
