import json
import os
import smtplib
import time
import uuid
from decimal import Decimal
from email.message import EmailMessage

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import database
from database import (
    execute_write,
    get_cached_product_by_id,
    get_cached_products,
    get_cached_settings,
    get_db,
    invalidate_products_cache,
    invalidate_settings_cache,
    is_postgres,
    query_all,
    query_one,
)

try:
    import stripe
except ImportError:
    stripe = None

load_dotenv()

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # 1 day browser cache for static CSS/JS/images
IS_RENDER = os.getenv('RENDER', '').lower() == 'true'
IS_PRODUCTION = IS_RENDER or os.getenv('COREMAN_PRODUCTION', '').lower() == 'true'
COD_ONLY = os.getenv('COREMAN_COD_ONLY', '').lower() == 'true'

# Secure secret key
secret_key = os.getenv('SECRET_KEY')
if IS_PRODUCTION and not secret_key:
    raise RuntimeError('SECRET_KEY must be configured for production.')
app.secret_key = secret_key or 'coreman-super-secure-session-key-2026'

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

DATA_DIR = os.getenv('COREMAN_DATA_DIR') or os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'uploads') if os.getenv('COREMAN_DATA_DIR') else os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database schema and migrate data
database.init_db()

# Rate limiting storage for admin login
LOGIN_ATTEMPTS = {}


def check_rate_limit(ip):
    now = time.time()
    record = LOGIN_ATTEMPTS.get(ip, {'count': 0, 'locked_until': 0})
    if record['locked_until'] > now:
        return False, int(record['locked_until'] - now)
    return True, 0


def record_failed_attempt(ip):
    now = time.time()
    record = LOGIN_ATTEMPTS.get(ip, {'count': 0, 'locked_until': 0})
    record['count'] += 1
    if record['count'] >= 5:
        record['locked_until'] = now + 120  # 2 minute lockout
        record['count'] = 0
    LOGIN_ATTEMPTS[ip] = record


def reset_failed_attempts(ip):
    LOGIN_ATTEMPTS.pop(ip, None)


BANGLADESH_DISTRICTS = {
    'Dhaka Division': [
        ('Dhaka', 'ঢাকা (Metro)', 60),
        ('Gazipur', 'গাজীপুর', 80),
        ('Narayanganj', 'নারায়ণগঞ্জ', 80),
        ('Tangail', 'টাঙ্গাইল', 120),
        ('Narsingdi', 'নরসিংদী', 100),
        ('Manikganj', 'মানিকগঞ্জ', 100),
        ('Munshiganj', 'মুন্সীগঞ্জ', 100),
        ('Kishoreganj', 'কিশোরগঞ্জ', 120),
        ('Faridpur', 'ফরিদপুর', 120),
        ('Gopalganj', 'গোপালগঞ্জ', 120),
        ('Madaripur', 'মাদারীপুর', 120),
        ('Rajbari', 'রাজবাড়ী', 120),
        ('Shariatpur', 'শরীয়তপুর', 120),
    ],
    'Chattogram Division': [
        ('Chittagong', 'চট্টগ্রাম', 120),
        ('Cox\'s Bazar', 'কক্সবাজার', 130),
        ('Cumilla', 'কুমিল্লা', 110),
        ('Feni', 'ফেনী', 110),
        ('Brahmanbaria', 'ব্রাহ্মণবাড়িয়া', 120),
        ('Chandpur', 'চাঁদপুর', 120),
        ('Noakhali', 'নোয়াখালী', 120),
        ('Lakshmipur', 'লক্ষ্মীপুর', 120),
        ('Rangamati', 'রাঙ্গামাটি', 140),
        ('Bandarban', 'বান্দরবান', 140),
        ('Khagrachhari', 'খাগড়াছড়ি', 140),
    ],
    'Sylhet Division': [
        ('Sylhet', 'সিলেট', 120),
        ('Moulvibazar', 'মৌলভীবাজার', 120),
        ('Habiganj', 'হবিগঞ্জ', 120),
        ('Sunamganj', 'সুনামগঞ্জ', 130),
    ],
    'Rajshahi Division': [
        ('Rajshahi', 'রাজশাহী', 120),
        ('Bogura', 'বগুড়া', 120),
        ('Pabna', 'পাবনা', 120),
        ('Sirajganj', 'সিরাজগঞ্জ', 120),
        ('Naogaon', 'নওগাঁ', 120),
        ('Natore', 'নাটোর', 120),
        ('Chapainawabganj', 'চাঁপাইনবাবগঞ্জ', 130),
        ('Joypurhat', 'জয়পুরহাট', 120),
    ],
    'Khulna Division': [
        ('Khulna', 'খুলনা', 120),
        ('Jashore', 'যশোর', 120),
        ('Kushtia', 'কুষ্টিয়া', 120),
        ('Jhenaidah', 'ঝিনাইদহ', 120),
        ('Satkhira', 'সাতক্ষীরা', 130),
        ('Bagerhat', 'বাগেরহাট', 120),
        ('Chuadanga', 'চুয়াডাঙ্গা', 120),
        ('Meherpur', 'মেহেরপুর', 120),
        ('Magura', 'মাগুরা', 120),
        ('Narail', 'নড়াইল', 120),
    ],
    'Barisal Division': [
        ('Barisal', 'বরিশাল', 120),
        ('Patuakhali', 'পটুয়াখালী', 130),
        ('Bhola', 'ভোলা', 130),
        ('Pirojpur', 'পিরোজপুর', 120),
        ('Barguna', 'বরগুনা', 130),
        ('Jhalokathi', 'ঝালকাঠি', 120),
    ],
    'Rangpur Division': [
        ('Rangpur', 'রংপুর', 120),
        ('Dinajpur', 'দিনাজপুর', 130),
        ('Kurigram', 'কুড়িগ্রাম', 130),
        ('Gaibandha', 'গাইবান্ধা', 120),
        ('Nilphamari', 'নীলফামারী', 130),
        ('Lalmonirhat', 'লালমনিরহাট', 130),
        ('Thakurgaon', 'ঠাকুরগাঁও', 140),
        ('Panchagarh', 'পঞ্চগড়', 140),
    ],
    'Mymensingh Division': [
        ('Mymensingh', 'ময়মনসিংহ', 110),
        ('Jamalpur', 'জামালপুর', 120),
        ('Netrokona', 'নেত্রকোণা', 120),
        ('Sherpur', 'শেরপুর', 120),
    ],
}


