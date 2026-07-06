from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "farmconnect123"
CORS(app)

# ------------------ SQLITE CONNECTION ------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'farmconnect.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- HOME ----------------
from flask import send_from_directory

FRONTEND_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "frontend"
)

# Home page
@app.route("/")
def home():
    return send_from_directory(FRONTEND_FOLDER, "home.html")

# Serve all frontend files automatically
@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_FOLDER, filename)


# ---------------- REGISTER ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    
    db = get_db_connection()
    cursor = db.cursor()

    # Check if email already exists
    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        (data["email"],)
    )
    user = cursor.fetchone()

    if user:
        cursor.close()
        db.close()
        return jsonify({
            "success": False,
            "message": "You are already registered."
        })

    # Register new user
    cursor.execute("""
        INSERT INTO users(name, email, password)
        VALUES(?, ?, ?)
    """, (
        data["name"],
        data["email"],
        data["password"]
    ))

    db.commit()
    cursor.close()
    db.close()

    return jsonify({
        "success": True,
        "message": "Registration Successful"
    })


# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT * FROM users
        WHERE email=? AND password=?
    """, (
        data["email"],
        data["password"]
    ))

    user = cursor.fetchone()
    cursor.close()
    db.close()

    if user:
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]

        return jsonify({
            "success": True,
            "message": "Login Successful",
            "name": user["name"]
        })

    return jsonify({
        "success": False,
        "message": "Invalid Email or Password"
    })


# ---------------- FARMER REGISTER ----------------
@app.route("/farmer-register", methods=["POST"])
def farmer_register():
    data = request.json
    
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM farmers WHERE email=?",
        (data["email"],)
    )
    farmer = cursor.fetchone()

    if farmer:
        cursor.close()
        db.close()
        return jsonify({
            "success": False,
            "message": "Farmer already registered. Please login."
        })

    cursor.execute("""
        INSERT INTO farmers(name, mobile, email, password)
        VALUES(?, ?, ?, ?)
    """, (
        data["name"],
        data["mobile"],
        data["email"],
        data["password"]
    ))

    db.commit()
    cursor.close()
    db.close()

    return jsonify({
        "success": True,
        "message": "Farmer Registration Successful"
    })


# ---------------- FARMER LOGIN ----------------
@app.route("/farmer-login", methods=["POST"])
def farmer_login():
    data = request.json

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT * FROM farmers
        WHERE email=? AND password=?
    """, (
        data["email"],
        data["password"]
    ))

    farmer = cursor.fetchone()
    cursor.close()
    db.close()

    if farmer:
        session["farmer_id"] = farmer["id"]
        session["farmer_name"] = farmer["name"]

        return jsonify({
            "success": True,
            "message": "Farmer Login Successful",
            "name": farmer["name"]
        })

    return jsonify({
        "success": False,
        "message": "Invalid Email or Password"
    })


# ---------------- GET PRODUCTS ----------------
@app.route("/products")
def products():
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT id, product_name AS name, quantity, price, image, description
        FROM products
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    # Convert Row objects to dict elements for jsonify
    data = [dict(row) for row in rows]
    
    cursor.close()
    db.close()

    return jsonify(data)


# ---------------- DELETE PRODUCT ----------------
@app.route("/delete-product/<int:id>", methods=["DELETE"])
def delete_product(id):
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("DELETE FROM products WHERE id=?", (id,))
    db.commit()
    cursor.close()
    db.close()

    return jsonify({"success": True})


# ---------------- PLACE ORDER ----------------
@app.route("/order", methods=["POST"])
def order():
    try:
        data = request.json
        db = get_db_connection()
        cursor = db.cursor()

        total = float(data["price"]) * float(data["quantity"])

        cursor.execute("""
            INSERT INTO orders
            (product_name, customer_name, mobile, address, quantity, total_price, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data["product"],
            data["customer_name"],
            data["mobile"],
            data["address"],
            float(data["quantity"]),
            total,
            "Pending"
        ))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({"success": True, "message": "Order Placed Successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------- GET ALL ORDERS (ADMIN) ----------------
@app.route("/orders")
def get_orders():
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        SELECT * FROM orders
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()
    data = [dict(row) for row in rows]
    
    cursor.close()
    db.close()

    return jsonify(data)


# ---------------- UPDATE ORDER STATUS ----------------
@app.route("/update-order/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    try:
        data = request.json
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET status=?
            WHERE id=?
        """, (data["status"], order_id))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({"success": True, "message": "Status Updated"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------- PAYMENT ----------------
@app.route('/payment', methods=['POST'])
def payment():
    try:
        data = request.get_json(force=True)

        order_id = data.get("order_id")
        method = data.get("method")

        if not order_id or not method:
            return jsonify({"status": "error", "message": "Missing data"})

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET payment_method=?,
                payment_status='Paid'
            WHERE id=?
        """, (method, order_id))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({"status": "success", "message": "Payment successful"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ---------------- DASHBOARD STATS ----------------
@app.route("/dashboard-stats")
def dashboard_stats():
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM products")
    total_products = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM orders")
    total_orders = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM orders WHERE status='Pending'")
    pending_orders = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM orders WHERE status='Delivered'")
    delivered_orders = cursor.fetchone()["total"]

    # Handled standard SQLite alternate syntax for IFNULL
    cursor.execute("""
        SELECT COALESCE(SUM(total_price), 0) AS sales
        FROM orders
        WHERE status='Delivered'
    """)
    total_sales = cursor.fetchone()["sales"]

    cursor.close()
    db.close()

    return jsonify({
        "totalProducts": total_products,
        "totalOrders": total_orders,
        "pendingOrders": pending_orders,
        "deliveredOrders": delivered_orders,
        "totalSales": total_sales
    })


# ---------------- ORDER STATUS ----------------
@app.route('/order-status/<int:order_id>')
def order_status(order_id):
    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("SELECT status FROM orders WHERE id=?", (order_id,))
    result = cursor.fetchone()

    cursor.close()
    db.close()

    if result:
        return jsonify({"status": result["status"]})
    else:
        return jsonify({"status": "Not Found"})


# ---------------- CUSTOMER ORDERS PAGE ----------------
@app.route('/customerOrders')
def customer_orders():
    return send_from_directory(FRONTEND_FOLDER, "customerOrders.html")


@app.route("/farmer-dashboard")
def farmer_dashboard():
    if "farmer_id" not in session:
        return redirect("/farmer-login.html")

    return send_from_directory(FRONTEND_FOLDER, "farmerDashboard.html")


# ---------------- RUN APP ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )