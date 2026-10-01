import os
import sqlite3
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# MYSQL DATABASE INITIALIZATION
# ============================================================

def init_mysql():
    print("Attempting to connect to Clever Cloud MySQL...")

    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )

    cursor = conn.cursor()

    # ========================================================
    # 1. USERS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
    );
    """)

    # ========================================================
    # 2. FARMERS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farmers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        mobile VARCHAR(20) NOT NULL,
        email VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
    );
    """)

    # ========================================================
    # 3. PRODUCTS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INT AUTO_INCREMENT PRIMARY KEY,
        product_name VARCHAR(255) NOT NULL,
        quantity DOUBLE DEFAULT 0.0,
        price DOUBLE NOT NULL,
        image LONGTEXT,
        description LONGTEXT,
        farmer_id INT NULL
    );
    """)

    # ========================================================
    # 4. ORDERS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        product_name VARCHAR(255) NOT NULL,
        customer_name VARCHAR(255) NOT NULL,
        mobile VARCHAR(20) NOT NULL,
        address VARCHAR(500) NOT NULL,
        quantity DOUBLE NOT NULL,
        total_price DOUBLE NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'Pending',
        payment_method VARCHAR(50),
        payment_status VARCHAR(50) DEFAULT 'Unpaid',
        farmer_id INT NULL,
        product_id INT NULL
    );
    """)

    conn.commit()

    # ========================================================
    # UPDATE EXISTING DATABASE TABLES
    #
    # CREATE TABLE IF NOT EXISTS does NOT add columns to
    # tables that already exist.
    #
    # These checks safely add the new columns if they are
    # missing.
    # ========================================================

    # Check products.farmer_id
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'products'
        AND COLUMN_NAME = 'farmer_id'
    """)

    products_farmer_id_exists = cursor.fetchone()[0]

    if products_farmer_id_exists == 0:
        print("Adding farmer_id to products table...")
        cursor.execute("""
            ALTER TABLE products
            ADD COLUMN farmer_id INT NULL
        """)
    else:
        print("products.farmer_id already exists.")

    # Check orders.farmer_id
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'farmer_id'
    """)

    orders_farmer_id_exists = cursor.fetchone()[0]

    if orders_farmer_id_exists == 0:
        print("Adding farmer_id to orders table...")
        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN farmer_id INT NULL
        """)
    else:
        print("orders.farmer_id already exists.")

    # Check orders.product_id
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'product_id'
    """)

    orders_product_id_exists = cursor.fetchone()[0]

    if orders_product_id_exists == 0:
        print("Adding product_id to orders table...")
        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN product_id INT NULL
        """)
    else:
        print("orders.product_id already exists.")

    conn.commit()

    cursor.close()
    conn.close()

    print("Successfully initialized Clever Cloud MySQL database!")
    print("Farmer ownership columns are ready.")


# ============================================================
# SQLITE DATABASE INITIALIZATION
# ============================================================

def init_sqlite():

    print("Initializing local SQLite database...")

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, "farmconnect.db")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # ========================================================
    # 1. USERS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    );
    """)

    # ========================================================
    # 2. FARMERS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS farmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    );
    """)

    # ========================================================
    # 3. PRODUCTS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        quantity REAL NOT NULL DEFAULT 0.0,
        price REAL NOT NULL,
        image TEXT,
        description TEXT,
        farmer_id INTEGER
    );
    """)

    # ========================================================
    # 4. ORDERS TABLE
    # ========================================================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        address TEXT NOT NULL,
        quantity REAL NOT NULL,
        total_price REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        payment_method TEXT,
        payment_status TEXT DEFAULT 'Unpaid',
        farmer_id INTEGER,
        product_id INTEGER
    );
    """)

    conn.commit()

    # ========================================================
    # UPDATE EXISTING SQLITE DATABASE
    # ========================================================

    # Get existing product columns
    cursor.execute("PRAGMA table_info(products)")
    product_columns = [row[1] for row in cursor.fetchall()]

    if "farmer_id" not in product_columns:
        print("Adding farmer_id to SQLite products table...")
        cursor.execute("""
            ALTER TABLE products
            ADD COLUMN farmer_id INTEGER
        """)
    else:
        print("SQLite products.farmer_id already exists.")

    # Get existing order columns
    cursor.execute("PRAGMA table_info(orders)")
    order_columns = [row[1] for row in cursor.fetchall()]

    if "farmer_id" not in order_columns:
        print("Adding farmer_id to SQLite orders table...")
        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN farmer_id INTEGER
        """)
    else:
        print("SQLite orders.farmer_id already exists.")

    if "product_id" not in order_columns:
        print("Adding product_id to SQLite orders table...")
        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN product_id INTEGER
        """)
    else:
        print("SQLite orders.product_id already exists.")

    conn.commit()
    conn.close()

    print("Local SQLite database initialized successfully!")
    print("Farmer ownership columns are ready.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    try:
        # Try Clever Cloud MySQL first
        init_mysql()

    except Exception as e:

        print("")
        print("==============================================")
        print("MySQL initialization failed!")
        print("==============================================")
        print(f"Error: {e}")
        print("")

        # Fallback to local SQLite
        init_sqlite()