def get_district_rates(store_settings=None):
    if store_settings is None:
        store_settings = get_cached_settings()
    rates = {}
    fee_dhaka = float(store_settings.get('delivery_fee_dhaka') or 60)
    fee_outside = float(store_settings.get('delivery_fee_outside') or 120)

    for div, d_list in BANGLADESH_DISTRICTS.items():
        for code, bn, default_fee in d_list:
            if code == 'Dhaka':
                rates[code] = fee_dhaka
            else:
                rates[code] = default_fee if default_fee != 120 else fee_outside

    raw_custom = store_settings.get('district_rates')
    if raw_custom:
        try:
            custom_map = json.loads(raw_custom)
            if isinstance(custom_map, dict):
                for k, v in custom_map.items():
                    try:
                        rates[k] = float(v)
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass
    return rates


def get_hero_slides(store_settings=None):
    if store_settings is None:
        store_settings = get_cached_settings()
    raw = store_settings.get('hero_slides')
    if raw:
        try:
            slides = json.loads(raw)
            if isinstance(slides, list) and slides:
                return slides
        except Exception:
            pass
    return [
        {
            'id': 'slide-1',
            'image': 'https://images.unsplash.com/photo-1483985988355-763728e1935b?w=1800',
            'eyebrow': 'NEW SEASON · 2026',
            'title': 'BUILT FOR YOUR CORE.',
            'subtitle': 'Clean silhouettes. Everyday essentials. Designed for modern men.',
            'btn_text': 'SHOP COLLECTION',
            'btn_link': '#shop',
            'active': True,
        },
        {
            'id': 'slide-2',
            'image': '/static/uploads/coreman_denim_cover_new_arrival_HD.png',
            'eyebrow': 'NEW ARRIVAL · 2026',
            'title': 'PREMIUM DENIM COLLECTION.',
            'subtitle': 'Crafted comfort, durable cuts, and effortless modern confidence.',
            'btn_text': 'SHOP COLLECTION',
            'btn_link': '#shop',
            'active': True,
        }
    ]


def save_hero_slides(slides):
    execute_write(
        '''INSERT INTO store_settings (key, value) VALUES (?, ?)
           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value''',
        ('hero_slides', json.dumps(slides)),
    )
    invalidate_settings_cache()


@app.context_processor
def inject_globals():
    cart = session.get('cart', {}) or {}
    item_count = sum(int(qty) for qty in cart.values() if str(qty).isdigit())
    settings = get_cached_settings()
    d_rates = get_district_rates(settings)
    return {
        'cart_count': item_count,
        'store_settings': settings,
        'hero_slides': get_hero_slides(settings),
        'bangladesh_districts': BANGLADESH_DISTRICTS,
        'district_rates': d_rates,
        'district_rates_json': json.dumps(d_rates),
        'is_postgres': is_postgres(),
    }


