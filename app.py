from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------- DATA STORAGE ----------------
users = []
products = []
orders = []

# ---------------- HOME ----------------
@app.route("/")
def home():
    return "FarmConnect Backend Running"

# ---------------- USER REGISTRATION ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    users.append(data)
    return jsonify({"message": "Registered Successfully"})

# ---------------- PRODUCTS ----------------
@app.route("/products")
def get_products():
    return jsonify(products)

@app.route("/add-product", methods=["POST"])
def add_product():
    data = request.json
    products.append(data)
    return jsonify({"message": "Product Added"})

# ---------------- ORDERS ----------------
@app.route("/order", methods=["POST"])
def order():
    data = request.get_json()

    if data:
        orders.append(data)

    return jsonify({"message": "Order Placed"})

@app.route("/orders")
def get_orders():
    return jsonify(orders)

# ---------------- AI DESCRIPTION ----------------
@app.route("/generate-description", methods=["POST"])
def generate_description():

    data = request.json

    product = data.get("product")
    location = data.get("location")

    description = f"Fresh {product} grown in {location}. High quality farm produce directly from farmers."

    return jsonify({
        "description": description
    })

# ---------------- AI PRICE PREDICTION ----------------
@app.route("/predict-price", methods=["POST"])
def predict_price():

    data = request.json

    product = data.get("product")
    location = data.get("location")

    base_prices = {
        "tomato": 25,
        "onion": 30,
        "potato": 20,
        "rice": 40
    }

    price = base_prices.get(product.lower(), 25)

    if location.lower() in ["mumbai", "pune"]:
        price += 5

    return jsonify({
        "product": product,
        "location": location,
        "predicted_price_per_kg": price
    })

# ---------------- RUN SERVER ----------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)