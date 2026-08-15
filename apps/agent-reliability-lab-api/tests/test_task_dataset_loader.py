import json
from pathlib import Path

import pytest
import yaml

from app.services.task_dataset_loader import (
    load_agent_task_cases,
    load_evaluation_dataset,
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


def test_load_evaluation_dataset_wraps_jsonl_cases(
    tmp_path: Path,
) -> None:
    dataset_file = tmp_path / "business_eligibility.jsonl"
    dataset_file.write_text(
        "\n".join(
            [
                json.dumps(make_task_payload("case-001"), ensure_ascii=False),
                json.dumps(make_task_payload("case-002"), ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )

    dataset, cases = load_evaluation_dataset(dataset_file)

    assert dataset.name == "business_eligibility"
    assert dataset.version == "1"
    assert dataset.source_path == str(dataset_file)
    assert len(cases) == 2
    assert {case.task.case_id for case in cases} == {
        "case-001",
        "case-002",
    }
    assert all(case.dataset_id == dataset.dataset_id for case in cases)


def test_load_evaluation_dataset_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.jsonl"

    with pytest.raises(ValueError, match="does not exist"):
        load_evaluation_dataset(missing_file)


def test_load_evaluation_dataset_rejects_unsupported_format(
    tmp_path: Path,
) -> None:
    text_file = tmp_path / "tasks.txt"
    text_file.write_text("not a supported dataset", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported"):
        load_evaluation_dataset(text_file)


def test_load_evaluation_dataset_rejects_empty_jsonl(
    tmp_path: Path,
) -> None:
    empty_file = tmp_path / "empty.jsonl"
    empty_file.write_text("\n\n", encoding="utf-8")

    with pytest.raises(ValueError, match="No Agent task cases"):
        load_evaluation_dataset(empty_file)


@pytest.mark.parametrize("suffix", [".yaml", ".yml"])
def test_load_evaluation_dataset_loads_yaml_cases(
    tmp_path: Path,
    suffix: str,
) -> None:
    dataset_file = tmp_path / f"business_eligibility{suffix}"
    payload = {
        "version": "2026.08",
        "cases": [
            make_task_payload("yaml-case-001"),
            make_task_payload("yaml-case-002"),
        ],
    }
    dataset_file.write_text(
        yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    dataset, cases = load_evaluation_dataset(dataset_file)

    assert dataset.name == "business_eligibility"
    assert dataset.version == "2026.08"
    assert len(cases) == 2
    assert {case.task.case_id for case in cases} == {
        "yaml-case-001",
        "yaml-case-002",
    }
    assert all(case.dataset_id == dataset.dataset_id for case in cases)


def test_load_evaluation_dataset_rejects_yaml_list_root(
    tmp_path: Path,
) -> None:
    dataset_file = tmp_path / "invalid-root.yaml"
    dataset_file.write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="must be an object"):
        load_evaluation_dataset(dataset_file)


def test_load_evaluation_dataset_rejects_yaml_without_version(
    tmp_path: Path,
) -> None:
    dataset_file = tmp_path / "missing-version.yaml"
    payload = {
        "cases": [make_task_payload("yaml-case-001")],
    }
    dataset_file.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a non-empty version"):
        load_evaluation_dataset(dataset_file)


def test_load_evaluation_dataset_rejects_yaml_with_empty_cases(
    tmp_path: Path,
) -> None:
    dataset_file = tmp_path / "empty-cases.yaml"
    payload = {
        "version": "1",
        "cases": [],
    }
    dataset_file.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a non-empty cases list"):
        load_evaluation_dataset(dataset_file)


def test_load_evaluation_dataset_rejects_duplicate_yaml_case_ids(
    tmp_path: Path,
) -> None:
    dataset_file = tmp_path / "duplicate-case-id.yaml"
    payload = {
        "version": "1",
        "cases": [
            make_task_payload("duplicate-case"),
            make_task_payload("duplicate-case"),
        ],
    }
    dataset_file.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate Agent task case_id"):
        load_evaluation_dataset(dataset_file)