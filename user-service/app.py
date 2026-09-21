from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest
import sqlite3
import time

app = Flask(__name__)

REQUEST_COUNT = Counter(
    'user_service_requests_total',
    'Total requests to User Service'
)

REQUEST_TIME = Histogram(
    'user_service_request_duration_seconds',
    'Request duration'
)

def get_db():
    conn = sqlite3.connect('/data/users.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.before_request
def before():
    request.start_time = time.time()
    REQUEST_COUNT.inc()

@app.after_request
def after(response):
    REQUEST_TIME.observe(time.time() - request.start_time)
    print(f"{request.method} {request.path} -> {response.status_code}", flush=True)
    return response

@app.route('/')
def home():
    return jsonify({
        "service": "User Service",
        "status": "running"
    })

@app.route('/users', methods=['GET'])
def get_users():
    conn = get_db()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return jsonify([dict(user) for user in users])

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE id=?',
        (user_id,)
    ).fetchone()
    conn.close()

    if user is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify(dict(user))

@app.route('/users', methods=['POST'])
def add_user():
    data = request.get_json()

    if not data or 'id' not in data or 'name' not in data:
        return jsonify({"error": "id and name required"}), 400

    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO users(id,name,email) VALUES(?,?,?)',
            (data['id'], data['name'], data.get('email'))
        )
        conn.commit()
        conn.close()

        return jsonify(data), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "User already exists"}), 409

@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "User deleted"})

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {
        'Content-Type': 'text/plain; version=0.0.4'
    }

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001)
