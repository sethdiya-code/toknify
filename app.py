from flask import Flask, render_template, request, redirect
from twilio.rest import client

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
    
    account_sid = "AC4b852228ce7c63a80942080ad72c30a5"
    auth_token = "551694d10b5ff7bbc38336ba3db0554f "
    client = Client(account_sid, auth_token)

    try:
    
        if current_token <= len(patients):
            phone = patients[current_token - 1]['phone']

            call = client.calls.create(
                url="http://demo.twilio.com/docs/voice.xml",
                to=phone,
                from_="+17625258609"
            )

            print("CALL SID:", call.sid)

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
