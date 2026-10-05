import os
import smtplib
import sqlite3
import uuid
from email.message import EmailMessage

from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import stripe
except ImportError:  # pragma: no cover
    stripe = None

load_dotenv()

app = Flask(__name__)
IS_RENDER = os.getenv('RENDER', '').lower() == 'true'
IS_PRODUCTION = IS_RENDER or os.getenv('COREMAN_PRODUCTION', '').lower() == 'true'
COD_ONLY = os.getenv('COREMAN_COD_ONLY', '').lower() == 'true'
secret_key = os.getenv('SECRET_KEY')
if IS_PRODUCTION and not secret_key:
    raise RuntimeError('SECRET_KEY must be configured for production.')
app.secret_key = secret_key or 'coreman-secret-key-2026'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
DATA_DIR = os.getenv('COREMAN_DATA_DIR') or os.path.dirname(__file__)
DB = os.path.join(DATA_DIR, 'coreman.db')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads') if os.getenv('COREMAN_DATA_DIR') else os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PRODUCTS = [
    (1, 'Classic Black Tee', 'T-Shirts', 890, '/static/uploads/default-classic-black-tee.svg'),
    (2, 'Premium White Shirt', 'Shirts', 1490, '/static/uploads/default-premium-white-shirt.svg'),
    (3, 'Urban Denim Jacket', 'Jackets', 2590, '/static/uploads/default-urban-denim-jacket.svg'),
    (4, 'Essential Polo', 'Polo', 1290, '/static/uploads/default-essential-polo.svg'),
    (5, 'Relaxed Cargo Pants', 'Pants', 1890, '/static/uploads/default-relaxed-cargo-pants.svg'),
    (6, 'Minimal Hoodie', 'Hoodies', 1990, '/static/uploads/default-minimal-hoodie.svg'),
]

APP_ADMIN_USER = os.getenv('COREMAN_ADMIN_USERNAME', 'admin')
APP_ADMIN_PASSWORD = os.getenv('COREMAN_ADMIN_PASSWORD', 'Coreman@2026!')
if IS_PRODUCTION and (APP_ADMIN_USER == 'admin' or APP_ADMIN_PASSWORD == 'Coreman@2026!'):
    raise RuntimeError('Set unique COREMAN_ADMIN_USERNAME and COREMAN_ADMIN_PASSWORD values for production.')
app.config['ADMIN_USER'] = APP_ADMIN_USER
app.config['ADMIN_PASS_HASH'] = generate_password_hash(APP_ADMIN_PASSWORD)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def ensure_column(table, column_name, column_sql):
    con = db()
    c = con.cursor()
    columns = [row['name'] for row in c.execute(f'PRAGMA table_info({table})').fetchall()]
    if column_name not in columns:
        c.execute(f'ALTER TABLE {table} ADD COLUMN {column_sql}')
    con.commit()
    con.close()


def init_db():
    con = db()
    c = con.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT,category TEXT,price REAL,image TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders(
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
    c.execute('''CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER,product_id INTEGER,name TEXT,qty INTEGER,price REAL)''')
    if c.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
        c.executemany('INSERT INTO products VALUES (?,?,?,?,?)', PRODUCTS)
    con.commit()
    con.close()
    ensure_column('orders', 'status', "status TEXT DEFAULT 'Pending'")
    ensure_column('orders', 'estimated_delivery', "estimated_delivery TEXT DEFAULT '3-4 days'")


init_db()


@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {}) or {}
    item_count = sum(int(qty) for qty in cart.values() if str(qty).isdigit())
    return {'cart_count': item_count}


def cart_items():
    cart = session.get('cart', {}) or {}
    if not cart:
        return [], 0
    con = db()
    rows = []
    total = 0
    for pid, qty in cart.items():
        product = con.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
        if product:
            item = dict(product)
            item['qty'] = int(qty)
            item['subtotal'] = product['price'] * int(qty)
            rows.append(item)
            total += item['subtotal']
    con.close()
    return rows, total


def delivery_eta_for_address(address):
    address_lower = (address or '').lower()
    dhaka_keywords = [
        'dhaka', 'motijheel', 'gulshan', 'banani', 'uttara', 'dhanmondi',
        'mirpur', 'baridhara', 'badda', 'tejgaon', 'shahbagh', 'ramna', 'khulna'
    ]
    if any(keyword in address_lower for keyword in dhaka_keywords):
        return '3-4 days'
    return '1 week'


