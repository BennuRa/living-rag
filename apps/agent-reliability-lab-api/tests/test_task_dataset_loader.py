import json
from pathlib import Path

import pytest

from app.services.task_dataset_loader import (
    load_agent_task_cases,
    load_shared_agent_task_cases,
    shared_agent_task_dataset_dir,
)


def make_task_payload(case_id: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "name": f"测试任务 {case_id}",
        "category": "normal_policy_qa",
        "user_input": "当前退款政策是什么？",
        "expected_route": "policy_qa",
        "expected_behavior": ["检索当前有效政策"],
    }


def write_jsonl(
    dataset_file: Path,
    rows: list[dict[str, object]],
) -> None:
    content = "\n".join(
        json.dumps(row, ensure_ascii=False)
        for row in rows
    )
    dataset_file.write_text(f"{content}\n", encoding="utf-8")


def test_loader_reads_the_real_shared_agent_task_dataset() -> None:
    dataset_dir = shared_agent_task_dataset_dir()
    cases = load_shared_agent_task_cases()

    assert dataset_dir.is_dir()
    assert len(cases) >= 1
    assert all(case.case_id for case in cases)
    assert all(case.expected_behavior for case in cases)


def test_loader_reads_multiple_valid_jsonl_cases(tmp_path: Path) -> None:
    write_jsonl(
        tmp_path / "cases.jsonl",
        [
            make_task_payload("case-001"),
            make_task_payload("case-002"),
        ],
    )

    cases = load_agent_task_cases(tmp_path)

    assert [case.case_id for case in cases] == [
        "case-001",
        "case-002",
    ]


def test_loader_rejects_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "invalid.jsonl").write_text(
        '{"case_id": "broken"\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Invalid JSON in invalid.jsonl at line 1",
    ):
        load_agent_task_cases(tmp_path)


def test_loader_rejects_invalid_task_schema(tmp_path: Path) -> None:
    invalid_payload = make_task_payload("invalid-case")
    invalid_payload.pop("expected_behavior")

    write_jsonl(
        tmp_path / "invalid.jsonl",
        [invalid_payload],
    )

    with pytest.raises(
        ValueError,
        match="Invalid task case in invalid.jsonl at line 1",
    ):
        load_agent_task_cases(tmp_path)


def test_loader_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    write_jsonl(
        tmp_path / "first.jsonl",
        [make_task_payload("duplicate-case")],
    )
    write_jsonl(
        tmp_path / "second.jsonl",
        [make_task_payload("duplicate-case")],
    )

    with pytest.raises(
        ValueError,
        match="Duplicate Agent task case_id: 'duplicate-case'",
    ):
        load_agent_task_cases(tmp_path)


def test_loader_rejects_an_empty_dataset_directory(tmp_path: Path) -> None:
    with pytest.raises(
        ValueError,
        match="No Agent task cases found in dataset directory",
    ):
        load_agent_task_cases(tmp_path)