def cart_items():
    cart = session.get('cart', {}) or {}
    if not cart:
        return [], 0
    rows = []
    total = 0
    for pid, qty in cart.items():
        try:
            pid_int = int(pid)
        except ValueError:
            continue
        product = get_cached_product_by_id(pid_int)
        if product:
            item = dict(product)
            price = float(product['price'])
            item['price'] = price
            item['qty'] = int(qty)
            item['subtotal'] = price * int(qty)
            rows.append(item)
            total += item['subtotal']
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

    smtp_host = os.getenv('SMTP_HOST', '').strip()
    smtp_user = os.getenv('SMTP_USER', '').strip()
    # If unconfigured or using placeholder values, simulate email
    if (
        not smtp_host
        or smtp_host.lower() in {'smtp.example.com', 'example.com', 'localhost', '127.0.0.1'}
        or smtp_user.lower() in {'your-smtp-user', 'user', ''}
    ):
        try:
            print(f'\n--- ORDER EMAIL (simulated) ---\n{subject}\n{body}\n')
        except Exception:
            print(f'\n--- ORDER EMAIL (simulated) #{order_id} to {email} ---\n')
        return True

    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_password = os.getenv('SMTP_PASSWORD')
    sender_email = os.getenv('EMAIL_FROM', 'no-reply@coreman.com')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender_email
    message['To'] = email
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
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
        return 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=900'
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
        checkout_sess = stripe.checkout.Session.create(
            mode='payment',
            line_items=[{
                'price_data': {
                    'currency': 'bdt',
                    'product_data': {'name': f'COREMAN Order #{order_id}'},
                    'unit_amount': int(float(total) * 100),
                },
                'quantity': 1,
            }],
            success_url=request.host_url.rstrip('/') + '/checkout?paid=1',
            cancel_url=request.host_url.rstrip('/') + '/checkout',
            customer_email=email,
            metadata={'order_id': str(order_id), 'name': name, 'phone': phone, 'address': address},
        )
        return checkout_sess.url
    except Exception as exc:
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


# ==========================================
# STOREFRONT ROUTES
# ==========================================

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.png', mimetype='image/png')


@app.route('/k-2-2')
@app.route('/k-2-2/')
def redirect_k_2_2():
    return redirect('/', code=301)


@app.route('/')
def home():
    selected_category = request.args.get('category', '').strip()
    products = get_cached_products()

    # Extract distinct categories preserving order
    categories = ['All']
    seen = set()
    for p in products:
        c = (p.get('category') or '').strip()
        if c and c.lower() not in seen:
            seen.add(c.lower())
            categories.append(c)

    filtered_products = products
    if selected_category and selected_category.lower() != 'all':
        filtered_products = [p for p in products if (p.get('category') or '').strip().lower() == selected_category.lower()]

    return render_template(
        'index.html',
        products=filtered_products,
        all_products=products,
        categories=categories,
        selected_category=selected_category or 'All'
    )


@app.route('/product/<int:pid>')
def product(pid):
    item = get_cached_product_by_id(pid)
    if not item:
        return 'Product not found', 404
    return render_template('product.html', p=item)


@app.post('/cart/add')
def add_cart():
    product_id = str(request.form.get('product_id', ''))
    cart = session.setdefault('cart', {})
    cart[product_id] = cart.get(product_id, 0) + 1
    session.modified = True

    total_count = sum(int(qty) for qty in cart.values() if str(qty).isdigit())

    # If requested via AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.accept_mimetypes.best == 'application/json':
        product = get_cached_product_by_id(int(product_id)) if product_id.isdigit() else None
        return jsonify({
            'success': True,
            'cart_count': total_count,
            'product_name': product['name'] if product else 'Item',
            'product_price': product['price'] if product else 0,
            'product_image': product.get('image', '') if product else '',
        })

    return redirect(request.referrer or url_for('home'))


@app.get('/cart')
def cart():
    items, total = cart_items()
    return render_template('cart.html', items=items, total=total)


@app.post('/cart/update')
def update_cart():
    cart = session.setdefault('cart', {})
    remove_id = request.form.get('remove_id')
    if remove_id:
        cart.pop(str(remove_id), None)

    for key, value in request.form.items():
        if key.startswith('qty_'):
            product_id = key[4:]
            try:
                qty = max(0, int(value))
            except ValueError:
                qty = 0
            if qty > 0:
                cart[product_id] = qty
            else:
                cart.pop(product_id, None)
    session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.accept_mimetypes.best == 'application/json':
        items, total = cart_items()
        return jsonify({
            'success': True,
            'cart_count': sum(int(qty) for qty in cart.values() if str(qty).isdigit()),
            'total': total,
            'items': items,
        })

    return redirect(url_for('cart'))


@app.post('/cart/remove/<product_id>')
def remove_cart_item(product_id):
    cart = session.setdefault('cart', {})
    cart.pop(str(product_id), None)
    session.modified = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or request.accept_mimetypes.best == 'application/json':
        items, total = cart_items()
        return jsonify({
            'success': True,
            'cart_count': sum(int(qty) for qty in cart.values() if str(qty).isdigit()),
            'total': total,
            'items': items,
        })

    return redirect(url_for('cart'))


@app.get('/checkout')
def checkout():
    items, total = cart_items()
    if not items:
        return redirect(url_for('home'))

    store_settings = get_cached_settings()
    threshold = float(store_settings.get('free_shipping_threshold') or 3000)
    d_rates = get_district_rates(store_settings)
    fee_dhaka = float(d_rates.get('Dhaka', 60))

    # Initial default is Dhaka
    initial_fee = 0.0 if total >= threshold else fee_dhaka
    initial_grand_total = total + initial_fee

    return render_template(
        'checkout.html',
        items=items,
        total=total,
        initial_fee=initial_fee,
        initial_grand_total=initial_grand_total,
        cod_only=COD_ONLY
    )


