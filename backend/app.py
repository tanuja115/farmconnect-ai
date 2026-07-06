from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from flask_cors import CORS
import os
import mysql.connector

app = Flask(__name__)
app.secret_key = "farmconnect123"
CORS(app)

# ------------------ MYSQL CONNECTION ------------------
def get_db_connection():
    # Looks for production environment parameters on Render; falls back to localhost credentials.
    conn = mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", "your_password"),
        database=os.environ.get("MYSQL_DATABASE", "farmconnect"),
        port=int(os.environ.get("MYSQL_PORT", 3306))
    )
    return conn


# ---------------- FRONTEND STATIC CONFIG ----------------
FRONTEND_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "frontend"
)

# Home page route explicitly set ahead of general static asset catchers
@app.route("/")
def home():
    return send_from_directory(FRONTEND_FOLDER, "home.html")


# ---------------- CUSTOMER AUTHENTICATION ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email = %s", (data["email"],))
    user = cursor.fetchone()

    if user:
        cursor.close()
        db.close()
        return jsonify({
            "success": False,
            "message": "You are already registered."
        })

    cursor.execute("""
        INSERT INTO users (name, email, password)
        VALUES (%s, %s, %s)
    """, (data["name"], data["email"], data["password"]))

    db.commit()
    cursor.close()
    db.close()
    return jsonify({"success": True, "message": "Registration Successful"})


@app.route("/login", methods=["POST"])
def login():
    data = request.json
    role = data.get("role")  # 'customer' or 'farmer'
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    table = "farmers" if role == "farmer" else "users"
    
    cursor.execute(f"SELECT * FROM {table} WHERE email = %s AND password = %s", (data["email"], data["password"]))
    account = cursor.fetchone()

    cursor.close()
    db.close()

    if account:
        return jsonify({
            "success": True, 
            "message": "Login successful", 
            "user": {"name": account["name"], "email": account["email"]}
        })
    else:
        return jsonify({"success": False, "message": "Invalid email or password."})


# ---------------- FARMER AUTHENTICATION ----------------
@app.route("/farmer-register", methods=["POST"])
def farmer_register():
    data = request.json
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM farmers WHERE email = %s", (data["email"],))
    farmer = cursor.fetchone()

    if farmer:
        cursor.close()
        db.close()
        return jsonify({
            "success": False,
            "message": "Farmer already registered. Please login."
        })

    cursor.execute("""
        INSERT INTO farmers (name, mobile, email, password)
        VALUES (%s, %s, %s, %s)
    """, (data["name"], data["mobile"], data["email"], data["password"]))

    db.commit()
    cursor.close()
    db.close()
    return jsonify({"success": True, "message": "Farmer Registration Successful"})


@app.route("/farmer-login", methods=["POST"])
def farmer_login():
    data = request.json
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM farmers WHERE email = %s AND password = %s", (data["email"], data["password"]))
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


# ---------------- PRODUCT ENGINE ----------------
@app.route("/products", methods=["GET"])
def get_products():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT id, product_name, price, quantity, image, description FROM products")
        rows = cursor.fetchall()
        
        products_list = []
        for row in rows:
            products_list.append({
                "id": row["id"],
                "name": row["product_name"],
                "price": row["price"],
                "quantity": row["quantity"],
                "image": row["image"],
                "description": row["description"]
            })
            
        cursor.close()
        db.close()
        return jsonify(products_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/add-product", methods=["POST"])
def add_product():
    try:
        data = request.json
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO products (product_name, price, quantity, image, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data.get("name"),
            float(data.get("price") or 0.0),
            float(data.get("quantity") or 1.0),
            data.get("image"),
            data.get("description")
        ))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": "Product Saved Successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------- TRANSACTIONS & ORDERS ----------------
@app.route("/order", methods=["POST"])
def order():
    try:
        data = request.json
        db = get_db_connection()
        cursor = db.cursor()

        p_name = data.get("product_name") or data.get("product") or "Unknown Produce"
        cust_email = data.get("customer_email") or "guest@farmconnect.com"
        mobile = data.get("mobile") or "N/A"
        address = data.get("address") or "Standard Delivery"
        qty = float(data.get("quantity") or 1.0)
        price = float(data.get("price") or 0.0)
        pay_method = data.get("payment_method") or "COD"
        total = price * qty

        cursor.execute("""
            INSERT INTO orders 
            (product_name, customer_name, mobile, address, quantity, total_price, status, payment_method)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (p_name, cust_email, mobile, address, qty, total, "Pending", pay_method))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": "Order Placed Successfully"})
    except Exception as e:
        print("Order Failure Error Trace:", str(e))
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/orders")
def get_orders():
    email_filter = request.args.get("email")
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if email_filter:
        cursor.execute("""
            SELECT * FROM orders 
            WHERE customer_name = %s OR customer_name LIKE %s
            ORDER BY id DESC
        """, (email_filter, f"%{email_filter}%"))
    else:
        cursor.execute("SELECT * FROM orders ORDER BY id DESC")

    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(rows)


@app.route("/update-order/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    try:
        data = request.json
        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET status = %s
            WHERE id = %s
        """, (data["status"], order_id))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": "Status Updated"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


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
            SET payment_method = %s,
                payment_status = 'Paid'
            WHERE id = %s
        """, (method, order_id))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"status": "success", "message": "Payment successful"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ---------------- BUSINESS METRICS & STATUS ----------------
@app.route("/dashboard-stats")
def dashboard_stats():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM products")
        total_products = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM orders")
        total_orders = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM orders WHERE status='Pending'")
        pending_orders = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM orders WHERE status='Delivered'")
        delivered_orders = cursor.fetchone()["total"]

        cursor.execute("SELECT COALESCE(SUM(total_price), 0) AS sales FROM orders WHERE status='Delivered'")
        total_sales = float(cursor.fetchone()["sales"])

        cursor.close()
        db.close()

        return jsonify({
            "totalProducts": total_products,
            "totalOrders": total_orders,
            "pendingOrders": pending_orders,
            "deliveredOrders": delivered_orders,
            "totalSales": total_sales
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/order-status/<int:order_id>')
def order_status(order_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
    result = cursor.fetchone()

    cursor.close()
    db.close()

    if result:
        return jsonify({"status": result["status"]})
    else:
        return jsonify({"status": "Not Found"})


# ---------------- NAVIGATION REDIRECTS ----------------
@app.route('/customerOrders')
def customer_orders():
    return send_from_directory(FRONTEND_FOLDER, "customerOrders.html")


@app.route("/farmer-dashboard")
def farmer_dashboard():
    if "farmer_id" not in session:
        return redirect("/farmer-login.html")
    return send_from_directory(FRONTEND_FOLDER, "farmerDashboard.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- STATIC ASSET FILE HANDLER (MUST REMAIN AT BOTTOM) ----------------
@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(FRONTEND_FOLDER, filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)