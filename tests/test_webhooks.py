import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.database.database import SessionLocal
from app.main import app
from app.models.payment import Payment
from app.models.user import User


client = TestClient(app)


@pytest.fixture
def test_user():
    db = SessionLocal()

    user = User(
        email=f"webhook_test_{uuid.uuid4().hex}@example.com",
        full_name="Webhook Test User",
        hashed_password="test-password",
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    db.query(Payment).filter(
        Payment.user_id == user.id
    ).delete()

    db.delete(user)
    db.commit()
    db.close()


@pytest.fixture
def authenticated_client(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user

    yield client

    app.dependency_overrides.clear()


def create_test_payment(authenticated_client):
    response = authenticated_client.post(
        "/payments/",
        headers={
            "Idempotency-Key": f"webhook-test-{uuid.uuid4().hex}",
        },
        json={
            "amount": 5000,
            "currency": "INR",
        },
    )

    assert response.status_code == 201

    return response.json()


def test_successful_payment_webhook(
    authenticated_client,
):
    payment = create_test_payment(authenticated_client)

    payment_intent_id = payment["stripe_payment_intent_id"]

    response = client.post(
        "/webhooks/stripe",
        json={
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": payment_intent_id,
                }
            },
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "processed"
    assert data["payment_status"] == "succeeded"


def test_duplicate_webhook_is_ignored(
    authenticated_client,
):
    payment = create_test_payment(authenticated_client)

    payment_intent_id = payment["stripe_payment_intent_id"]

    event_id = f"evt_{uuid.uuid4().hex}"

    payload = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
            }
        },
    }

    first_response = client.post(
        "/webhooks/stripe",
        json=payload,
    )

    second_response = client.post(
        "/webhooks/stripe",
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert first_response.json()["status"] == "processed"

    assert second_response.json()["status"] == "already_processed"
    assert second_response.json()["payment_status"] == "succeeded"


def test_unsupported_webhook_event_is_ignored():
    response = client.post(
        "/webhooks/stripe",
        json={
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "customer.created",
            "data": {
                "object": {},
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_for_missing_payment_returns_404():
    response = client.post(
        "/webhooks/stripe",
        json={
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": f"mock_pi_nonexistent_{uuid.uuid4().hex}",
                }
            },
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"