@app.post('/checkout')
def place_order():
    items, total = cart_items()
    if not items:
        return redirect(url_for('home'))

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    district = request.form.get('district', 'Dhaka').strip()
    method = request.form.get('payment_method', 'Cash on Delivery')

    if COD_ONLY and method != 'Cash on Delivery':
        flash('Online payment is not available yet. Please choose Cash on Delivery.', 'error')
        return redirect(url_for('checkout'))

    # Calculate delivery charge based on district rates
    store_settings = get_cached_settings()
    threshold = float(store_settings.get('free_shipping_threshold') or 3000)
    d_rates = get_district_rates(store_settings)

    is_dhaka = district.lower() == 'dhaka'
    assigned_fee = float(d_rates.get(district, 120 if not is_dhaka else 60))

    if is_dhaka and total >= threshold:
        delivery_fee = 0.0
    else:
        delivery_fee = assigned_fee

    # Grand total includes items subtotal + delivery fee!
    grand_total = total + delivery_fee
    delivery_eta = '1-2 Days (Dhaka Metro)' if is_dhaka else f'3-5 Days ({district})'
    full_shipping_destination = f"{address}, {district}"

    db_inst = get_db()
    try:
        order_id = db_inst.execute_insert(
            '''INSERT INTO orders (name, email, phone, address, total, payment_method, payment_status, status, estimated_delivery, district, delivery_fee)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (name, email, phone, full_shipping_destination, grand_total, method, 'Pending', 'Pending', delivery_eta, district, delivery_fee)
        )
        db_inst.commit()

        for item in items:
            p_row = get_cached_product_by_id(item['id'])
            p_img = (p_row.get('image') if p_row else '') or item.get('image') or ''
            db_inst.execute(
                '''INSERT INTO order_items (order_id, product_id, name, qty, price, image)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (order_id, item['id'], item['name'], item['qty'], item['price'], p_img)
            )
            # Decrement stock count safely for both PostgreSQL and SQLite
            if db_inst.is_pg:
                db_inst.execute(
                    '''UPDATE products SET stock = GREATEST(0, stock - ?) WHERE id = ?''',
                    (item['qty'], item['id'])
                )
            else:
                db_inst.execute(
                    '''UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?''',
                    (item['qty'], item['id'])
                )
        db_inst.commit()
        invalidate_products_cache()
    except Exception as e:
        db_inst.rollback()
        raise e
    finally:
        db_inst.close()

    session['cart'] = {}
    session.modified = True

    live_payment_url = None
    if method.lower() in {'card / online payment', 'online payment', 'stripe'}:
        live_payment_url = stripe_checkout_session(order_id, grand_total, email, name, phone, full_shipping_destination)

    if email:
        try:
            send_order_email(email, order_id, grand_total, method, delivery_eta, full_shipping_destination)
        except Exception as exc:
            print(f"Order confirmation email warning: {exc}")

    if live_payment_url:
        return redirect(live_payment_url)

    return render_template(
        'success.html',
        order_id=order_id,
        total=grand_total,
        subtotal=total,
        delivery_fee=delivery_fee,
        district=district,
        method=method,
        email=email,
        estimated_delivery=delivery_eta,
        address=full_shipping_destination,
    )


# ==========================================
# ADMIN AUTHENTICATION
# ==========================================

@app.get('/dingidingi/admin/login')
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')


@app.post('/dingidingi/admin/login')
def admin_login_submit():
    client_ip = request.remote_addr or 'unknown'
    allowed, wait_sec = check_rate_limit(client_ip)
    if not allowed:
        flash(f'Too many failed attempts. Please wait {wait_sec} seconds before trying again.', 'error')
        return redirect(url_for('admin_login'))

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    admin_row = query_one('SELECT * FROM admin_users WHERE username = ?', (username,))

    is_valid = False
    if admin_row and check_password_hash(admin_row['password_hash'], password):
        is_valid = True
    elif (username == os.getenv('COREMAN_ADMIN_USERNAME', 'admin') and
          password == os.getenv('COREMAN_ADMIN_PASSWORD', 'Coreman@Admin#2026')):
        is_valid = True

    if is_valid:
        reset_failed_attempts(client_ip)
        session.regenerate() if hasattr(session, 'regenerate') else None
        session['admin_logged_in'] = True
        session['admin_username'] = username
        flash('Welcome back! Logged in to COREMAN Admin Suite.', 'success')
        return redirect(url_for('admin_dashboard'))

    record_failed_attempt(client_ip)
    flash('Invalid admin credentials. Please verify username and password.', 'error')
    return redirect(url_for('admin_login'))


