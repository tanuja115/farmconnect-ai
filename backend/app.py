from flask import Flask, request, jsonify, redirect, session, send_from_directory
from flask_cors import CORS
import mysql.connector
import os
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import razorpay
from dotenv import load_dotenv

load_dotenv()


# =========================================================
# FLASK CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "farmconnect123"
)

CORS(app)


# =========================================================
# DATABASE CONNECTION
# =========================================================

db = mysql.connector.connect(
    host=os.environ["DB_HOST"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ["DB_NAME"],
    port=int(os.environ.get("DB_PORT", 3306))
)


# =========================================================
# RAZORPAY CONFIGURATION
# =========================================================

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    print("WARNING: Razorpay API keys are not configured.")

razorpay_client = None

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(
        auth=(
            RAZORPAY_KEY_ID,
            RAZORPAY_KEY_SECRET
        )
    )


# =========================================================
# FRONTEND FOLDER
# =========================================================

FRONTEND_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "frontend"
)


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        FRONTEND_FOLDER,
        "home.html"
    )


# =========================================================
# CUSTOMER REGISTRATION
# =========================================================

@app.route("/register", methods=["POST"])
def register():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        name = data.get("name")
        email = data.get("email", "").strip().lower()
        password = data.get("password")

        if not name or not email or not password:
            return jsonify({
                "success": False,
                "message": "All fields are required"
            }), 400

        if len(password) < 6:
            return jsonify({
                "success": False,
                "message": "Password must contain at least 6 characters"
            }), 400

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()
        cursor.close()

        if user:
            return jsonify({
                "success": False,
                "message": "You are already registered. Please login."
            })

        # New customer passwords are stored securely.
        password_hash = generate_password_hash(password)

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO users
            (name, email, password)
            VALUES
            (%s, %s, %s)
        """, (
            name,
            email,
            password_hash
        ))

        db.commit()
        cursor.close()

        return jsonify({
            "success": True,
            "message": "Registration Successful"
        })

    except Exception as e:

        print("Customer registration error:", e)

        return jsonify({
            "success": False,
            "message": "Registration failed."
        }), 500


# =========================================================
# CUSTOMER LOGIN
# Supports:
# 1. Old plain-text passwords
# 2. New hashed passwords
# =========================================================

@app.route("/login", methods=["POST"])
def login():

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Email and password are required"
            }), 400

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM users
            WHERE email=%s
        """, (
            email,
        ))

        user = cursor.fetchone()
        cursor.close()

        if not user:
            return jsonify({
                "success": False,
                "message": "Invalid Email or Password"
            })

        stored_password = user["password"]

        password_valid = False

        # Newly registered/reset passwords
        if stored_password.startswith(("pbkdf2:", "scrypt:")):

            try:
                password_valid = check_password_hash(
                    stored_password,
                    password
                )
            except Exception:
                password_valid = False

        # Existing old passwords
        else:

            password_valid = (
                stored_password == password
            )

        if password_valid:

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

    except Exception as e:

        print("Customer login error:", e)

        return jsonify({
            "success": False,
            "message": "Login failed."
        }), 500


# =========================================================
# CUSTOMER FORGOT PASSWORD
# =========================================================

@app.route("/forgot-password", methods=["POST"])
def forgot_password():

    data = request.get_json() or {}

    email = data.get(
        "email",
        ""
    ).strip().lower()

    if not email:

        return jsonify({
            "success": False,
            "message": "Email is required."
        }), 400

    try:

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        # Don't reveal whether the email exists.
        if not user:

            cursor.close()

            return jsonify({
                "success": True,
                "message": "If this email is registered, a password reset request has been created."
            })

        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Token valid for 30 minutes
        expiry = datetime.now() + timedelta(
            minutes=30
        )

        cursor.execute("""
            UPDATE users
            SET
                reset_token=%s,
                reset_token_expiry=%s
            WHERE id=%s
        """, (
            token,
            expiry,
            user["id"]
        ))

        db.commit()
        cursor.close()

        # TEMPORARY DEVELOPMENT RESPONSE
        # Later this token should be sent through email.
        return jsonify({
            "success": True,
            "message": "Password reset request created.",
            "reset_token": token
        })

    except Exception as e:

        print(
            "Customer forgot password error:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Unable to process password reset."
        }), 500