def send_order_email(email, order_id, total, method, delivery_eta, address):
    subject = f'COREMAN order confirmation #{order_id}'
    body = (
        f'Hello,\n\n'
        f'Your order #{order_id} has been confirmed.\n'
        f'Total: ৳{total:.0f}\n'
        f'Payment: {method}\n'
        f'Delivery ETA: {delivery_eta}\n'
        f'Delivery Address: {address}\n\n'
        f'Thank you for shopping with COREMAN.'
    )

    smtp_host = os.getenv('SMTP_HOST')
    if not smtp_host:
        print(f'\n--- ORDER EMAIL (simulated) ---\n{subject}\n{body}\n')
        return True

    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    sender_email = os.getenv('EMAIL_FROM', 'no-reply@coreman.com')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender_email
    message['To'] = email
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        return True
    except Exception as exc:
        print(f'Email send failed: {exc}')
        return False


def normalize_image_url(value):
    if not value:
        return '/static/uploads/default-placeholder.svg'
    if value.startswith('http://') or value.startswith('https://'):
        return value
    if value.startswith('/static/'):
        return value
    if value.startswith('uploads/'):
        return f"/static/{value}"
    return f"/static/uploads/{value}"


def save_uploaded_image(file_storage):
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None

    allowed_exts = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
    filename = file_storage.filename.lower()
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    if ext not in allowed_exts:
        return None

    unique_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file_storage.save(save_path)
    if os.getenv('COREMAN_DATA_DIR'):
        return url_for('uploaded_image', filename=unique_name)
    return f"/static/uploads/{unique_name}"


@app.get('/uploads/<path:filename>')
def uploaded_image(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


def stripe_checkout_session(order_id, total, email, name, phone, address):
    provider = os.getenv('PAYMENT_PROVIDER', 'stripe').lower()
    if provider != 'stripe':
        return None
    key = os.getenv('STRIPE_SECRET_KEY')
    if not key or stripe is None:
        return None

    stripe.api_key = key
    try:
        session = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': 'bdt',
                    'product_data': {'name': f'COREMAN Order #{order_id}'},
                    'unit_amount': int(float(total) * 100),
                },
                'quantity': 1,
            }],
            success_url='http://127.0.0.1:5000/checkout?paid=1',
            cancel_url='http://127.0.0.1:5000/checkout',
            customer_email=email,
            metadata={'order_id': str(order_id), 'name': name, 'phone': phone, 'address': address},
        )
        return session.url
    except Exception as exc:  # pragma: no cover
        print(f'Stripe payment error: {exc}')
        return None


def admin_required(view):
    def wrapped(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please sign in to access the admin dashboard.', 'error')
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)

    wrapped.__name__ = view.__name__
    return wrapped


@app.route('/')
def home():
    con = db()
    products = con.execute('SELECT * FROM products').fetchall()
    con.close()
    return render_template('index.html', products=products)


@app.route('/product/<int:pid>')
def product(pid):
    con = db()
    item = con.execute('SELECT * FROM products WHERE id=?', (pid,)).fetchone()
    con.close()
    if not item:
        return 'Product not found', 404
    return render_template('product.html', p=item)


@app.post('/cart/add')
def add_cart():
    product_id = str(request.form['product_id'])
    cart = session.setdefault('cart', {})
    cart[product_id] = cart.get(product_id, 0) + 1
    session.modified = True
    return redirect(request.referrer or url_for('home'))


@app.get('/cart')
def cart():
    items, total = cart_items()
    return render_template('cart.html', items=items, total=total)


@app.post('/cart/update')
def update_cart():
    cart = session.setdefault('cart', {})
    for key, value in request.form.items():
        if key.startswith('qty_'):
            product_id = key[4:]
            try:
                qty = max(0, int(value))
            except ValueError:
                qty = 0
            if qty:
                cart[product_id] = qty
            else:
                cart.pop(product_id, None)
    session.modified = True
    return redirect(url_for('cart'))


@app.get('/checkout')
def checkout():
    items, total = cart_items()
    if not items:
        return redirect(url_for('home'))
    return render_template('checkout.html', items=items, total=total, cod_only=COD_ONLY)