@app.get('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('You have been logged out securely.', 'success')
    return redirect(url_for('admin_login'))


# ==========================================
# ADMIN SUITE & DASHBOARD
# ==========================================

@app.get('/admin')
@app.get('/admin/dashboard')
@app.get('/admin/orders')
@admin_required
def admin_dashboard():
    # Fetch orders
    orders_raw = query_all('SELECT * FROM orders ORDER BY id DESC')
    order_items_raw = query_all('''
        SELECT oi.*, 
               COALESCE(NULLIF(oi.image, ''), p.image, '/static/uploads/default-classic-black-tee.svg') as image,
               COALESCE(p.category, 'Apparel') as category,
               COALESCE(p.stock, 0) as stock,
               COALESCE(p.description, '') as description
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        ORDER BY oi.id ASC
    ''')
    items_by_order = {}
    for it in order_items_raw:
        it_dict = dict(it)
        it_dict['price'] = float(it_dict['price'])
        if not it_dict.get('image'):
            it_dict['image'] = '/static/uploads/default-classic-black-tee.svg'
        items_by_order.setdefault(it_dict['order_id'], []).append(it_dict)

    orders = []
    total_revenue = 0.0
    pending_orders = 0
    status_counts = {'Pending': 0, 'Processing': 0, 'Packed': 0, 'Shipped': 0, 'Delivered': 0, 'Cancelled': 0}

    for o in orders_raw:
        o_dict = dict(o)
        o_dict['total'] = float(o_dict['total'])
        raw_dt = o_dict.get('created_at')
        if hasattr(raw_dt, 'strftime'):
            o_dict['created_date'] = raw_dt.strftime('%d %b %Y')
            o_dict['created_at'] = raw_dt.strftime('%Y-%m-%d %H:%M')
        else:
            o_dict['created_date'] = str(raw_dt or '')[:10]
            o_dict['created_at'] = str(raw_dt or '')
        o_dict['items'] = items_by_order.get(o_dict['id'], [])
        o_dict['order_items'] = o_dict['items']
        orders.append(o_dict)

        st = o_dict.get('status') or 'Pending'
        status_counts[st] = status_counts.get(st, 0) + 1
        if st == 'Pending':
            pending_orders += 1
        if st != 'Cancelled':
            total_revenue += o_dict['total']

    # Fetch products
    products_raw = query_all('SELECT * FROM products ORDER BY id ASC')
    products = []
    low_stock_items = []
    categories_set = set()

    for p in products_raw:
        p_dict = dict(p)
        p_dict['price'] = float(p_dict['price'])
        p_dict['stock'] = int(p_dict.get('stock') or 0)
        products.append(p_dict)
        if p_dict.get('category'):
            categories_set.add(p_dict['category'])
        if p_dict['stock'] <= 15:
            low_stock_items.append(p_dict)

    # Aggregated Customers
    cust_map = {}
    for o in orders:
        key = o.get('phone') or o.get('email') or o.get('name')
        if not key:
            continue
        if key not in cust_map:
            cust_map[key] = {
                'name': o.get('name'),
                'phone': o.get('phone'),
                'email': o.get('email'),
                'address': o.get('address'),
                'order_count': 0,
                'total_spent': 0.0,
                'last_order': o.get('created_date') or '',
            }
        cust_map[key]['order_count'] += 1
        cust_map[key]['total_spent'] += o['total']

    customers = sorted(cust_map.values(), key=lambda x: x['total_spent'], reverse=True)

    # Store Settings
    settings_rows = query_all('SELECT key, value FROM store_settings')
    settings = {r['key']: r['value'] for r in settings_rows}

    total_orders = len(orders)
    aov = (total_revenue / total_orders) if total_orders > 0 else 0.0

    stats = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_products': len(products),
        'low_stock_count': len(low_stock_items),
        'total_customers': len(customers),
        'aov': aov,
        'status_breakdown': status_counts,
    }

    return render_template(
        'admin.html',
        stats=stats,
        recent_orders=orders[:6],
        orders=orders,
        products=products,
        categories=sorted(list(categories_set)),
        low_stock_items=low_stock_items,
        customers=customers,
        settings=settings,
        admin_user=session.get('admin_username') or os.getenv('COREMAN_ADMIN_USERNAME', 'admin'),
        is_postgres=is_postgres(),
    )


# ==========================================
# ADMIN ORDER ACTIONS
# ==========================================

@app.get('/admin/api/orders-feed')
@admin_required
def admin_orders_feed():
    orders_raw = query_all('SELECT * FROM orders ORDER BY id DESC')
    order_items_raw = query_all('''
        SELECT oi.*, 
               COALESCE(NULLIF(oi.image, ''), p.image, '/static/uploads/default-classic-black-tee.svg') as image,
               COALESCE(p.category, 'Apparel') as category,
               COALESCE(p.stock, 0) as stock,
               COALESCE(p.description, '') as description
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        ORDER BY oi.id ASC
    ''')
    items_by_order = {}
    for it in order_items_raw:
        it_dict = dict(it)
        it_dict['price'] = float(it_dict['price'])
        if not it_dict.get('image'):
            it_dict['image'] = '/static/uploads/default-classic-black-tee.svg'
        items_by_order.setdefault(it_dict['order_id'], []).append(it_dict)

    orders = []
    total_revenue = 0.0
    pending_orders = 0
    status_counts = {'Pending': 0, 'Processing': 0, 'Packed': 0, 'Shipped': 0, 'Delivered': 0, 'Cancelled': 0}

    for o in orders_raw:
        o_dict = dict(o)
        o_dict['total'] = float(o_dict['total'])
        raw_dt = o_dict.get('created_at')
        if hasattr(raw_dt, 'strftime'):
            o_dict['created_date'] = raw_dt.strftime('%d %b %Y')
            o_dict['created_at'] = raw_dt.strftime('%Y-%m-%d %H:%M')
        else:
            o_dict['created_date'] = str(raw_dt or '')[:10]
            o_dict['created_at'] = str(raw_dt or '')
        o_dict['items'] = items_by_order.get(o_dict['id'], [])
        o_dict['order_items'] = o_dict['items']
        orders.append(o_dict)

        st = o_dict.get('status') or 'Pending'
        status_counts[st] = status_counts.get(st, 0) + 1
        if st == 'Pending':
            pending_orders += 1
        if st != 'Cancelled':
            total_revenue += o_dict['total']

    latest_id = orders[0]['id'] if orders else 0
    total_orders = len(orders)
    aov = (total_revenue / total_orders) if total_orders > 0 else 0.0

    return jsonify({
        'latest_id': latest_id,
        'total_orders': total_orders,
        'orders': orders,
        'stats': {
            'total_revenue': total_revenue,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'aov': aov,
            'status_breakdown': status_counts,
        }
    })


