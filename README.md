# Payments Gateway API

A production-oriented REST API for processing payments, handling idempotent requests, detecting suspicious transactions, processing refunds, and handling payment-provider webhooks.

## Features

- User authentication with JWT
- Secure password hashing using Argon2
- Payment creation
- PostgreSQL database integration
- Idempotent payment requests
- Payment status management
- Rule-based fraud detection
- High-value payment detection
- Rapid repeated-payment detection
- Stripe webhook handling
- Duplicate webhook protection
- Partial refunds
- Multiple partial refunds
- Full refunds
- Over-refund protection
- Automated API testing
- Alembic database migrations
- Production-oriented database connection handling

## Tech Stack

- Backend: Python, FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Authentication: JWT
- Password Hashing: Argon2
- Payment Provider: Stripe / Mock Provider
- Testing: Pytest
- Server: Uvicorn

## Architecture

```text
Client
  |
  v
FastAPI
  |
  +---- Authentication
  |
  +---- Payment API
  |       |
  |       +---- Idempotency
  |       +---- Fraud Detection
  |       +---- Payment Provider
  |
  +---- Refund API
  |
  +---- Webhooks
  |
  v
PostgreSQL
```

## Idempotency
Payment creation supports idempotency keys to prevent duplicate payments when the same request is submitted multiple times.

## The API handles:
 Same idempotency key + same parameters → existing payment is returned 
 Same idempotency key + different parameters → request is rejected 

## Fraud Detection:
The API currently uses rule-based fraud detection.
High-Amount Rule:
Payments above the configured threshold receive additional fraud risk.
Rapid-Payment Rule:
Multiple payments made by the same user within a short time window increase the fraud score.

The payment stores:
- is_suspicious 
- fraud_score 
- fraud_reasons 

Suspicious payments can be rejected according to the configured payment flow.

## Refunds

The API supports:
- Partial refunds
- Multiple partial refunds
- Full refunds after partial refunds
- Protection against refunding more than the original payment amount
- Rejection of refunds for non-refundable payment states

Refunds are stored separately from payments and are linked through a foreign key.
Payment
   |
   +---- Refund
   |
   +---- Refund
   |
   +---- Refund

The payment also maintains the total refunded_amount.

## Webhooks:
The API provides a Stripe webhook endpoint for payment-provider events.

Supported payment events include:
-> payment_intent.succeeded
-> payment_intent.payment_failed

Webhook signatures are verified when using Stripe.
Duplicate webhook events are detected and ignored to prevent the same event from being processed more than once.

## Authentication
Protected endpoints use JWT-based authentication.

The authentication flow is:

Register / Login
      |
      v
JWT Access Token
      |
      v
Authorization: Bearer <token>
      |
      v
Protected API Endpoint

Passwords are stored as secure Argon2 hashes rather than plaintext.

## Database:
PostgreSQL is used for persistent storage.

Main entities include:
- Users
- Payments
- Refunds

Alembic is used for database schema migrations.

Run migrations with:
python -m alembic upgrade head

## API Endpoints:
- Authentication
POST /auth/login
- Payments
POST /payments/
GET  /payments/
- Refunds
POST /payments/{payment_id}/refund
- Webhooks
POST /webhooks/stripe
- Health
GET /health

## Environment Variables:
Create a local .env file containing the required configuration.

Example:
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=payments_db
DATABASE_USER=postgres
DATABASE_PASSWORD=your_database_password

SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

PAYMENT_PROVIDER=mock

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

-> Never commit the real .env file to GitHub.

A .env.example file is included as a template.

## Local Setup
1. Clone the repository
git clone <repository-url>
cd payments-api
2. Create a virtual environment
python -m venv .venv
3. Activate the environment
Windows CMD:
.venv\Scripts\activate
4. Install dependencies
pip install -r requirements.txt
5. Configure environment variables
Create .env using .env.example as a reference.
6. Run database migrations
python -m alembic upgrade head
7. Start the API
uvicorn app.main:app --reload

The API will be available locally through the FastAPI server.

FastAPI's interactive Swagger documentation is available at:
/docs

## Testing
The project uses Pytest for automated testing.

Run the complete test suite:
python -m pytest -v

The test suite covers:
-> Health checks
-> Payment creation
-> Idempotency
-> Fraud detection
-> Refunds
-> Webhooks
-> Authorization
-> Edge cases

Current test status:
20 tests passed

## Project Structure
```text
payments-api/
│
├── app/
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   │
│   ├── database/
│   │   └── database.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── payment.py
│   │   └── refund.py
│   │
│   ├── routers/
│   │   ├── users.py
│   │   ├── auth.py
│   │   ├── payments.py
│   │   └── webhooks.py
│   │
│   ├── schemas/
│   │   ├── user.py
│   │   ├── payment.py
│   │   └── refund.py
│   │
│   └── services/
│       ├── payment_service.py
│       └── fraud_service.py
│
├── alembic/
│   └── versions/
│
├── tests/
│   ├── test_health.py
│   ├── test_payments.py
│   ├── test_refunds.py
│   └── test_webhooks.py
│
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```
