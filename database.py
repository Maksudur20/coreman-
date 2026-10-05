import os
import sqlite3
import re
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# Ensure environment variables are loaded
load_dotenv()

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

DEFAULT_PRODUCTS = [
    (1, 'Classic Black Tee', 'T-Shirts', 890.0, 45, 'Premium breathable combed cotton tee designed for daily comfort.', 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=900', True),
    (2, 'Premium White Shirt', 'Shirts', 1490.0, 30, 'Crisp formal tailored shirt with breathable cotton weave.', 'https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=900', True),
    (3, 'Urban Denim Jacket', 'Jackets', 2590.0, 20, 'Heavyweight vintage denim with reinforced double-stitch detailing.', 'https://images.unsplash.com/photo-1551028719-00167b16eac5?w=900', True),
    (4, 'Essential Polo', 'Polo', 1290.0, 35, 'Classic pique knit polo shirt with ribbed collar and premium buttons.', 'https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=900', True),
    (5, 'Relaxed Cargo Pants', 'Pants', 1890.0, 25, 'Modern utilitarian multi-pocket cargo pants with ergonomic fit.', 'https://images.unsplash.com/photo-1624378439575-d8705ad7ae80?w=900', True),
    (6, 'Minimal Hoodie', 'Hoodies', 1990.0, 18, 'Fleece-lined heavyweight pullover hoodie with kangaroo pocket.', 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=900', True),
]

_pg_pool = None

def get_database_url():
    return os.getenv('DATABASE_URL', '').strip()

def is_postgres():
    url = get_database_url()
    return bool(psycopg2 and (url.startswith('postgresql://') or url.startswith('postgres://')))

def get_pg_pool():
    global _pg_pool
    if _pg_pool is None and is_postgres():
        db_url = get_database_url()
        _pg_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=db_url,
            connect_timeout=10,
            sslmode='require',
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )
    return _pg_pool

# In-Memory Smart Cache for Ultra-Fast Loading
_SETTINGS_CACHE = None
_SETTINGS_CACHE_TIME = 0
_PRODUCTS_CACHE = None
_PRODUCTS_CACHE_TIME = 0

def get_cached_settings():
    global _SETTINGS_CACHE, _SETTINGS_CACHE_TIME
    import time
    now = time.time()
    if _SETTINGS_CACHE is not None and (now - _SETTINGS_CACHE_TIME < 300):
        return _SETTINGS_CACHE
    try:
        rows = query_all('SELECT key, value FROM store_settings')
        _SETTINGS_CACHE = {r['key']: r['value'] for r in rows}
        _SETTINGS_CACHE_TIME = now
    except Exception:
        if _SETTINGS_CACHE is None:
            _SETTINGS_CACHE = {}
    return _SETTINGS_CACHE

def invalidate_settings_cache():
    global _SETTINGS_CACHE, _SETTINGS_CACHE_TIME
    _SETTINGS_CACHE = None
    _SETTINGS_CACHE_TIME = 0

def get_cached_products():
    global _PRODUCTS_CACHE, _PRODUCTS_CACHE_TIME
    import time
    now = time.time()
    if _PRODUCTS_CACHE is not None and (now - _PRODUCTS_CACHE_TIME < 60):
        return _PRODUCTS_CACHE
    try:
        rows = query_all('SELECT * FROM products ORDER BY id ASC')
        for r in rows:
            r['price'] = float(r['price'])
            r['stock'] = int(r.get('stock') or 0)
        _PRODUCTS_CACHE = rows
        _PRODUCTS_CACHE_TIME = now
    except Exception:
        if _PRODUCTS_CACHE is None:
            _PRODUCTS_CACHE = []
    return _PRODUCTS_CACHE

def get_cached_product_by_id(pid):
    prods = get_cached_products()
    for p in prods:
        if p['id'] == pid:
            return dict(p)
    p = query_one('SELECT * FROM products WHERE id = ?', (pid,))
    if p:
        p['price'] = float(p['price'])
        p['stock'] = int(p.get('stock') or 0)
    return p

def invalidate_products_cache():
    global _PRODUCTS_CACHE, _PRODUCTS_CACHE_TIME
    _PRODUCTS_CACHE = None
    _PRODUCTS_CACHE_TIME = 0

class DBWrapper:
    """A wrapper for database connection that provides unified dict-like access and query helpers."""
    def __init__(self, conn, is_pg=False):
        self.conn = conn
        self.is_pg = is_pg

    def cursor(self):
        if self.is_pg:
            return self.conn.cursor(cursor_factory=RealDictCursor)
        return self.conn.cursor()

    def execute(self, sql, params=()):
        cur = self.cursor()
        if self.is_pg:
            sql = re.sub(r'\?', '%s', sql)
            cur.execute(sql, params)
        else:
            cur.execute(sql, params)
        return cur

    def execute_insert(self, sql, params=(), id_col='id'):
        cur = self.cursor()
        if self.is_pg:
            sql_pg = re.sub(r'\?', '%s', sql)
            if 'RETURNING' not in sql_pg.upper():
                sql_pg = f"{sql_pg.rstrip(';')} RETURNING {id_col}"
            cur.execute(sql_pg, params)
            row = cur.fetchone()
            return row[id_col] if row else None
        else:
            cur.execute(sql, params)
            return cur.lastrowid

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        if self.is_pg:
            pool_inst = get_pg_pool()
            if pool_inst and self.conn:
                try:
                    pool_inst.putconn(self.conn)
                except Exception:
                    self.conn.close()
        else:
            self.conn.close()

def get_db():
    """Returns a DBWrapper instance wrapping either PostgreSQL (Supabase) or SQLite."""
    if is_postgres():
        pool_inst = get_pg_pool()
        if pool_inst:
            raw_conn = pool_inst.getconn()
            raw_conn.autocommit = False
            return DBWrapper(raw_conn, is_pg=True)
        else:
            raw_conn = psycopg2.connect(get_database_url(), sslmode='require')
            return DBWrapper(raw_conn, is_pg=True)
    else:
        data_dir = os.getenv('COREMAN_DATA_DIR') or os.path.dirname(__file__)
        db_path = os.path.join(data_dir, 'coreman.db')
        raw_conn = sqlite3.connect(db_path)
        raw_conn.row_factory = sqlite3.Row
        return DBWrapper(raw_conn, is_pg=False)

def query_all(sql, params=()):
    db_inst = get_db()
    try:
        cur = db_inst.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        db_inst.close()

def query_one(sql, params=()):
    db_inst = get_db()
    try:
        cur = db_inst.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        db_inst.close()

def execute_write(sql, params=()):
    db_inst = get_db()
    try:
        cur = db_inst.execute(sql, params)
        db_inst.commit()
        return cur.rowcount
    except Exception:
        db_inst.rollback()
        raise
    finally:
        db_inst.close()

def init_db():
    """Initializes tables, creates indexes, seeds default data and migrates from SQLite if applicable."""
    db_conn = get_db()
    is_pg = db_conn.is_pg

    try:
        cur = db_conn.cursor()
        if is_pg:
            # PostgreSQL Schema
            cur.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                category VARCHAR(100) NOT NULL,
                price NUMERIC(10,2) NOT NULL,
                stock INTEGER DEFAULT 50,
                description TEXT DEFAULT '',
                image TEXT DEFAULT '',
                is_featured BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                phone VARCHAR(50),
                address TEXT,
                total NUMERIC(10,2) NOT NULL,
                payment_method VARCHAR(100),
                payment_status VARCHAR(50) DEFAULT 'Pending',
                status VARCHAR(50) DEFAULT 'Pending',
                estimated_delivery VARCHAR(100) DEFAULT '3-4 days',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER,
                name VARCHAR(255),
                qty INTEGER DEFAULT 1,
                price NUMERIC(10,2)
            );
            ''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS admin_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(50) DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            cur.execute('''
            CREATE TABLE IF NOT EXISTS store_settings (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT
            );
            ''')

            # Indexes recommended by best practices
            cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);')
            # Safe schema migrations for district & delivery_fee
            try:
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS district VARCHAR(100) DEFAULT 'Dhaka';")
                cur.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee NUMERIC(10,2) DEFAULT 0;")
                db_conn.commit()
            except Exception as se:
                print(f"Schema migration notice: {se}")
                db_conn.rollback()

            db_conn.commit()

            # Check if products exist
            cur.execute('SELECT COUNT(*) AS cnt FROM products;')
            row = cur.fetchone()
            count = row['cnt'] if isinstance(row, dict) else row[0]

            if count == 0:
                sqlite_path = os.path.join(os.path.dirname(__file__), 'coreman.db')
                migrated = False
                if os.path.exists(sqlite_path):
                    try:
                        scon = sqlite3.connect(sqlite_path)
                        scon.row_factory = sqlite3.Row
                        scur = scon.cursor()
                        scur.execute('SELECT * FROM products')
                        sq_prods = scur.fetchall()
                        if sq_prods:
                            for sp in sq_prods:
                                cur.execute(
                                    '''INSERT INTO products (name, category, price, stock, description, image, is_featured)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                                    (sp['name'], sp['category'], float(sp['price']), 50, '', sp['image'], True)
                                )
                            db_conn.commit()
                            migrated = True

                        scur.execute('SELECT * FROM orders')
                        sq_orders = scur.fetchall()
                        for so in sq_orders:
                            cur.execute(
                                '''INSERT INTO orders (id, name, email, phone, address, total, payment_method, payment_status, status, estimated_delivery, created_at)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                   ON CONFLICT (id) DO NOTHING''',
                                (so['id'], so['name'], so['email'], so['phone'], so['address'], float(so['total']),
                                 so['payment_method'], so['payment_status'] or 'Pending', so['status'] or 'Pending',
                                 so['estimated_delivery'] or '3-4 days', so['created_at'])
                            )
                        scur.execute('SELECT * FROM order_items')
                        sq_items = scur.fetchall()
                        for si in sq_items:
                            cur.execute(
                                '''INSERT INTO order_items (order_id, product_id, name, qty, price)
                                   VALUES (%s, %s, %s, %s, %s)''',
                                (si['order_id'], si['product_id'], si['name'], si['qty'], float(si['price']))
                            )
                        cur.execute("SELECT setval('orders_id_seq', COALESCE((SELECT MAX(id) FROM orders), 1), true);")
                        cur.execute("SELECT setval('products_id_seq', COALESCE((SELECT MAX(id) FROM products), 1), true);")
                        db_conn.commit()
                        scon.close()
                    except Exception as me:
                        print(f"Migration from SQLite warning: {me}")
                        db_conn.rollback()

                if not migrated:
                    cur.execute("SELECT value FROM store_settings WHERE key = 'db_initialized'")
                    already_inited = cur.fetchone()
                    if not already_inited:
                        for prod in DEFAULT_PRODUCTS:
                            cur.execute(
                                '''INSERT INTO products (name, category, price, stock, description, image, is_featured)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                                (prod[1], prod[2], prod[3], prod[4], prod[5], prod[6], prod[7])
                            )
                        db_conn.commit()

            # Ensure admin user exists
            admin_user = os.getenv('COREMAN_ADMIN_USERNAME', 'admin')
            admin_pass = os.getenv('COREMAN_ADMIN_PASSWORD', 'Coreman@Admin#2026')
            cur.execute('SELECT id FROM admin_users WHERE username = %s', (admin_user,))
            if not cur.fetchone():
                hashed = generate_password_hash(admin_pass, method='scrypt')
                cur.execute('INSERT INTO admin_users (username, password_hash, role) VALUES (%s, %s, %s)',
                            (admin_user, hashed, 'admin'))
                db_conn.commit()
            else:
                # Update password hash to match current env admin password
                hashed = generate_password_hash(admin_pass, method='scrypt')
                cur.execute('UPDATE admin_users SET password_hash = %s WHERE username = %s', (hashed, admin_user))
                db_conn.commit()

            # Seed default store settings if missing
            default_settings = [
                ('store_name', 'COREMAN'),
                ('currency', '৳'),
                ('delivery_fee_dhaka', '60'),
                ('delivery_fee_outside', '120'),
                ('free_shipping_threshold', '3000'),
                ('contact_phone', '+8801410141584'),
                ('contact_email', 'support@coreman.com'),
                ('announcement', 'Enjoy free shipping inside Dhaka on orders above ৳3000!')
            ]
            for k, v in default_settings:
                cur.execute(
                    '''INSERT INTO store_settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING''',
                    (k, v)
                )
            db_conn.commit()

        else:
            # SQLite fallback schema
            cur.execute('''CREATE TABLE IF NOT EXISTS products(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                category TEXT,
                price REAL,
                stock INTEGER DEFAULT 50,
                description TEXT DEFAULT '',
                image TEXT,
                is_featured INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                total REAL,
                payment_method TEXT,
                payment_status TEXT DEFAULT 'Pending',
                status TEXT DEFAULT 'Pending',
                estimated_delivery TEXT DEFAULT '3-4 days',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS order_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_id INTEGER,
                name TEXT,
                qty INTEGER,
                price REAL
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS admin_users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS store_settings(
                key TEXT PRIMARY KEY,
                value TEXT
            )''')

            columns = [r[1] for r in cur.execute('PRAGMA table_info(products)').fetchall()]
            for col_name, col_def in [
                ('stock', 'INTEGER DEFAULT 50'),
                ('description', "TEXT DEFAULT ''"),
                ('is_featured', 'INTEGER DEFAULT 1'),
                ('created_at', 'TIMESTAMP DEFAULT NULL'),
            ]:
                if col_name not in columns:
                    try:
                        cur.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_def}")
                    except Exception:
                        pass

            columns_ord = [r[1] for r in cur.execute('PRAGMA table_info(orders)').fetchall()]
            for col_name, col_def in [
                ('status', "TEXT DEFAULT 'Pending'"),
                ('estimated_delivery', "TEXT DEFAULT '3-4 days'"),
                ('district', "TEXT DEFAULT 'Dhaka'"),
                ('delivery_fee', 'REAL DEFAULT 0'),
            ]:
                if col_name not in columns_ord:
                    try:
                        cur.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_def}")
                    except Exception:
                        pass

            cur.execute("SELECT value FROM store_settings WHERE key = 'db_initialized'")
            sqlite_inited = cur.fetchone()
            if not sqlite_inited and cur.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
                for prod in DEFAULT_PRODUCTS:
                    cur.execute(
                        'INSERT INTO products (name, category, price, stock, description, image, is_featured) VALUES (?,?,?,?,?,?,?)',
                        (prod[1], prod[2], prod[3], prod[4], prod[5], prod[6], 1)
                    )

            admin_user = os.getenv('COREMAN_ADMIN_USERNAME', 'admin')
            admin_pass = os.getenv('COREMAN_ADMIN_PASSWORD', 'Coreman@Admin#2026')
            admin_row = cur.execute('SELECT id FROM admin_users WHERE username=?', (admin_user,))
            if not admin_row.fetchone():
                hashed = generate_password_hash(admin_pass, method='scrypt')
                cur.execute('INSERT INTO admin_users (username, password_hash, role) VALUES (?,?,?)', (admin_user, hashed, 'admin'))
            else:
                hashed = generate_password_hash(admin_pass, method='scrypt')
                cur.execute('UPDATE admin_users SET password_hash=? WHERE username=?', (hashed, admin_user))

            default_settings = [
                ('store_name', 'COREMAN'),
                ('currency', '৳'),
                ('delivery_fee_dhaka', '60'),
                ('delivery_fee_outside', '120'),
                ('free_shipping_threshold', '3000'),
                ('contact_phone', '+8801410141584'),
                ('contact_email', 'support@coreman.com'),
                ('announcement', 'Enjoy free shipping inside Dhaka on orders above ৳3000!'),
                ('db_initialized', 'true')
            ]
            for k, v in default_settings:
                cur.execute('INSERT OR IGNORE INTO store_settings (key, value) VALUES (?, ?)', (k, v))

            db_conn.commit()

    finally:
        db_conn.close()
