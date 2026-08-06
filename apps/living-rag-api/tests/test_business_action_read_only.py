from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.membership_account import (
    MembershipAccount,
    MembershipAccountStatus,
    MembershipTier,
)
from app.models.order import Order, OrderStatus
from app.models.user import User


@pytest.fixture
def client(db_session) -> TestClient:
    """Use the isolated database session for read-only API tests."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_order_case(
    db_session,
    *,
    external_id: str,
    order_number: str,
    tier: MembershipTier,
    membership_status: MembershipAccountStatus,
    received_at: str,
    designated_free_return: bool,
) -> User:
    """Create one user, membership, and order for a read-only query."""

    user = User(
        external_id=external_id,
        display_name=f"Read Only User {external_id}",
    )

    membership = MembershipAccount(
        user=user,
        membership_number=f"M-{external_id}",
        tier=tier,
        status=membership_status,
    )

    Order(
        membership_account=membership,
        order_number=order_number,
        status=OrderStatus.COMPLETED,
        total_amount=Decimal("199.00"),
        metadata_={
            "received_at": received_at,
            "returnable": True,
            "product_name": "Demo Product",
            "designated_free_return": designated_free_return,
            "campaign_tags": [],
        },
    )

    db_session.add(user)
    db_session.flush()

    return user


def test_standard_member_read_only_query_returns_eligibility(
    client: TestClient,
    db_session,
) -> None:
    """O2025001 should return eligible and customer-paid shipping."""

    user = _create_order_case(
        db_session,
        external_id="USR-READ-001",
        order_number="O2025001",
        tier=MembershipTier.STANDARD,
        membership_status=MembershipAccountStatus.ACTIVE,
        received_at="2026-01-05T14:30:00+08:00",
        designated_free_return=False,
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "Is O2025001 eligible for a refund?",
            "as_of": "2026-01-17T00:00:00+00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["action"] == "read_only"
    assert payload["status"] == "eligible"
    assert payload["order_number"] == "O2025001"
    assert payload["order_facts"]["status"] == "completed"
    assert payload["order_facts"]["is_received"] is True
    assert payload["order_facts"]["product_name"] == "Demo Product"
    assert payload["membership_facts"]["tier"] == "standard"
    assert payload["membership_facts"]["status"] == "active"
    assert payload["eligibility"]["eligible"] is True
    assert payload["eligibility"]["decision"] == "eligible"
    assert payload["eligibility"]["return_shipping_payer"] == "customer"


def test_gold_member_read_only_query_returns_platform_shipping(
    client: TestClient,
    db_session,
) -> None:
    """An active gold member with a designated item gets platform shipping."""

    user = _create_order_case(
        db_session,
        external_id="USR-READ-002",
        order_number="O2025002",
        tier=MembershipTier.GOLD,
        membership_status=MembershipAccountStatus.ACTIVE,
        received_at="2026-01-06T16:00:00+08:00",
        designated_free_return=True,
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "Is O2025002 eligible for a refund?",
            "as_of": "2026-01-20T00:00:00+00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "eligible"
    assert payload["membership_facts"]["tier"] == "gold"
    assert payload["membership_facts"]["status"] == "active"
    assert payload["order_facts"]["designated_free_return"] is True
    assert payload["eligibility"]["return_shipping_payer"] == "platform"


def test_suspended_gold_member_read_only_query_requires_manual_review(
    client: TestClient,
    db_session,
) -> None:
    """A suspended gold account must not receive automatic gold benefits."""

    user = _create_order_case(
        db_session,
        external_id="USR-READ-007",
        order_number="O2025007",
        tier=MembershipTier.GOLD,
        membership_status=MembershipAccountStatus.SUSPENDED,
        received_at="2026-01-05T11:00:00+08:00",
        designated_free_return=True,
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "Is O2025007 eligible for a refund?",
            "as_of": "2026-01-17T00:00:00+00:00",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "manual_review"
    assert payload["eligibility"]["eligible"] is False
    assert payload["eligibility"]["decision"] == "manual_review"
    assert payload["eligibility"]["requires_manual_review"] is True
    assert payload["membership_facts"]["tier"] == "gold"
    assert payload["membership_facts"]["status"] == "suspended"
