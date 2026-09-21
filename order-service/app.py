from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest
import sqlite3
import requests
import time

app = Flask(__name__)

REQUEST_COUNT = Counter(
    'order_service_requests_total',
    'Total requests to Order Service'
)

REQUEST_TIME = Histogram(
    'order_service_request_duration_seconds',
    'Request duration'
)

USER_SERVICE = "http://user-service:5001"
PRODUCT_SERVICE = "http://product-service:5002"

def get_db():
    conn = sqlite3.connect('/data/orders.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER
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
        "service": "Order Service",
        "status": "running"
    })

@app.route('/orders', methods=['GET'])
def get_orders():
    conn = get_db()
    orders = conn.execute('SELECT * FROM orders').fetchall()
    conn.close()
    return jsonify([dict(order) for order in orders])

@app.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json()

    required = ['id', 'user_id', 'product_id', 'quantity']

    if not data or not all(key in data for key in required):
        return jsonify({
            "error": "id, user_id, product_id and quantity required"
        }), 400

    try:
        user_response = requests.get(
            f"{USER_SERVICE}/users/{data['user_id']}",
            timeout=5
        )

        if user_response.status_code != 200:
            return jsonify({"error": "User does not exist"}), 400

        product_response = requests.get(
            f"{PRODUCT_SERVICE}/products/{data['product_id']}",
            timeout=5
        )

        if product_response.status_code != 200:
            return jsonify({"error": "Product does not exist"}), 400

        user = user_response.json()
        product = product_response.json()

        conn = get_db()
        conn.execute(
            'INSERT INTO orders(id,user_id,product_id,quantity) VALUES(?,?,?,?)',
            (
                data['id'],
                data['user_id'],
                data['product_id'],
                data['quantity']
            )
        )
        conn.commit()
        conn.close()

        total = product['price'] * data['quantity']

        return jsonify({
            "message": "Order created successfully",
            "order_id": data['id'],
            "user": user,
            "product": product,
            "quantity": data['quantity'],
            "total": total
        }), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "Order already exists"}), 409

    except requests.exceptions.RequestException:
        return jsonify({
            "error": "Unable to communicate with another microservice"
        }), 503

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {
        'Content-Type': 'text/plain; version=0.0.4'
    }

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5003)
