from flask import Flask, render_template, request, redirect

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
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)