# =========================================================
# CUSTOMER RESET PASSWORD
# =========================================================

@app.route("/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json() or {}

    token = data.get(
        "token",
        ""
    ).strip()

    new_password = data.get(
        "password",
        ""
    )

    if not token or not new_password:

        return jsonify({
            "success": False,
            "message": "Reset token and new password are required."
        }), 400

    if len(new_password) < 6:

        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters."
        }), 400

    try:

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id
            FROM users
            WHERE reset_token=%s
            AND reset_token_expiry > NOW()
        """, (
            token,
        ))

        user = cursor.fetchone()

        if not user:

            cursor.close()

            return jsonify({
                "success": False,
                "message": "Invalid or expired reset link."
            }), 400

        password_hash = generate_password_hash(
            new_password
        )

        cursor.execute("""
            UPDATE users
            SET
                password=%s,
                reset_token=NULL,
                reset_token_expiry=NULL
            WHERE id=%s
        """, (
            password_hash,
            user["id"]
        ))

        db.commit()
        cursor.close()

        return jsonify({
            "success": True,
            "message": "Password reset successfully."
        })

    except Exception as e:

        print(
            "Customer reset password error:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Unable to reset password."
        }), 500


# =========================================================
# FARMER REGISTRATION
# =========================================================

@app.route("/farmer-register", methods=["POST"])
def farmer_register():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        name = data.get("name")
        mobile = data.get("mobile")
        email = data.get(
            "email",
            ""
        ).strip().lower()
        password = data.get("password")

        if not name or not mobile or not email or not password:

            return jsonify({
                "success": False,
                "message": "All fields are required"
            }), 400

        if len(password) < 6:

            return jsonify({
                "success": False,
                "message": "Password must contain at least 6 characters"
            }), 400

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM farmers WHERE email=%s",
            (email,)
        )

        farmer = cursor.fetchone()
        cursor.close()

        if farmer:

            return jsonify({
                "success": False,
                "message": "Farmer already registered. Please login."
            })

        # New farmer passwords are stored securely.
        password_hash = generate_password_hash(
            password
        )

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO farmers
            (name, mobile, email, password)
            VALUES
            (%s, %s, %s, %s)
        """, (
            name,
            mobile,
            email,
            password_hash
        ))

        db.commit()
        cursor.close()

        return jsonify({
            "success": True,
            "message": "Farmer Registration Successful"
        })

    except Exception as e:

        print("Farmer registration error:", e)

        return jsonify({
            "success": False,
            "message": "Registration failed."
        }), 500


# =========================================================
# FARMER LOGIN
# Supports:
# 1. Old plain-text passwords
# 2. New hashed passwords
# =========================================================

