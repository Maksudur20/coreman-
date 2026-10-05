import io
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
    login = client.post('/dingidingi/admin/login', data={'username': 'admin', 'password': 'Coreman@2026!'}, follow_redirects=False)
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
