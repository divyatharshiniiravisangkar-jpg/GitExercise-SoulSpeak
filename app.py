from flask import Flask, render_template, request

app = Flask("Soul Speak")

@app.route('/')
def home():
    return render_template('homepage.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        return f"Login received: {username}"

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        return f"Registered: {username}"

    return render_template('register.html')



if __name__ == '__main__':
    app.run(debug=True)