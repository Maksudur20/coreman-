# COREMAN Full-Stack E-commerce

A runnable Flask + SQLite fashion storefront inspired by the visual structure of the referenced site, with COREMAN branding.

## Included
- Responsive storefront
- Product catalogue stored in SQLite
- Add/update cart
- Checkout form
- Order + order-items database tables
- Order admin page at `/admin/orders`
- JSON product API at `/api/products`
- Payment-method selection and a clear gateway integration hook

## Run on Windows
```powershell
cd coreman_project
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```
Open http://127.0.0.1:5000

## Free hosting on PythonAnywhere

The Beginner plan provides one public Python web app and persistent file storage. Its published limits include 100 CPU-seconds per day, 512 MB storage, low bandwidth, and restricted outbound internet. It may suit a small COD-only shop, but it does not provide an uptime SLA; SMTP and live payment integrations are not included in this free setup.

1. Create a free Beginner account at PythonAnywhere and add a web app using Manual Configuration with Python 3.13.
2. Upload and extract a clean project archive into `/home/YOURUSERNAME/coreman_project`.
3. Create a private `.env` file in that directory with a generated `SECRET_KEY`, unique `COREMAN_ADMIN_USERNAME`, strong `COREMAN_ADMIN_PASSWORD`, and `COREMAN_COD_ONLY=true`. Never put these values in GitHub.
4. In the web app's WSGI configuration, set the project path and import the app like this, replacing `YOURUSERNAME`:

```python
import os
import sys

project_home = '/home/YOURUSERNAME/coreman_project'
if project_home not in sys.path:
	sys.path.insert(0, project_home)

os.environ['COREMAN_PRODUCTION'] = 'true'
from app import app as application
```

5. Set the web app's virtualenv to one with the packages in `requirements.txt`, then reload it from the Web tab.

The database and uploaded images stay in your PythonAnywhere home directory. The local database and uploaded images are deliberately excluded from the deploy archive; the app starts with its six built-in products. Keep image uploads small to stay within the free storage limit.

## Deploy on Render

1. Create or use a dedicated GitHub repository with this project folder as its root. Do not push the parent-directory repository, or commit `.env` or `coreman.db`.
2. In Render, create a Blueprint and connect the repository containing `render.yaml`.
3. Enter a unique admin username and strong password when prompted, review the paid web-service and persistent-disk charges, then create the service.
4. The service stores SQLite data and uploaded product images under `/var/data`. A new deployment starts with the six built-in products; the local `coreman.db`, orders, and uploaded images are not copied automatically.
5. Add your SMTP settings to the service's environment variables to enable order emails. Until a payment provider and its verified callbacks are configured, checkout is intentionally limited to Cash on Delivery.

The Render Blueprint uses a paid web service because Render only supports persistent disks on paid services. Creating the service starts billing; adding `render.yaml` to the repository does not.

## Real payment
A real payment gateway cannot be made live from source code alone. You must create a merchant account and add the provider's credentials. The checkout route contains the integration hook. For Bangladesh, connect bKash/SSLCOMMERZ using their current merchant API credentials and callback/webhook flow. Never commit live secrets to GitHub.