@app.post('/checkout')
def place_order():
    items, total = cart_items()
    if not items:
        return redirect(url_for('home'))

    name = request.form['name'].strip()
    email = request.form['email'].strip()
    phone = request.form['phone'].strip()
    address = request.form['address'].strip()
    method = request.form['payment_method']
    if COD_ONLY and method != 'Cash on Delivery':
        flash('Online payment is not available yet. Please choose Cash on Delivery.', 'error')
        return redirect(url_for('checkout'))
    delivery_eta = delivery_eta_for_address(address)

    con = db()
    cur = con.cursor()
    cur.execute(
        'INSERT INTO orders(name,email,phone,address,total,payment_method,payment_status,status,estimated_delivery) VALUES (?,?,?,?,?,?,?,?,?)',
        (name, email, phone, address, total, method, 'Pending', 'Pending', delivery_eta),
    )
    order_id = cur.lastrowid
    for item in items:
        cur.execute(
            'INSERT INTO order_items(order_id,product_id,name,qty,price) VALUES (?,?,?,?,?)',
            (order_id, item['id'], item['name'], item['qty'], item['price']),
        )
    con.commit()
    con.close()

    session['cart'] = {}
    session.modified = True

    live_payment_url = None
    if method.lower() in {'card / online payment', 'online payment', 'stripe'}:
        live_payment_url = stripe_checkout_session(order_id, total, email, name, phone, address)

    send_order_email(email, order_id, total, method, delivery_eta, address)

    if live_payment_url:
        return redirect(live_payment_url)

    return render_template(
        'success.html',
        order_id=order_id,
        total=total,
        method=method,
        email=email,
        estimated_delivery=delivery_eta,
        address=address,
    )


@app.get('/dingidingi/admin/login')
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')


@app.post('/dingidingi/admin/login')
def admin_login_submit():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    if username == app.config['ADMIN_USER'] and check_password_hash(app.config['ADMIN_PASS_HASH'], password):
        session['admin_logged_in'] = True
        flash('Admin login successful.', 'success')
        return redirect(url_for('admin_dashboard'))
    flash('Invalid admin credentials.', 'error')
    return redirect(url_for('admin_login'))


@app.get('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('admin_login'))


@app.get('/admin')
@app.get('/admin/orders')
@admin_required
def admin_dashboard():
    con = db()
    orders = con.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()
    products = con.execute('SELECT * FROM products ORDER BY id ASC').fetchall()
    con.close()
    return render_template('admin.html', orders=orders, products=products)


@app.post('/admin/products/add')
@admin_required
def add_product():
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    price = request.form.get('price', '0')
    image_url = request.form.get('image_url', '').strip()
    uploaded_image = request.files.get('image')
    image = save_uploaded_image(uploaded_image) or normalize_image_url(image_url)
    if not name or not category:
        flash('Product name and category are required.', 'error')
        return redirect(url_for('admin_dashboard'))
    try:
        price_value = float(price)
    except ValueError:
        flash('Product price must be a valid number.', 'error')
        return redirect(url_for('admin_dashboard'))

    con = db()
    con.execute(
        'INSERT INTO products(name, category, price, image) VALUES (?, ?, ?, ?)',
        (name, category, price_value, image),
    )
    con.commit()
    con.close()
    flash('New product added successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.post('/admin/products/<int:product_id>/update')
@admin_required
def update_product(product_id):
    price = request.form.get('price', '0')
    try:
        price_value = float(price)
    except ValueError:
        flash('Price must be numeric.', 'error')
        return redirect(url_for('admin_dashboard'))

    con = db()
    con.execute('UPDATE products SET price=? WHERE id=?', (price_value, product_id))
    con.commit()
    con.close()
    flash('Product price updated successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.post('/admin/orders/<int:order_id>/update')
@admin_required
def update_order(order_id):
    status = request.form.get('status', 'Pending')
    payment_status = request.form.get('payment_status', 'Pending')
    con = db()
    if status == 'Cancelled':
        payment_status = 'Cancelled'
    con.execute(
        'UPDATE orders SET status=?, payment_status=? WHERE id=?',
        (status, payment_status, order_id),
    )
    con.commit()
    con.close()
    flash(f'Order #{order_id} updated successfully.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.get('/api/products')
def api_products():
    con = db()
    rows = [dict(row) for row in con.execute('SELECT * FROM products').fetchall()]
    con.close()
    return jsonify(rows)


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
