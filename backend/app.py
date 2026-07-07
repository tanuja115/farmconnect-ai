from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory
from flask_cors import CORS
import os
import mysql.connector


app = Flask(__name__)
app.secret_key = "farmconnect"
CORS(app)

# Load the keys from your .env file
# ------------------ MYSQL CONNECTION ------------------
# ------------------ HYBRID DATABASE CONNECTION ------------------
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME"),
            port=int(os.environ.get("DB_PORT", 3306)),
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            use_unicode=True
        )

        print("✅ Connected to MySQL successfully")

        return conn, conn.cursor(dictionary=True, buffered=True)

    except Exception as e:
        print("❌ MySQL Connection Error:", e)
        raise


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
    try:
        data = request.json or {}
        email = data.get("email")
        name = data.get("name")
        password = data.get("password")

        if not email or not name or not password:
            return jsonify({"success": False, "message": "All fields are required."}), 400

        db, cursor = get_db_connection()

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
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
        """, (name, email, password))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": "Registration Successful"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json or {}
        email = data.get("email")
        password = data.get("password")
        role = data.get("role")  # 'customer' or 'farmer'

        if not email or not password:
            return jsonify({"success": False, "message": "Email and password are required."}), 400

        # --- UPDATED CONNECTION LINE ---
        db, cursor = get_db_connection()

        table = "farmers" if role == "farmer" else "users"
        
        # --- COMPATIBILITY CHECK FOR SQLITE vs MYSQL PLACEHOLDERS ---
        # SQLite uses '?', MySQL uses '%s'
        placeholder = "?" if hasattr(db, 'execute') or type(db).__name__ == 'Connection' else "%s"
        
        cursor.execute(f"SELECT * FROM {table} WHERE email = {placeholder} AND password = {placeholder}", (email, password))
        account = cursor.fetchone()

        cursor.close()
        db.close()

        if account:
            # Convert row to a regular dict in case it's an offline SQLite Row object
            account_dict = dict(account) if not isinstance(account, dict) else account
            
            session["loggedin"] = True
            session["id"] = account_dict.get("id")
            session["email"] = account_dict.get("email")
            session["role"] = role

            return jsonify({
                "success": True, 
                "message": f"Welcome back, {account_dict.get('name')}!",
                "user": {"id": account_dict.get("id"), "name": account_dict.get("name"), "email": account_dict.get("email"), "role": role}
            }), 200
        else:
            return jsonify({"success": False, "message": "Incorrect email or password."}), 401

    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


# ---------------- FARMER AUTHENTICATION ----------------
@app.route("/farmer-register", methods=["POST"])
def farmer_register():
    try:
        data = request.json or {}
        name = data.get("name")
        mobile = data.get("mobile")
        email = data.get("email")
        password = data.get("password")

        if not name or not mobile or not email or not password:
            return jsonify({"success": False, "message": "All fields are required."}), 400

        db, cursor = get_db_connection()

        cursor.execute("SELECT * FROM farmers WHERE email = %s", (email,))
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
        """, (name, mobile, email, password))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": "Farmer Registration Successful"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/farmer-login", methods=["POST"])
def farmer_login():
    try:
        data = request.json or {}
        email = data.get("email")
        password = data.get("password")

        db, cursor = get_db_connection()

        cursor.execute("SELECT * FROM farmers WHERE email = %s AND password = %s", (email, password))
        farmer = cursor.fetchone()
        
        if farmer:
            session["farmer_id"] = farmer["id"]
            session["farmer_name"] = farmer["name"]
            cursor.close()
            db.close()
            return jsonify({
                "success": True,
                "message": "Farmer Login Successful",
                "name": farmer["name"]
            })

        cursor.close()
        db.close()
        return jsonify({
            "success": False,
            "message": "Invalid Email or Password"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------- PRODUCT ENGINE ----------------
@app.route("/add-product", methods=["POST"])
def add_product():
    try:
        data = request.get_json(force=True)

        print("===== ADD PRODUCT =====")
        print(data)

        db, cursor = get_db_connection()

        # Remove emojis from description
        description = data.get("description", "")
        description = description.encode("ascii", "ignore").decode()

        query = """
            INSERT INTO products
            (product_name, price, quantity, image, description)
            VALUES (%s, %s, %s, %s, %s)
        """

        values = (
            data.get("name"),
            float(data.get("price") or 0),
            float(data.get("quantity") or 1),
            data.get("image"),
            description
        )

        cursor.execute(query, values)

        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            "success": True,
            "message": "Product Saved Successfully"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ---------------- TRANSACTIONS & ORDERS ----------------
@app.route("/order", methods=["POST"])
def order():
    try:
        data = request.json or {}
        db, cursor = get_db_connection()

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
            (product_name, customer_name, mobile, address, quantity, total_price, status, payment_method, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (p_name, cust_email, mobile, address, qty, total, "Pending", pay_method, "Unpaid"))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": "Order Placed Successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/orders")
def get_orders():
    try:
        email_filter = request.args.get("email")
        db, cursor = get_db_connection()

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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/update-order/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    try:
        data = request.json or {}
        db, cursor = get_db_connection()

        cursor.execute("""
            UPDATE orders
            SET status = %s
            WHERE id = %s
        """, (data.get("status"), order_id))

        db.commit()
        cursor.close()
        db.close()
        return jsonify({"success": True, "message": "Status Updated"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/payment', methods=['POST'])
def payment():
    try:
        data = request.get_json(force=True) or {}
        order_id = data.get("order_id")
        method = data.get("method")

        if not order_id or not method:
            return jsonify({"status": "error", "message": "Missing data"}), 400

        db, cursor = get_db_connection()

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
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------------- BUSINESS METRICS & STATUS ----------------
@app.route("/dashboard-stats")
def dashboard_stats():
    try:
        db, cursor = get_db_connection()

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
    try:
        db, cursor = get_db_connection()

        cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        result = cursor.fetchone()

        cursor.close()
        db.close()

        if result:
            return jsonify({"status": result["status"]})
        else:
            return jsonify({"status": "Not Found"})
    except Exception as e:
        return jsonify({"status": "Error", "message": str(e)}), 500


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