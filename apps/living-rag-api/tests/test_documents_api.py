import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app


@pytest.fixture
def client(db_session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_upload_markdown_document_returns_version_response(
    client: TestClient,
) -> None:
    response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "REFUND-POLICY",
            "source_type": "official_policy",
            "version_number": "1",
            "effective_at": "2026-07-21T00:00:00+08:00",
        },
        files={
            "file": (
                "refund_policy.md",
                "# 退款政策\n\n用户可以申请退款。",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["policy_key"] == "REFUND-POLICY"
    assert payload["version_number"] == 1
    assert payload["source_type"] == "official_policy"
    assert payload["original_filename"] == "refund_policy.md"
    assert payload["content_type"] == "text/markdown"
    assert payload["chunk_count"] == 1
    assert payload["content_hash"]


def test_upload_unsupported_document_type_returns_422(
    client: TestClient,
) -> None:
    response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "UNSUPPORTED-POLICY",
            "source_type": "official_policy",
            "version_number": "1",
            "effective_at": "2026-07-21T00:00:00+08:00",
        },
        files={
            "file": (
                "policy.docx",
                b"not a real docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported document type."


def test_upload_duplicate_content_returns_existing_version(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "DUPLICATE-REFUND-POLICY",
            "source_type": "official_policy",
            "version_number": "1",
            "effective_at": "2026-07-21T00:00:00+08:00",
        },
        files={
            "file": (
                "refund_policy_v1.md",
                "# 退款政策\n\n用户可以申请退款。",
                "text/markdown",
            )
        },
    )

    second_response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "DUPLICATE-REFUND-POLICY",
            "source_type": "official_policy",
            "version_number": "1",
            "effective_at": "2026-07-21T00:00:00+08:00",
        },
        files={
            "file": (
                "refund_policy_copy.md",
                "# 退款政策\n\n用户可以申请退款。",
                "text/markdown",
            )
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()

    assert second_payload["document_version_id"] == (first_payload["document_version_id"])
    assert second_payload["version_number"] == 1


def test_upload_new_content_with_wrong_version_number_returns_422(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "VERSION-REFUND-POLICY",
            "source_type": "official_policy",
            "version_number": "1",
            "effective_at": "2026-07-21T00:00:00+08:00",
        },
        files={
            "file": (
                "refund_policy_v1.md",
                "# 退款政策\n\n第一版正文。",
                "text/markdown",
            )
        },
    )

    second_response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "VERSION-REFUND-POLICY",
            "source_type": "official_policy",
            "version_number": "3",
            "effective_at": "2026-07-21T00:00:00+08:00",
        },
        files={
            "file": (
                "refund_policy_v3.md",
                "# 退款政策\n\n这是新的正文。",
                "text/markdown",
            )
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 422
    assert second_response.json()["detail"] == (
        "Requested version change is a possible conflict."
    )

def test_list_document_versions_returns_descending_versions(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "LIST-REFUND-POLICY",
            "source_type": "official_policy",
            "version_number": "1",
            "effective_at": "2026-07-21T00:00:00+08:00",
        },
        files={
            "file": (
                "refund_policy_v1.md",
                "# 退款政策\n\n第一版正文。",
                "text/markdown",
            )
        },
    )

    second_response = client.post(
        "/documents/upload",
        data={
            "title": "会员退款政策",
            "domain": "refund",
            "policy_key": "LIST-REFUND-POLICY",
            "source_type": "official_policy",
            "version_number": "2",
            "effective_at": "2026-08-01T00:00:00+08:00",
        },
        files={
            "file": (
                "refund_policy_v2.md",
                "# 退款政策\n\n第二版正文。",
                "text/markdown",
            )
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    response = client.get("/documents/LIST-REFUND-POLICY/versions")

    assert response.status_code == 200

    payload = response.json()

    assert [item["version_number"] for item in payload] == [2, 1]
    assert payload[0]["policy_key"] == "LIST-REFUND-POLICY"
    assert payload[0]["source_type"] == "official_policy"
    assert payload[0]["chunk_count"] == 1
    assert payload[0]["original_filename"] == "refund_policy_v2.md"
    assert payload[1]["original_filename"] == "refund_policy_v1.md"


def test_list_document_versions_returns_empty_for_unknown_policy(
    client: TestClient,
) -> None:
    response = client.get("/documents/UNKNOWN-LIST-POLICY/versions")

    assert response.status_code == 200
    assert response.json() == []
