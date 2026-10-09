import io
import os
import uuid

from app import app


def test_admin_requires_login():
    client = app.test_client()
    response = client.get('/admin', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/dingidingi/admin/login')


def test_login_page_loads():
    client = app.test_client()
    response = client.get('/dingidingi/admin/login')
    assert response.status_code == 200
    assert b'Admin Portal' in response.data or b'Admin Login' in response.data


def test_checkout_order_success_flow():
    client = app.test_client()
    client.get('/')
    response = client.post('/cart/add', data={'product_id': '1'}, follow_redirects=False)
    assert response.status_code == 302

    checkout = client.post('/checkout', data={
        'name': 'Test User',
        'email': 'test@example.com',
        'phone': '01700000000',
        'address': 'Dhaka, Bangladesh',
        'payment_method': 'Cash on Delivery'
    }, follow_redirects=True)
    assert checkout.status_code == 200
    assert b'ORDER CONFIRMED' in checkout.data
    assert b'Dhaka' in checkout.data or b'3-4 days' in checkout.data


def test_admin_can_upload_product_image():
    client = app.test_client()
    admin_pass = os.getenv('COREMAN_ADMIN_PASSWORD', 'Coreman@Admin#2026')
    login = client.post('/dingidingi/admin/login', data={'username': 'admin', 'password': admin_pass}, follow_redirects=False)
    assert login.status_code == 302

    image = io.BytesIO(b'fake-image-content')
    product_name = f'Uploaded Test Tee {uuid.uuid4().hex[:6]}'
    response = client.post('/admin/products/add', data={
        'name': product_name,
        'category': 'T-Shirts',
        'price': '999',
        'image': (image, 'uploaded-test-tee.png')
    }, follow_redirects=False)
    assert response.status_code == 302

    products = client.get('/api/products').get_json()
    uploaded = next((p for p in products if p['name'] == product_name), None)
    assert uploaded is not None
    assert uploaded['image'].startswith('/static/uploads/')


def test_delivery_fee_single_item_inside_dhaka():
    client = app.test_client()
    # Clear cart first
    with client.session_transaction() as sess:
        sess['cart'] = {'1': 1}  # 1 product (৳890)

    checkout_page = client.get('/checkout')
    assert checkout_page.status_code == 200
    assert b'80' in checkout_page.data

    order = client.post('/checkout', data={
        'name': 'Dhaka User',
        'email': 'dhaka@example.com',
        'phone': '01711111111',
        'address': 'Dhanmondi, Dhaka',
        'district': 'Dhaka',
        'delivery_zone': 'dhaka',
        'payment_method': 'Cash on Delivery'
    }, follow_redirects=True)
    assert order.status_code == 200
    # Subtotal 890 + Inside Dhaka fee 80 = 970
    assert b'970' in order.data


def test_delivery_fee_single_item_outside_dhaka():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['cart'] = {'1': 1}  # 1 product (৳890)

    order = client.post('/checkout', data={
        'name': 'Chittagong User',
        'email': 'ctg@example.com',
        'phone': '01811111111',
        'address': 'GEC Circle',
        'district': 'Chittagong',
        'delivery_zone': 'outside',
        'payment_method': 'Cash on Delivery'
    }, follow_redirects=True)
    assert order.status_code == 200
    # Subtotal 890 + Outside Dhaka fee 130 = 1020
    assert b'1020' in order.data


def test_combo_offer_free_delivery():
    client = app.test_client()
    # 2 products = Combo Offer Free Delivery
    with client.session_transaction() as sess:
        sess['cart'] = {'1': 2}  # 2 units (2 * 890 = 1780)

    checkout_page = client.get('/checkout')
    assert checkout_page.status_code == 200
    assert b'FREE' in checkout_page.data

    # Even outside Dhaka, delivery fee should be 0 (Free Delivery)
    order = client.post('/checkout', data={
        'name': 'Combo User Outside Dhaka',
        'email': 'combo@example.com',
        'phone': '01911111111',
        'address': 'Zindabazar, Sylhet',
        'district': 'Sylhet',
        'delivery_zone': 'outside',
        'payment_method': 'Cash on Delivery'
    }, follow_redirects=True)
    assert order.status_code == 200
    # Grand total should be exactly 1780 with 0 delivery charge!
    assert b'1780' in order.data


def test_main_page_displays_combo_offer():
    client = app.test_client()
    res = client.get('/')
    assert res.status_code == 200
    # Confirm announcement bar features the combo offer and clean home page
    assert b'COMBO OFFER' in res.data or b'free' in res.data.lower()


def test_meta_pixel_configuration_and_rendering():
    from database import execute_write, invalidate_settings_cache
    client = app.test_client()

    # Configure a test Pixel ID
    test_pixel = '987654321098765'
    execute_write("INSERT OR REPLACE INTO store_settings (key, value) VALUES ('meta_pixel_id', ?)", (test_pixel,))
    invalidate_settings_cache()

    # Base page should include Meta Pixel script and PageView
    res = client.get('/')
    assert res.status_code == 200
    assert test_pixel.encode() in res.data
    assert b'connect.facebook.net' in res.data
    assert b"fbq('track', 'PageView')" in res.data

    # Product page should include ViewContent
    res_prod = client.get('/product/1')
    assert res_prod.status_code == 200
    assert b"'ViewContent'" in res_prod.data

    # Clean up setting
    execute_write("INSERT OR REPLACE INTO store_settings (key, value) VALUES ('meta_pixel_id', '')")
    invalidate_settings_cache()

    res_clean = client.get('/')
    assert test_pixel.encode() not in res_clean.data


def test_cookie_lifetime_is_one_year():
    from datetime import timedelta
    assert app.config['PERMANENT_SESSION_LIFETIME'] == timedelta(days=365)
    client = app.test_client()
    res = client.post('/cart/add', data={'product_id': '1'})
    cookie_header = res.headers.get('Set-Cookie')
    assert cookie_header is not None
    assert 'Expires=' in cookie_header or 'Max-Age=' in cookie_header


def test_advanced_tracking_features():
    from app import sha256_hash, normalize_bd_phone
    from database import execute_write, invalidate_settings_cache
    client = app.test_client()

    # 1. EMQ Enricher functions
    assert normalize_bd_phone('01711-223344') == '+8801711223344'
    assert sha256_hash('test@example.com') is not None
    assert len(sha256_hash('test@example.com')) == 64

    # 2. Click ID Restorer & Cookie Keeper (_fbc)
    res = client.get('/?fbclid=IwAR0FakeClickID123')
    assert res.status_code == 200
    cookie_header = res.headers.get('Set-Cookie', '')
    assert '_fbc=' in cookie_header
    assert 'IwAR0FakeClickID123' in cookie_header

    # 3. Bot Detection & Filtering
    execute_write("INSERT OR REPLACE INTO store_settings (key, value) VALUES ('meta_pixel_id', '111222333444555')")
    invalidate_settings_cache()

    # Normal user gets pixel
    res_user = client.get('/', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    assert b'111222333444555' in res_user.data

    # Bot does NOT get pixel
    res_bot = client.get('/', headers={'User-Agent': 'Googlebot/2.1 (+http://www.google.com/bot.html)'})
    assert b'111222333444555' not in res_bot.data

    # Clean up setting
    execute_write("INSERT OR REPLACE INTO store_settings (key, value) VALUES ('meta_pixel_id', '')")
    invalidate_settings_cache()