@app.get('/admin/orders/<int:order_id>/json')
@admin_required
def admin_order_json(order_id):
    order = query_one('SELECT * FROM orders WHERE id = ?', (order_id,))
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    order_dict = dict(order)
    order_dict['total'] = float(order_dict['total'])
    order_dict['created_at'] = str(order_dict.get('created_at') or '')

    items_raw = query_all('''
        SELECT oi.*, 
               COALESCE(NULLIF(oi.image, ''), p.image, '/static/uploads/default-classic-black-tee.svg') as image,
               COALESCE(p.category, 'Apparel') as category,
               COALESCE(p.stock, 0) as stock,
               COALESCE(p.description, '') as description
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
        ORDER BY oi.id ASC
    ''', (order_id,))
    items = []
    for it in items_raw:
        it_dict = dict(it)
        it_dict['price'] = float(it_dict['price'])
        if not it_dict.get('image'):
            it_dict['image'] = '/static/uploads/default-classic-black-tee.svg'
        items.append(it_dict)

    return jsonify({'order': order_dict, 'items': items})


@app.post('/admin/orders/<int:order_id>/update')
@admin_required
def update_order(order_id):
    status = request.form.get('status', 'Pending')
    payment_status = request.form.get('payment_status', 'Pending')

    if status == 'Cancelled':
        payment_status = 'Cancelled'

    execute_write(
        'UPDATE orders SET status = ?, payment_status = ? WHERE id = ?',
        (status, payment_status, order_id),
    )
    flash(f'Order #{order_id} status updated to {status} ({payment_status}).', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=orders')


@app.post('/admin/orders/<int:order_id>/delete')
@admin_required
def delete_order(order_id):
    execute_write('DELETE FROM order_items WHERE order_id = ?', (order_id,))
    execute_write('DELETE FROM orders WHERE id = ?', (order_id,))
    flash(f'Order #{order_id} was deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=orders')


@app.post('/admin/orders/clear-all')
@admin_required
def clear_all_orders():
    execute_write('DELETE FROM order_items')
    execute_write('DELETE FROM orders')
    flash('All orders have been deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=orders')


@app.get('/admin/orders/<int:order_id>/invoice')
@admin_required
def order_invoice(order_id):
    order = query_one('SELECT * FROM orders WHERE id = ?', (order_id,))
    if not order:
        return 'Order not found', 404
    order_dict = dict(order)
    order_dict['total'] = float(order_dict['total'])
    order_dict['created_at'] = str(order_dict.get('created_at') or '')

    items_raw = query_all('SELECT * FROM order_items WHERE order_id = ?', (order_id,))
    items = []
    for it in items_raw:
        it_dict = dict(it)
        it_dict['price'] = float(it_dict['price'])
        items.append(it_dict)

    return render_template('invoice.html', order=order_dict, items=items)


# ==========================================
# ADMIN PRODUCT ACTIONS
# ==========================================

@app.post('/admin/products/add')
@admin_required
def add_product():
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    price = request.form.get('price', '0')
    stock = request.form.get('stock', '50')
    description = request.form.get('description', '').strip()
    is_featured = bool(int(request.form.get('is_featured', '1')))
    image_url = request.form.get('image_url', '').strip()
    uploaded_image = request.files.get('image')

    image = save_uploaded_image(uploaded_image) or normalize_image_url(image_url)

    if not name or not category:
        flash('Product name and category are required.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=products')

    try:
        price_val = float(price)
        stock_val = int(stock)
    except ValueError:
        flash('Price and stock must be valid numbers.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=products')

    db_inst = get_db()
    try:
        db_inst.execute_insert(
            '''INSERT INTO products (name, category, price, stock, description, image, is_featured)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (name, category, price_val, stock_val, description, image, is_featured)
        )
        db_inst.commit()
        invalidate_products_cache()
        flash(f'Product "{name}" added successfully to {category}.', 'success')
    finally:
        db_inst.close()

    return redirect(url_for('admin_dashboard') + '?tab=products')


@app.post('/admin/products/<int:product_id>/update')
@admin_required
def update_product(product_id):
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    price = request.form.get('price', '0')
    stock = request.form.get('stock', '50')
    description = request.form.get('description', '').strip()
    is_featured = bool(int(request.form.get('is_featured', '1')))
    image_url = request.form.get('image_url', '').strip()
    uploaded_image = request.files.get('image')

    try:
        price_val = float(price)
        stock_val = int(stock)
    except ValueError:
        flash('Price and stock must be numeric.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=products')

    current_prod = query_one('SELECT * FROM products WHERE id = ?', (product_id,))
    if not current_prod:
        flash('Product not found.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=products')

    new_img = save_uploaded_image(uploaded_image)
    if not new_img:
        new_img = image_url or current_prod.get('image')

    execute_write(
        '''UPDATE products
           SET name = ?, category = ?, price = ?, stock = ?, description = ?, image = ?, is_featured = ?
           WHERE id = ?''',
        (name or current_prod['name'],
         category or current_prod['category'],
         price_val,
         stock_val,
         description,
         new_img,
         is_featured,
         product_id),
    )
    invalidate_products_cache()
    flash(f'Product #{product_id} updated successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=products')


@app.post('/admin/products/<int:product_id>/delete')
@admin_required
def delete_product(product_id):
    execute_write('DELETE FROM products WHERE id = ?', (product_id,))
    invalidate_products_cache()
    flash(f'Product #{product_id} deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=products')


# ==========================================
# ADMIN SETTINGS & SECURITY ACTIONS
# ==========================================

@app.post('/admin/settings/password')
@admin_required
def change_admin_password():
    current_pass = request.form.get('current_password', '')
    new_pass = request.form.get('new_password', '')
    confirm_pass = request.form.get('confirm_password', '')

    if new_pass != confirm_pass:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=settings')

    if len(new_pass) < 6:
        flash('New password must be at least 6 characters.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=settings')

    admin_username = session.get('admin_username') or os.getenv('COREMAN_ADMIN_USERNAME', 'admin')
    admin_row = query_one('SELECT * FROM admin_users WHERE username = ?', (admin_username,))

    is_current_valid = False
    if admin_row and check_password_hash(admin_row['password_hash'], current_pass):
        is_current_valid = True
    elif current_pass == os.getenv('COREMAN_ADMIN_PASSWORD', 'Coreman@Admin#2026'):
        is_current_valid = True

    if not is_current_valid:
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=settings')

    new_hash = generate_password_hash(new_pass, method='scrypt')
    execute_write('UPDATE admin_users SET password_hash = ? WHERE username = ?', (new_hash, admin_username))
    flash('Admin password changed successfully! Please keep it secure.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=settings')


@app.post('/admin/settings/update')
@admin_required
def update_store_settings():
    fields = [
        'store_name',
        'currency',
        'delivery_fee_dhaka',
        'delivery_fee_outside',
        'free_shipping_threshold',
        'contact_phone',
        'contact_email',
        'announcement',
    ]
    for field in fields:
        val = request.form.get(field, '').strip()
        execute_write(
            '''INSERT INTO store_settings (key, value) VALUES (?, ?)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value''',
            (field, val),
        )

    # Process all district-specific rates from form
    district_rates = {}
    for key, val in request.form.items():
        if key.startswith('dist_rate_'):
            d_name = key[len('dist_rate_'):]
            try:
                district_rates[d_name] = float(val)
            except (ValueError, TypeError):
                pass

    if district_rates:
        execute_write(
            '''INSERT INTO store_settings (key, value) VALUES (?, ?)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value''',
            ('district_rates', json.dumps(district_rates)),
        )

    invalidate_settings_cache()
    flash('Storefront configuration and delivery charges saved successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=settings')


@app.post('/admin/settings/districts')
@admin_required
def update_district_rates():
    district_rates = {}
    for key, val in request.form.items():
        if key.startswith('dist_rate_'):
            d_name = key[len('dist_rate_'):]
            try:
                district_rates[d_name] = float(val)
            except (ValueError, TypeError):
                pass

    # Also update base fees if provided
    base_dhaka = request.form.get('delivery_fee_dhaka')
    base_outside = request.form.get('delivery_fee_outside')
    if base_dhaka:
        execute_write(
            '''INSERT INTO store_settings (key, value) VALUES (?, ?)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value''',
            ('delivery_fee_dhaka', base_dhaka.strip()),
        )
    if base_outside:
        execute_write(
            '''INSERT INTO store_settings (key, value) VALUES (?, ?)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value''',
            ('delivery_fee_outside', base_outside.strip()),
        )

    execute_write(
        '''INSERT INTO store_settings (key, value) VALUES (?, ?)
           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value''',
        ('district_rates', json.dumps(district_rates)),
    )
    invalidate_settings_cache()
    flash('District delivery charges updated successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=settings')


# ==========================================
# ADMIN HERO SLIDER ACTIONS
# ==========================================

@app.post('/admin/hero/add')
@admin_required
def admin_hero_add():
    slides = get_hero_slides()
    uploaded_files = request.files.getlist('slide_images')
    image_url = request.form.get('image_url', '').strip()
    eyebrow = request.form.get('eyebrow', 'NEW SEASON · 2026').strip()
    title = request.form.get('title', 'BUILT FOR YOUR CORE.').strip()
    subtitle = request.form.get('subtitle', 'Clean silhouettes. Everyday essentials. Designed for modern men.').strip()
    btn_text = request.form.get('btn_text', 'SHOP COLLECTION').strip()
    btn_link = request.form.get('btn_link', '#shop').strip()

    added_count = 0

    # Process all uploaded image files (supports multiple selection!)
    for f in uploaded_files:
        if f and getattr(f, 'filename', None):
            saved_path = save_uploaded_image(f)
            if saved_path:
                slide_id = f"slide-{uuid.uuid4().hex[:8]}"
                slides.append({
                    'id': slide_id,
                    'image': saved_path,
                    'eyebrow': eyebrow,
                    'title': title,
                    'subtitle': subtitle,
                    'btn_text': btn_text,
                    'btn_link': btn_link,
                    'active': True,
                })
                added_count += 1

    # Also handle single image URL if provided and no file was uploaded
    if image_url and added_count == 0:
        slide_id = f"slide-{uuid.uuid4().hex[:8]}"
        slides.append({
            'id': slide_id,
            'image': image_url,
            'eyebrow': eyebrow,
            'title': title,
            'subtitle': subtitle,
            'btn_text': btn_text,
            'btn_link': btn_link,
            'active': True,
        })
        added_count += 1

    if added_count > 0:
        save_hero_slides(slides)
        flash(f'Successfully added {added_count} slide(s) to the hero slider.', 'success')
    else:
        flash('No valid image was uploaded or provided.', 'error')

    return redirect(url_for('admin_dashboard') + '?tab=hero')


@app.post('/admin/hero/<slide_id>/update')
@admin_required
def admin_hero_update(slide_id):
    slides = get_hero_slides()
    slide = next((s for s in slides if str(s.get('id')) == str(slide_id)), None)
    if not slide:
        flash('Slide not found.', 'error')
        return redirect(url_for('admin_dashboard') + '?tab=hero')

    uploaded_file = request.files.get('slide_image')
    image_url = request.form.get('image_url', '').strip()
    if uploaded_file and getattr(uploaded_file, 'filename', None):
        saved = save_uploaded_image(uploaded_file)
        if saved:
            slide['image'] = saved
    elif image_url:
        slide['image'] = image_url

    slide['eyebrow'] = request.form.get('eyebrow', slide.get('eyebrow', '')).strip()
    slide['title'] = request.form.get('title', slide.get('title', '')).strip()
    slide['subtitle'] = request.form.get('subtitle', slide.get('subtitle', '')).strip()
    slide['btn_text'] = request.form.get('btn_text', slide.get('btn_text', '')).strip()
    slide['btn_link'] = request.form.get('btn_link', slide.get('btn_link', '#shop')).strip()

    save_hero_slides(slides)
    flash(f'Slide "{slide.get("title")}" updated successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=hero')


@app.post('/admin/hero/<slide_id>/delete')
@admin_required
def admin_hero_delete(slide_id):
    slides = get_hero_slides()
    new_slides = [s for s in slides if str(s.get('id')) != str(slide_id)]
    if len(new_slides) < len(slides):
        save_hero_slides(new_slides)
        flash('Slide removed successfully.', 'success')
    else:
        flash('Slide not found.', 'error')
    return redirect(url_for('admin_dashboard') + '?tab=hero')


@app.post('/admin/hero/<slide_id>/toggle')
@admin_required
def admin_hero_toggle(slide_id):
    slides = get_hero_slides()
    slide = next((s for s in slides if str(s.get('id')) == str(slide_id)), None)
    if slide:
        slide['active'] = not slide.get('active', True)
        save_hero_slides(slides)
        status_text = 'activated' if slide['active'] else 'hidden'
        flash(f'Slide {status_text} successfully.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=hero')


@app.post('/admin/hero/<slide_id>/move')
@admin_required
def admin_hero_move(slide_id):
    slides = get_hero_slides()
    idx = next((i for i, s in enumerate(slides) if str(s.get('id')) == str(slide_id)), -1)
    direction = request.form.get('direction', 'up')
    if idx != -1:
        if direction == 'up' and idx > 0:
            slides[idx], slides[idx - 1] = slides[idx - 1], slides[idx]
            save_hero_slides(slides)
        elif direction == 'down' and idx < len(slides) - 1:
            slides[idx], slides[idx + 1] = slides[idx + 1], slides[idx]
            save_hero_slides(slides)
    return redirect(url_for('admin_dashboard') + '?tab=hero')


@app.post('/admin/hero/settings')
@admin_required
def admin_hero_settings():
    speed = request.form.get('hero_autoplay_speed', '5000').strip()
    execute_write(
        '''INSERT INTO store_settings (key, value) VALUES (?, ?)
           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value''',
        ('hero_autoplay_speed', speed),
    )
    invalidate_settings_cache()
    flash('Hero slider autoplay settings saved.', 'success')
    return redirect(url_for('admin_dashboard') + '?tab=hero')


# ==========================================
# PUBLIC API
# ==========================================

@app.get('/api/products')
def api_products():
    return jsonify(get_cached_products())


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
