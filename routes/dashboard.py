from app import app


@app.route('/dashboard')
def dashboard():
    arr = [1, 2]
    print(arr[2])
    return '<center><h1>dashboard</h1></center>'
