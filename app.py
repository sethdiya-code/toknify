from flask import Flask, render_template, request, redirect
from twilio.rest import Client

app = Flask(__name__)

patients = []
current_token = 0


@app.route('/')
def index():
    return render_template('index.html', patients=patients, current_token=current_token)


@app.route('/add', methods=['POST'])
def add_patient():
    global current_token

    current_token=0
    
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


    account_sid = "AC4b852228ce7c63a80942080ad72c30a5 "
    auth_token = "daba2ec69e4ca4828c8bce847f67718c"

    client = Client(account_sid, auth_token)

    print("FUNCTION RUN HUA")

    try:
        if current_token <= len(patients):
            phone = patients[current_token]['phone']
            print("Calling:", phone)

            call = client.calls.create(
                twiml='<Response><Say>Hello, your token number has come</Say></Response>',
                to=phone,
                from_="+17625258609"
            )

            print("CALL SID:", call.sid)

            current_token+=1

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


if __name__ == '__main__':
    app.run(debug=True)