@app.route("/farmer-login", methods=["POST"])
def farmer_login():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        email = data.get(
            "email",
            ""
        ).strip().lower()

        password = data.get(
            "password",
            ""
        )

        if not email or not password:

            return jsonify({
                "success": False,
                "message": "Email and password are required"
            }), 400

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM farmers
            WHERE email=%s
        """, (
            email,
        ))

        farmer = cursor.fetchone()
        cursor.close()

        if not farmer:

            return jsonify({
                "success": False,
                "message": "Invalid Email or Password"
            })

        stored_password = farmer["password"]

        password_valid = False

        # New hashed password
        if stored_password.startswith(("pbkdf2:", "scrypt:")):

            try:

                password_valid = check_password_hash(
                    stored_password,
                    password
                )

            except Exception:

                password_valid = False

        # Old plain-text password
        else:

            password_valid = (
                stored_password == password
            )

        if password_valid:

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

    except Exception as e:

        print("Farmer login error:", e)

        return jsonify({
            "success": False,
            "message": "Login failed."
        }), 500


# =========================================================
# FARMER FORGOT PASSWORD
# =========================================================

@app.route("/farmer-forgot-password", methods=["POST"])
def farmer_forgot_password():

    data = request.get_json() or {}

    email = data.get(
        "email",
        ""
    ).strip().lower()

    if not email:

        return jsonify({
            "success": False,
            "message": "Email is required."
        }), 400

    try:

        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM farmers WHERE email=%s",
            (email,)
        )

        farmer = cursor.fetchone()

        # Don't reveal whether the email exists.
        if not farmer:

            cursor.close()

            return jsonify({
                "success": True,
                "message": "If this email is registered, a password reset request has been created."
            })

        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Token valid for 30 minutes
        expiry = datetime.now() + timedelta(
            minutes=30
        )

        cursor.execute("""
            UPDATE farmers
            SET
                reset_token=%s,
                reset_token_expiry=%s
            WHERE id=%s
        """, (
            token,
            expiry,
            farmer["id"]
        ))

        db.commit()
        cursor.close()

        # TEMPORARY DEVELOPMENT RESPONSE
        # Later this token should be sent through email.
        return jsonify({
            "success": True,
            "message": "Password reset request created.",
            "reset_token": token
        })

    except Exception as e:

        print(
            "Farmer forgot password error:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Unable to process password reset."
        }), 500


# =========================================================
# FARMER RESET PASSWORD
# =========================================================

@app.route("/farmer-reset-password", methods=["POST"])
def farmer_reset_password():

    data = request.get_json() or {}

    token = data.get(
        "token",
        ""
    ).strip()

    new_password = data.get(
        "password",
        ""
    )

    if not token or not new_password:

        return jsonify({
            "success": False,
            "message": "Reset token and new password are required."
        }), 400

    if len(new_password) < 6:

        return jsonify({
            "success": False,
            "message": "Password must contain at least 6 characters."
        }), 400

    try:

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id
            FROM farmers
            WHERE reset_token=%s
            AND reset_token_expiry > NOW()
        """, (
            token,
        ))

        farmer = cursor.fetchone()

        if not farmer:

            cursor.close()

            return jsonify({
                "success": False,
                "message": "Invalid or expired reset link."
            }), 400

        password_hash = generate_password_hash(
            new_password
        )

        cursor.execute("""
            UPDATE farmers
            SET
                password=%s,
                reset_token=NULL,
                reset_token_expiry=NULL
            WHERE id=%s
        """, (
            password_hash,
            farmer["id"]
        ))

        db.commit()
        cursor.close()

        return jsonify({
            "success": True,
            "message": "Password reset successfully."
        })

    except Exception as e:

        print(
            "Farmer reset password error:",
            e
        )

        return jsonify({
            "success": False,
            "message": "Unable to reset password."
        }), 500


# =========================================================
# PRODUCTS API
# =========================================================

