from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.approval_task import (
    ApprovalTaskStatus,
    ApprovalTaskType,
)
from app.models.user import User
from app.services.approval_task_service import (
    create_approval_task,
)


@pytest.fixture
def client(db_session) -> TestClient:
    """Use the isolated test session for API requests."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create_user(
    db_session,
    *,
    external_id: str,
    display_name: str,
) -> User:
    """Create a test user for task ownership or approval."""

    user = User(
        external_id=external_id,
        display_name=display_name,
    )

    db_session.add(user)
    db_session.flush()

    return user


def test_list_approval_tasks_returns_created_task(
    client: TestClient,
    db_session,
) -> None:
    """The approval task list endpoint should return stored tasks."""

    requester = _create_user(
        db_session,
        external_id="USR-API-001",
        display_name="API Requester",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="User requested a direct refund.",
    )

    response = client.get("/approval-tasks")

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["id"] == str(task.id)
    assert payload[0]["task_type"] == "direct_refund"
    assert payload[0]["status"] == "pending"
    assert payload[0]["resource_type"] == "order"
    assert payload[0]["reason"] == (
        "User requested a direct refund."
    )
    assert payload[0]["metadata"] == {}


def test_list_approval_tasks_supports_status_filter(
    client: TestClient,
    db_session,
) -> None:
    """The list endpoint should filter tasks by status."""

    requester = _create_user(
        db_session,
        external_id="USR-API-002",
        display_name="Status Filter Requester",
    )

    create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="Pending direct refund.",
    )

    approved_task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.REFUND_REQUEST,
        resource_type="refund_request",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="Pending refund request.",
    )

    approved_task.status = ApprovalTaskStatus.APPROVED
    db_session.flush()

    pending_response = client.get(
        "/approval-tasks",
        params={"status": "pending"},
    )

    approved_response = client.get(
        "/approval-tasks",
        params={"status": "approved"},
    )

    assert pending_response.status_code == 200
    assert approved_response.status_code == 200

    pending_payload = pending_response.json()
    approved_payload = approved_response.json()

    assert len(pending_payload) == 1
    assert pending_payload[0]["status"] == "pending"

    assert len(approved_payload) == 1
    assert approved_payload[0]["id"] == str(approved_task.id)
    assert approved_payload[0]["status"] == "approved"


def test_list_approval_tasks_supports_type_filter(
    client: TestClient,
    db_session,
) -> None:
    """The list endpoint should filter tasks by task type."""

    requester = _create_user(
        db_session,
        external_id="USR-API-003",
        display_name="Type Filter Requester",
    )

    create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="Direct refund request.",
    )

    create_approval_task(
        db_session,
        task_type=ApprovalTaskType.MODIFY_POLICY,
        resource_type="document_version",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="Policy modification request.",
    )

    response = client.get(
        "/approval-tasks",
        params={"task_type": "modify_policy"},
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["task_type"] == "modify_policy"
    assert payload[0]["resource_type"] == "document_version"


def test_decision_endpoint_approves_task(
    client: TestClient,
    db_session,
) -> None:
    """The decision endpoint should approve a pending task."""

    requester = _create_user(
        db_session,
        external_id="USR-API-004",
        display_name="Decision Requester",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-API-001",
        display_name="Approval Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="User requested a direct refund.",
    )

    response = client.post(
        f"/approval-tasks/{task.id}/decision",
        headers={
            "X-Actor-ID": str(admin.id),
        },
        json={
            "decision": "approve",
            "decision_reason": "订单和退款资格已核实。",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["id"] == str(task.id)
    assert payload["status"] == "approved"
    assert payload["decision"] == "approve"
    assert payload["decision_reason"] == (
        "订单和退款资格已核实。"
    )
    assert payload["decided_by"] == str(admin.id)
    assert payload["decided_at"] is not None


def test_decision_endpoint_rejects_task(
    client: TestClient,
    db_session,
) -> None:
    """The decision endpoint should reject a pending task."""

    requester = _create_user(
        db_session,
        external_id="USR-API-005",
        display_name="Reject Requester",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-API-002",
        display_name="Reject Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DELETE_DOCUMENT,
        resource_type="document_version",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="User requested document deletion.",
    )

    response = client.post(
        f"/approval-tasks/{task.id}/decision",
        headers={
            "X-Actor-ID": str(admin.id),
        },
        json={
            "decision": "reject",
            "decision_reason": "删除政策文档必须保留人工审核记录。",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["id"] == str(task.id)
    assert payload["status"] == "rejected"
    assert payload["decision"] == "reject"
    assert payload["decision_reason"] == (
        "删除政策文档必须保留人工审核记录。"
    )
    assert payload["decided_by"] == str(admin.id)


def test_decision_endpoint_requires_actor_header(
    client: TestClient,
    db_session,
) -> None:
    """The decision endpoint must require an approver identity."""

    requester = _create_user(
        db_session,
        external_id="USR-API-006",
        display_name="Missing Actor Requester",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="Direct refund request.",
    )

    response = client.post(
        f"/approval-tasks/{task.id}/decision",
        json={
            "decision": "approve",
            "decision_reason": "Approved.",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_decision_endpoint_returns_bad_request_for_unknown_task(
    client: TestClient,
) -> None:
    """Deciding a missing task should return a client error."""

    admin_id = uuid4()
    missing_task_id = uuid4()

    response = client.post(
        f"/approval-tasks/{missing_task_id}/decision",
        headers={
            "X-Actor-ID": str(admin_id),
        },
        json={
            "decision": "approve",
            "decision_reason": "Attempted approval.",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Approval task not found: {missing_task_id}"
    )


def test_decision_endpoint_rejects_duplicate_decision(
    client: TestClient,
    db_session,
) -> None:
    """An already approved task must not be decided again."""

    requester = _create_user(
        db_session,
        external_id="USR-API-007",
        display_name="Duplicate API Requester",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-API-003",
        display_name="Duplicate API Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="Direct refund request.",
    )

    first_response = client.post(
        f"/approval-tasks/{task.id}/decision",
        headers={
            "X-Actor-ID": str(admin.id),
        },
        json={
            "decision": "approve",
            "decision_reason": "Approved after review.",
        },
    )

    second_response = client.post(
        f"/approval-tasks/{task.id}/decision",
        headers={
            "X-Actor-ID": str(admin.id),
        },
        json={
            "decision": "reject",
            "decision_reason": "Attempted second decision.",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == (
        "Only pending approval tasks can be decided."
    )


def test_decision_endpoint_rejects_empty_reason(
    client: TestClient,
    db_session,
) -> None:
    """The API should reject a decision without a meaningful reason."""

    requester = _create_user(
        db_session,
        external_id="USR-API-008",
        display_name="Empty Reason Requester",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-API-004",
        display_name="Empty Reason Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=requester.id,
        trace_id=uuid4(),
        reason="Direct refund request.",
    )

    response = client.post(
        f"/approval-tasks/{task.id}/decision",
        headers={
            "X-Actor-ID": str(admin.id),
        },
        json={
            "decision": "approve",
            "decision_reason": "   ",
        },
    )

    assert response.status_code == 422