from __future__ import annotations

from scripts.prepare_demo_data import (
    SOURCE_STATUS_TO_GOVERNANCE_STATUS,
    generate_pending_embeddings,
)
from app.models.document import DocumentGovernanceStatus


def test_sample_source_statuses_map_to_searchable_governance_statuses() -> None:
    assert SOURCE_STATUS_TO_GOVERNANCE_STATUS == {
        "active": DocumentGovernanceStatus.ACTIVE,
        "archived": DocumentGovernanceStatus.SUPERSEDED,
        "invalid": DocumentGovernanceStatus.INVALID,
    }


def test_generate_pending_embeddings_uses_provider_and_returns_count(
    monkeypatch,
) -> None:
    calls: list[object] = []

    class FakeSessionContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def begin(self):
            return self

    class FakeProvider:
        pass

    def fake_session_local():
        return FakeSessionContext()

    def fake_create_provider():
        calls.append("provider")
        return FakeProvider()

    def fake_embed_pending_chunks(session, provider):
        calls.extend([session, provider])
        return 56

    monkeypatch.setattr(
        "scripts.prepare_demo_data.SessionLocal",
        fake_session_local,
    )
    monkeypatch.setattr(
        "scripts.prepare_demo_data.create_embedding_provider",
        fake_create_provider,
    )
    monkeypatch.setattr(
        "scripts.prepare_demo_data.embed_pending_chunks",
        fake_embed_pending_chunks,
    )

    assert generate_pending_embeddings() == 56
    assert calls[0] == "provider"
    assert isinstance(calls[2], FakeProvider)
