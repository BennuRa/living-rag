from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import get_db
from app.main import app
from app.models.approval_task import ApprovalTask
from app.models.audit_log import AuditLog
from app.models.membership_account import (
    MembershipAccount,
    MembershipTier,
)
from app.models.order import Order, OrderStatus
from app.models.user import User


@pytest.fixture
def client(db_session) -> TestClient:
    """Use the isolated database session for business-action requests."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_user_with_order(
    db_session,
    *,
    external_id: str,
    order_number: str,
) -> tuple[User, Order]:
    """Create one user, membership account, and owned order."""

    user = User(
        external_id=external_id,
        display_name=f"Business Action User {external_id}",
    )

    membership = MembershipAccount(
        user=user,
        membership_number=f"M-{external_id}",
        tier=MembershipTier.STANDARD,
    )

    order = Order(
        membership_account=membership,
        order_number=order_number,
        status=OrderStatus.COMPLETED,
        total_amount=Decimal("199.00"),
        metadata_={
            "received_at": "2026-08-01T14:30:00+08:00",
            "returnable": True,
            "product_name": "Test Product",
        },
    )

    db_session.add(user)
    db_session.flush()

    return user, order


def test_direct_refund_creates_pending_approval_task(
    client: TestClient,
    db_session,
) -> None:
    """A direct refund request must create approval, not execute refund."""

    user, order = _create_user_with_order(
        db_session,
        external_id="USR-BUSINESS-001",
        order_number="O2025001",
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "直接退款 O2025001",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["trace_id"]
    assert payload["action"] == "create_approval_task"
    assert payload["intent"] == "high_risk_operation"
    assert payload["status"] == "pending"
    assert payload["order_number"] == "O2025001"
    assert payload["approval_task_id"]
    assert payload["refund_request_id"] is None

    task_statement = select(ApprovalTask).where(
        ApprovalTask.id == payload["approval_task_id"],
    )

    task = db_session.scalar(task_statement)

    assert task is not None
    assert task.task_type.value == "direct_refund"
    assert task.status.value == "pending"
    assert task.resource_type == "order"
    assert task.resource_id == order.id
    assert task.requested_by == user.id
    assert task.trace_id is not None

    audit_statement = select(AuditLog).where(
        AuditLog.resource_id == task.id,
        AuditLog.action == "create_approval_task",
    )

    audit_log = db_session.scalar(audit_statement)

    assert audit_log is not None
    assert audit_log.result.value == "pending"
    assert audit_log.actor_id == user.id
    assert audit_log.trace_id == task.trace_id


def test_read_only_eligibility_question_creates_no_task(
    client: TestClient,
    db_session,
) -> None:
    """A read-only eligibility question must not create approval."""

    user, _ = _create_user_with_order(
        db_session,
        external_id="USR-BUSINESS-002",
        order_number="O2025002",
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "O2025002 能退款吗？",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["action"] == "read_only"
    assert payload["intent"] == "order_membership"
    assert payload["status"] == "eligible"
    assert payload["eligibility"]["eligible"] is True
    assert payload["order_number"] == "O2025002"
    assert payload["approval_task_id"] is None
    assert payload["refund_request_id"] is None

    tasks = db_session.scalars(
        select(ApprovalTask),
    ).all()

    assert tasks == []


def test_unknown_request_rejects_direct_execution(
    client: TestClient,
    db_session,
) -> None:
    """An unknown request must not create any business record."""

    user, _ = _create_user_with_order(
        db_session,
        external_id="USR-BUSINESS-003",
        order_number="O2025003",
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "帮我处理一下",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["action"] == "reject_direct_execution"
    assert payload["intent"] == "unknown"
    assert payload["status"] == "rejected"
    assert payload["approval_task_id"] is None
    assert payload["refund_request_id"] is None

    tasks = db_session.scalars(
        select(ApprovalTask),
    ).all()

    audit_logs = db_session.scalars(
        select(AuditLog),
    ).all()

    assert tasks == []
    assert audit_logs == []


def test_direct_refund_for_unknown_order_is_rejected(
    client: TestClient,
    db_session,
) -> None:
    """A direct refund for an order not owned by the user is rejected."""

    user, _ = _create_user_with_order(
        db_session,
        external_id="USR-BUSINESS-004",
        order_number="O2025004",
    )

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "直接退款 O9999001",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["action"] == "reject_direct_execution"
    assert payload["intent"] == "high_risk_operation"
    assert payload["status"] == "rejected"
    assert payload["order_number"] == "O9999001"
    assert payload["approval_task_id"] is None

    tasks = db_session.scalars(
        select(ApprovalTask),
    ).all()

    assert tasks == []


def test_modify_policy_creates_policy_approval_task(
    client: TestClient,
    db_session,
) -> None:
    """Policy modification must create an approval task."""

    user = User(
        external_id="USR-BUSINESS-005",
        display_name="Policy Modification User",
    )

    db_session.add(user)
    db_session.flush()

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "把退款政策修改成 60 天",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["action"] == "create_approval_task"
    assert payload["intent"] == "high_risk_operation"
    assert payload["status"] == "pending"
    assert payload["approval_task_id"]
    assert payload["order_number"] is None

    task_statement = select(ApprovalTask).where(
        ApprovalTask.id == payload["approval_task_id"],
    )

    task = db_session.scalar(task_statement)

    assert task is not None
    assert task.task_type.value == "modify_policy"
    assert task.status.value == "pending"
    assert task.resource_type == "policy"
    assert task.resource_id is None
    assert task.requested_by == user.id


def test_delete_document_creates_document_approval_task(
    client: TestClient,
    db_session,
) -> None:
    """Policy document deletion must create an approval task."""

    user = User(
        external_id="USR-BUSINESS-006",
        display_name="Document Deletion User",
    )

    db_session.add(user)
    db_session.flush()

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": str(user.id),
            "question": "删除退款政策文档",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["action"] == "create_approval_task"
    assert payload["intent"] == "high_risk_operation"
    assert payload["status"] == "pending"
    assert payload["approval_task_id"]

    task_statement = select(ApprovalTask).where(
        ApprovalTask.id == payload["approval_task_id"],
    )

    task = db_session.scalar(task_statement)

    assert task is not None
    assert task.task_type.value == "delete_document"
    assert task.status.value == "pending"
    assert task.resource_type == "document"
    assert task.resource_id is None
    assert task.requested_by == user.id


def test_business_action_rejects_invalid_user_id(
    client: TestClient,
) -> None:
    """The request schema must reject an invalid user UUID."""

    response = client.post(
        "/api/business-actions",
        json={
            "user_id": "not-a-uuid",
            "question": "直接退款 O2025001",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]