@app.route("/add-product", methods=["POST"])
def add_product():

    if "farmer_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login as farmer"
        }), 401

    try:

        data = request.get_json() or {}

        product_name = (
            data.get("product_name")
            or data.get("name")
            or ""
        ).strip()

        quantity = data.get("quantity", 0)
        price = data.get("price")
        image = data.get("image", "")
        description = data.get("description", "")

        if not product_name:
            return jsonify({
                "success": False,
                "message": "Product name is required"
            }), 400

        if price is None:
            return jsonify({
                "success": False,
                "message": "Price is required"
            }), 400

        try:
            quantity = float(quantity)
            price = float(price)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Quantity and price must be valid numbers"
            }), 400

        if quantity < 0 or price < 0:
            return jsonify({
                "success": False,
                "message": "Quantity and price cannot be negative"
            }), 400

        farmer_id = session["farmer_id"]

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO products
            (
                product_name,
                quantity,
                price,
                image,
                description,
                farmer_id
            )
            VALUES
            (%s, %s, %s, %s, %s, %s)
        """, (
            product_name,
            quantity,
            price,
            image,
            description,
            farmer_id
        ))

        db.commit()

        product_id = cursor.lastrowid

        cursor.close()

        return jsonify({
            "success": True,
            "message": "Product added successfully",
            "product_id": product_id
        })

    except Exception as e:

        print("Add product error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.route("/products", methods=["GET"])
def products():

    try:

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                product_name AS name,
                quantity,
                price,
                image,
                description,
                farmer_id
            FROM products
            ORDER BY id DESC
        """)

        data = cursor.fetchall()

        cursor.close()

        return jsonify(data)

    except Exception as e:

        print("Products error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.route("/farmer-products", methods=["GET"])
def farmer_products():

    if "farmer_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login as farmer"
        }), 401

    try:

        farmer_id = session["farmer_id"]

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                product_name AS name,
                quantity,
                price,
                image,
                description
            FROM products
            WHERE farmer_id=%s
            ORDER BY id DESC
        """, (
            farmer_id,
        ))

        data = cursor.fetchall()

        cursor.close()

        return jsonify({
            "success": True,
            "products": data
        })

    except Exception as e:

        print("Farmer products error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# PRODUCTS PAGE
# =========================================================

@app.route("/products-page")
def products_page():

    return send_from_directory(
        FRONTEND_FOLDER,
        "products.html"
    )


# =========================================================
# DELETE PRODUCT
# =========================================================

@app.route("/delete-product/<int:id>", methods=["DELETE"])
def delete_product(id):

    if "farmer_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login as farmer"
        }), 401

    try:

        farmer_id = session["farmer_id"]

        cursor = db.cursor()

        cursor.execute("""
            DELETE FROM products
            WHERE id=%s
            AND farmer_id=%s
        """, (
            id,
            farmer_id
        ))

        db.commit()

        deleted = cursor.rowcount

        cursor.close()

        if deleted == 0:

            return jsonify({
                "success": False,
                "message": "Product not found or you do not own this product"
            }), 404

        return jsonify({
            "success": True,
            "message": "Product deleted successfully"
        })

    except Exception as e:

        print("Delete product error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# CREATE ORDER
# =========================================================

@app.route("/order", methods=["POST"])
def order():

    try:

        data = request.get_json() or {}

        product_id = data.get("product_id")
        product_name_from_request = data.get("product")

        customer_name = data.get("customer_name")
        mobile = data.get("mobile")
        address = data.get("address")
        quantity = data.get("quantity")

        if (
            not customer_name
            or not mobile
            or not address
        ):

            return jsonify({
                "success": False,
                "message": "Please fill all customer details"
            }), 400

        if quantity is None:

            return jsonify({
                "success": False,
                "message": "Quantity is required"
            }), 400

        try:
            quantity = float(quantity)
        except (TypeError, ValueError):

            return jsonify({
                "success": False,
                "message": "Invalid quantity"
            }), 400

        if quantity <= 0:

            return jsonify({
                "success": False,
                "message": "Quantity must be greater than zero"
            }), 400

        cursor = db.cursor(dictionary=True)

        # Preferred method:
        # frontend sends product_id.
        if product_id is not None:

            try:
                product_id = int(product_id)
            except (TypeError, ValueError):

                cursor.close()

                return jsonify({
                    "success": False,
                    "message": "Invalid product ID"
                }), 400

            cursor.execute("""
                SELECT
                    id,
                    product_name,
                    price,
                    farmer_id
                FROM products
                WHERE id=%s
            """, (
                product_id,
            ))

        # Backward compatibility:
        # old frontend may only send product name.
        else:

            if not product_name_from_request:

                cursor.close()

                return jsonify({
                    "success": False,
                    "message": "Product ID is required"
                }), 400

            cursor.execute("""
                SELECT
                    id,
                    product_name,
                    price,
                    farmer_id
                FROM products
                WHERE product_name=%s
                ORDER BY id DESC
                LIMIT 1
            """, (
                product_name_from_request,
            ))

        product_data = cursor.fetchone()

        if not product_data:

            cursor.close()

            return jsonify({
                "success": False,
                "message": "Product not found"
            }), 404

        product_id = product_data["id"]
        product_name = product_data["product_name"]
        price = float(product_data["price"])
        farmer_id = product_data["farmer_id"]

        # IMPORTANT:
        # Price is taken from the database instead of trusting
        # the price sent by the browser.
        total = price * quantity

        cursor.close()

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO orders
            (
                product_name,
                customer_name,
                mobile,
                address,
                quantity,
                total_price,
                status,
                payment_method,
                payment_status,
                farmer_id,
                product_id
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
        """, (
            product_name,
            customer_name,
            mobile,
            address,
            quantity,
            total,
            "Pending",
            None,
            "Pending",
            farmer_id,
            product_id
        ))

        db.commit()

        order_id = cursor.lastrowid

        cursor.close()

        return jsonify({
            "success": True,
            "message": "Order Placed Successfully",
            "order_id": order_id,
            "product_id": product_id,
            "total": total
        })

    except Exception as e:

        print("Order error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET SINGLE ORDER DETAILS
# =========================================================

@app.route("/order-details/<int:order_id>")
def order_details(order_id):

    try:

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                product_id,
                farmer_id,
                product_name,
                customer_name,
                mobile,
                address,
                quantity,
                total_price,
                status,
                payment_method,
                payment_status
            FROM orders
            WHERE id=%s
        """, (
            order_id,
        ))

        order_data = cursor.fetchone()

        cursor.close()

        if not order_data:

            return jsonify({
                "success": False,
                "message": "Order not found"
            }), 404

        order_data["total_price"] = float(
            order_data["total_price"]
        )

        return jsonify({
            "success": True,
            "order": order_data,
            "total_price": order_data["total_price"]
        })

    except Exception as e:

        print("Order details error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET FARMER ORDERS
# =========================================================

@app.route("/orders", methods=["GET"])
def get_orders():

    if "farmer_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login as farmer"
        }), 401

    try:

        farmer_id = session["farmer_id"]

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                product_id,
                farmer_id,
                product_name,
                customer_name,
                mobile,
                address,
                quantity,
                total_price,
                status,
                payment_method,
                payment_status
            FROM orders
            WHERE farmer_id=%s
            ORDER BY id DESC
        """, (
            farmer_id,
        ))

        data = cursor.fetchall()

        cursor.close()

        for item in data:
            item["total_price"] = float(
                item["total_price"]
            )

        return jsonify(data)

    except Exception as e:

        print("Farmer orders error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# UPDATE FARMER ORDER STATUS
# =========================================================

@app.route("/update-order/<int:order_id>", methods=["PUT"])
def update_order(order_id):

    if "farmer_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login as farmer"
        }), 401

    try:

        data = request.get_json() or {}

        status = data.get("status")

        if not status:

            return jsonify({
                "success": False,
                "message": "Status is required"
            }), 400

        allowed_statuses = {
            "Pending",
            "Confirmed",
            "Processing",
            "Shipped",
            "Delivered",
            "Cancelled"
        }

        if status not in allowed_statuses:

            return jsonify({
                "success": False,
                "message": "Invalid order status"
            }), 400

        farmer_id = session["farmer_id"]

        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET status=%s
            WHERE id=%s
            AND farmer_id=%s
        """, (
            status,
            order_id,
            farmer_id
        ))

        db.commit()

        updated = cursor.rowcount

        cursor.close()

        if updated == 0:

            return jsonify({
                "success": False,
                "message": "Order not found or you do not own this order"
            }), 404

        return jsonify({
            "success": True,
            "message": "Status Updated"
        })

    except Exception as e:

        print("Update order error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# CASH ON DELIVERY
# =========================================================

@app.route("/payment/cod", methods=["POST"])
def payment_cod():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        order_id = data.get("order_id")

        if not order_id:

            return jsonify({
                "success": False,
                "message": "Order ID is required"
            }), 400

        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET
                payment_method='COD',
                payment_status='Pending'
            WHERE id=%s
        """, (
            order_id,
        ))

        db.commit()

        updated = cursor.rowcount

        cursor.close()

        if updated == 0:

            return jsonify({
                "success": False,
                "message": "Order not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Cash on Delivery selected",
            "order_id": order_id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# CREATE RAZORPAY ORDER
# =========================================================

@app.route("/create-razorpay-order", methods=["POST"])
def create_razorpay_order():

    try:

        if razorpay_client is None:

            return jsonify({
                "success": False,
                "message": "Razorpay is not configured on the server."
            }), 500

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "No data received"
            }), 400

        order_id = data.get("order_id")

        if not order_id:

            return jsonify({
                "success": False,
                "message": "Order ID is required"
            }), 400

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                total_price,
                payment_status
            FROM orders
            WHERE id=%s
        """, (
            order_id,
        ))

        order_data = cursor.fetchone()

        cursor.close()

        if not order_data:

            return jsonify({
                "success": False,
                "message": "Order not found"
            }), 404

        if order_data["payment_status"] == "Paid":

            return jsonify({
                "success": False,
                "message": "This order is already paid"
            }), 400

        amount = int(
            round(
                float(order_data["total_price"]) * 100
            )
        )

        if amount <= 0:

            return jsonify({
                "success": False,
                "message": "Invalid order amount"
            }), 400

        razorpay_order = razorpay_client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": "farmconnect_" + str(order_id),
            "payment_capture": 1
        })

        return jsonify({
            "success": True,
            "key_id": RAZORPAY_KEY_ID,
            "razorpay_order_id": razorpay_order["id"],
            "amount": amount,
            "currency": "INR"
        })

    except Exception as e:

        print("Razorpay order error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# VERIFY RAZORPAY PAYMENT
# =========================================================

@app.route("/verify-payment", methods=["POST"])
def verify_payment():

    try:

        if razorpay_client is None:

            return jsonify({
                "success": False,
                "message": "Razorpay is not configured on the server."
            }), 500

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "No payment data received"
            }), 400

        order_id = data.get("order_id")

        razorpay_order_id = data.get(
            "razorpay_order_id"
        )

        razorpay_payment_id = data.get(
            "razorpay_payment_id"
        )

        razorpay_signature = data.get(
            "razorpay_signature"
        )

        if not order_id:

            return jsonify({
                "success": False,
                "message": "Order ID missing"
            }), 400

        if not razorpay_order_id:

            return jsonify({
                "success": False,
                "message": "Razorpay Order ID missing"
            }), 400

        if not razorpay_payment_id:

            return jsonify({
                "success": False,
                "message": "Razorpay Payment ID missing"
            }), 400

        if not razorpay_signature:

            return jsonify({
                "success": False,
                "message": "Payment signature missing"
            }), 400

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                payment_status
            FROM orders
            WHERE id=%s
        """, (
            order_id,
        ))

        order_data = cursor.fetchone()

        cursor.close()

        if not order_data:

            return jsonify({
                "success": False,
                "message": "Order not found"
            }), 404

        verification_data = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        }

        try:

            razorpay_client.utility.verify_payment_signature(
                verification_data
            )

        except Exception:

            return jsonify({
                "success": False,
                "message": "Payment verification failed"
            }), 400

        cursor = db.cursor()

        cursor.execute("""
            UPDATE orders
            SET
                payment_method=%s,
                payment_status=%s
            WHERE id=%s
        """, (
            "Razorpay",
            "Paid",
            order_id
        ))

        db.commit()

        cursor.close()

        return jsonify({
            "success": True,
            "message": "Payment verified successfully",
            "order_id": order_id,
            "payment_id": razorpay_payment_id
        })

    except Exception as e:

        print("Payment verification error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# ORDER STATUS
# =========================================================

@app.route("/order-status/<int:order_id>")
def order_status(order_id):

    try:

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                status,
                payment_method,
                payment_status
            FROM orders
            WHERE id=%s
        """, (
            order_id,
        ))

        result = cursor.fetchone()

        cursor.close()

        if result:

            return jsonify({
                "success": True,
                **result
            })

        return jsonify({
            "success": False,
            "message": "Order not found"
        }), 404

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# CUSTOMER ORDERS PAGE
# =========================================================

@app.route("/customerOrders")
def customer_orders():

    return send_from_directory(
        FRONTEND_FOLDER,
        "customerOrders.html"
    )


# =========================================================
# ORDER SUCCESS PAGE
# =========================================================

@app.route("/order_success")
def order_success():

    return send_from_directory(
        FRONTEND_FOLDER,
        "orderSuccess.html"
    )


# =========================================================
# FARMER DASHBOARD
# =========================================================

@app.route("/farmer-dashboard")
def farmer_dashboard():

    if "farmer_id" not in session:

        return redirect(
            "/farmer-login.html"
        )

    return send_from_directory(
        FRONTEND_FOLDER,
        "farmerDashboard.html"
    )


# =========================================================
# DASHBOARD STATISTICS
# =========================================================

@app.route("/dashboard-stats")
def dashboard_stats():

    if "farmer_id" not in session:

        return jsonify({
            "success": False,
            "message": "Please login as farmer"
        }), 401

    try:

        farmer_id = session["farmer_id"]
        farmer_name = session.get("farmer_name", "")

        cursor = db.cursor(dictionary=True)

        # =====================================================
        # TOTAL PRODUCTS OF LOGGED-IN FARMER
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM products
            WHERE farmer_id=%s
        """, (
            farmer_id,
        ))

        total_products = cursor.fetchone()["total"]

        # =====================================================
        # TOTAL ORDERS OF LOGGED-IN FARMER
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders
            WHERE farmer_id=%s
        """, (
            farmer_id,
        ))

        total_orders = cursor.fetchone()["total"]

        # =====================================================
        # PENDING ORDERS
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders
            WHERE farmer_id=%s
            AND status='Pending'
        """, (
            farmer_id,
        ))

        pending_orders = cursor.fetchone()["total"]

        # =====================================================
        # DELIVERED ORDERS
        # =====================================================

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM orders
            WHERE farmer_id=%s
            AND status='Delivered'
        """, (
            farmer_id,
        ))

        delivered_orders = cursor.fetchone()["total"]

        # =====================================================
        # TOTAL SALES
        # Only delivered orders are counted as sales.
        # =====================================================

        cursor.execute("""
            SELECT
                IFNULL(
                    SUM(total_price),
                    0
                ) AS sales
            FROM orders
            WHERE farmer_id=%s
            AND status='Delivered'
        """, (
            farmer_id,
        ))

        total_sales = cursor.fetchone()["sales"]

        cursor.close()

        return jsonify({
            "success": True,
            "farmerName": farmer_name,
            "totalProducts": total_products,
            "totalOrders": total_orders,
            "pendingOrders": pending_orders,
            "deliveredOrders": delivered_orders,
            "totalSales": float(
                total_sales or 0
            )
        })

    except Exception as e:

        print("Dashboard stats error:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================================================
# FRONTEND FILES
# =========================================================

@app.route("/<path:filename>")
def frontend_files(filename):

    return send_from_directory(
        FRONTEND_FOLDER,
        filename
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )