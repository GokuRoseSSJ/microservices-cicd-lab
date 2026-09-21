from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest
import sqlite3
import time

app = Flask(__name__)

REQUEST_COUNT = Counter(
    'product_service_requests_total',
    'Total requests to Product Service'
)

REQUEST_TIME = Histogram(
    'product_service_request_duration_seconds',
    'Request duration'
)

def get_db():
    conn = sqlite3.connect('/data/products.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL
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
        "service": "Product Service",
        "status": "running"
    })

@app.route('/products', methods=['GET'])
def get_products():
    conn = get_db()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    return jsonify([dict(product) for product in products])

@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db()
    product = conn.execute(
        'SELECT * FROM products WHERE id=?',
        (product_id,)
    ).fetchone()
    conn.close()

    if product is None:
        return jsonify({"error": "Product not found"}), 404

    return jsonify(dict(product))

@app.route('/products', methods=['POST'])
def add_product():
    data = request.get_json()

    if not data or 'id' not in data or 'name' not in data or 'price' not in data:
        return jsonify({"error": "id, name and price required"}), 400

    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO products(id,name,price) VALUES(?,?,?)',
            (data['id'], data['name'], data['price'])
        )
        conn.commit()
        conn.close()

        return jsonify(data), 201

    except sqlite3.IntegrityError:
        return jsonify({"error": "Product already exists"}), 409

@app.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id=?', (product_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Product deleted"})

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {
        'Content-Type': 'text/plain; version=0.0.4'
    }

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5002)
