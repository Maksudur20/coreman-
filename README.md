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

## Deploy on Render

1. Create or use a dedicated GitHub repository with this project folder as its root. Do not push the parent-directory repository, or commit `.env` or `coreman.db`.
2. In Render, create a Blueprint and connect the repository containing `render.yaml`.
3. Enter a unique admin username and strong password when prompted, review the paid web-service and persistent-disk charges, then create the service.
4. The service stores SQLite data and uploaded product images under `/var/data`. A new deployment starts with the six built-in products; the local `coreman.db`, orders, and uploaded images are not copied automatically.
5. Add your SMTP settings to the service's environment variables to enable order emails. Until a payment provider and its verified callbacks are configured, checkout is intentionally limited to Cash on Delivery.

The Render Blueprint uses a paid web service because Render only supports persistent disks on paid services. Creating the service starts billing; adding `render.yaml` to the repository does not.

## Real payment
A real payment gateway cannot be made live from source code alone. You must create a merchant account and add the provider's credentials. The checkout route contains the integration hook. For Bangladesh, connect bKash/SSLCOMMERZ using their current merchant API credentials and callback/webhook flow. Never commit live secrets to GitHub.
