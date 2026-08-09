import json
from pathlib import Path

import pytest

from app.schemas.agent_task_case import AgentTaskCategory
from app.services.task_dataset_loader import (
    TaskDatasetLoadError,
    load_all_task_cases,
    load_json_task_file,
    load_jsonl_task_file,
    load_task_directory,
    load_task_file,
)


def _task_payload(
    case_id: str,
    *,
    category: str = "normal_policy_qa",
    name: str = "测试任务",
    user_input: str = "当前退款政策是什么？",
    expected_route: str = "policy_qa",
) -> dict[str, object]:
    """Build one valid task payload for loader tests."""

    return {
        "case_id": case_id,
        "category": category,
        "name": name,
        "user_input": user_input,
        "context": {
            "source": "pytest",
        },
        "expected_route": expected_route,
        "expected_citations": [],
        "expected_behavior": [
            "返回有证据的回答",
        ],
        "forbidden_behavior": [
            "无证据编造结论",
        ],
        "failure_conditions": [
            "没有返回 trace_id",
        ],
    }


def test_load_json_task_file_returns_valid_task_cases(
    tmp_path: Path,
) -> None:
    """A JSON array is converted into validated AgentTaskCase objects."""

    dataset_file = tmp_path / "policy-qa.json"
    dataset_file.write_text(
        json.dumps(
            [
                _task_payload("qa-policy-001"),
                _task_payload("qa-policy-002"),
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    task_cases = load_json_task_file(dataset_file)

    assert len(task_cases) == 2
    assert task_cases[0].case_id == "qa-policy-001"
    assert task_cases[1].case_id == "qa-policy-002"
    assert task_cases[0].category is AgentTaskCategory.NORMAL_POLICY_QA


def test_load_jsonl_task_file_returns_valid_task_cases(
    tmp_path: Path,
) -> None:
    """A JSONL file is converted one line at a time into task cases."""

    dataset_file = tmp_path / "policy-qa.jsonl"
    lines = [
        json.dumps(
            _task_payload("qa-policy-001"),
            ensure_ascii=False,
        ),
        json.dumps(
            _task_payload("qa-policy-002"),
            ensure_ascii=False,
        ),
    ]
    dataset_file.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    task_cases = load_jsonl_task_file(dataset_file)

    assert [task.case_id for task in task_cases] == [
        "qa-policy-001",
        "qa-policy-002",
    ]


def test_load_jsonl_task_file_ignores_blank_lines(
    tmp_path: Path,
) -> None:
    """Blank JSONL lines do not create empty tasks."""

    dataset_file = tmp_path / "policy-qa.jsonl"
    dataset_file.write_text(
        "\n".join(
            [
                json.dumps(_task_payload("qa-policy-001")),
                "",
                "   ",
                json.dumps(_task_payload("qa-policy-002")),
            ]
        ),
        encoding="utf-8",
    )

    task_cases = load_jsonl_task_file(dataset_file)

    assert len(task_cases) == 2
    assert [task.case_id for task in task_cases] == [
        "qa-policy-001",
        "qa-policy-002",
    ]


def test_load_task_file_selects_parser_by_extension(
    tmp_path: Path,
) -> None:
    """The generic loader selects JSON or JSONL by file extension."""

    json_file = tmp_path / "tasks.json"
    jsonl_file = tmp_path / "tasks.jsonl"

    json_file.write_text(
        json.dumps([_task_payload("json-001")]),
        encoding="utf-8",
    )
    jsonl_file.write_text(
        json.dumps(_task_payload("jsonl-001")),
        encoding="utf-8",
    )

    json_tasks = load_task_file(json_file)
    jsonl_tasks = load_task_file(jsonl_file)

    assert [task.case_id for task in json_tasks] == ["json-001"]
    assert [task.case_id for task in jsonl_tasks] == ["jsonl-001"]


def test_load_task_file_rejects_unsupported_extension(
    tmp_path: Path,
) -> None:
    """Unsupported dataset file extensions are rejected."""

    dataset_file = tmp_path / "tasks.txt"
    dataset_file.write_text(
        "not a supported task dataset",
        encoding="utf-8",
    )

    with pytest.raises(
        TaskDatasetLoadError,
        match="Unsupported task dataset file extension",
    ):
        load_task_file(dataset_file)


def test_load_json_task_file_rejects_missing_file(
    tmp_path: Path,
) -> None:
    """A missing JSON task file produces a domain-specific error."""

    dataset_file = tmp_path / "missing.json"

    with pytest.raises(
        TaskDatasetLoadError,
        match="does not exist",
    ):
        load_json_task_file(dataset_file)


def test_load_json_task_file_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    """Invalid JSON reports the file path and parser location."""

    dataset_file = tmp_path / "broken.json"
    dataset_file.write_text(
        '[{"case_id": "broken-001"',
        encoding="utf-8",
    )

    with pytest.raises(
        TaskDatasetLoadError,
        match=r"Invalid JSON.*broken\.json",
    ):
        load_json_task_file(dataset_file)


def test_load_json_task_file_requires_array_root(
    tmp_path: Path,
) -> None:
    """A JSON task file must have an array as its root value."""

    dataset_file = tmp_path / "object-root.json"
    dataset_file.write_text(
        json.dumps(_task_payload("object-root-001")),
        encoding="utf-8",
    )

    with pytest.raises(
        TaskDatasetLoadError,
        match="JSON root must be a list",
    ):
        load_json_task_file(dataset_file)


def test_loader_reports_json_item_location_on_validation_error(
    tmp_path: Path,
) -> None:
    """A Pydantic error includes the source file and item number."""

    dataset_file = tmp_path / "invalid-task.json"
    invalid_task = _task_payload("invalid-001")
    invalid_task["name"] = ""

    dataset_file.write_text(
        json.dumps(
            [
                _task_payload("valid-001"),
                invalid_task,
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        TaskDatasetLoadError,
        match=r"invalid-task\.json at item 2",
    ):
        load_json_task_file(dataset_file)


def test_loader_reports_jsonl_line_location_on_parse_error(
    tmp_path: Path,
) -> None:
    """A malformed JSONL line reports the source file and line number."""

    dataset_file = tmp_path / "broken-tasks.jsonl"
    dataset_file.write_text(
        "\n".join(
            [
                json.dumps(_task_payload("valid-001")),
                '{"case_id": "broken-002"',
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        TaskDatasetLoadError,
        match=r"broken-tasks\.jsonl at line 2",
    ):
        load_jsonl_task_file(dataset_file)


def test_ensure_unique_case_ids_rejects_duplicates(
    tmp_path: Path,
) -> None:
    """Duplicate task IDs are rejected before batch execution."""

    dataset_file = tmp_path / "duplicate-tasks.json"
    dataset_file.write_text(
        json.dumps(
            [
                _task_payload("duplicate-001"),
                _task_payload("duplicate-001"),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        TaskDatasetLoadError,
        match="Duplicate case_id",
    ):
        load_json_task_file(dataset_file)


def test_load_task_directory_returns_sorted_merged_tasks(
    tmp_path: Path,
) -> None:
    """A directory loader reads supported files in stable order."""

    first_file = tmp_path / "01-first.json"
    second_file = tmp_path / "02-second.jsonl"

    first_file.write_text(
        json.dumps([_task_payload("directory-001")]),
        encoding="utf-8",
    )
    second_file.write_text(
        json.dumps(_task_payload("directory-002")),
        encoding="utf-8",
    )

    task_cases = load_task_directory(tmp_path)

    assert [task.case_id for task in task_cases] == [
        "directory-001",
        "directory-002",
    ]


def test_load_task_directory_filters_by_category(
    tmp_path: Path,
) -> None:
    """Directory loading can return only one task category."""

    dataset_file = tmp_path / "mixed.json"
    dataset_file.write_text(
        json.dumps(
            [
                _task_payload(
                    "policy-001",
                    category="normal_policy_qa",
                ),
                _task_payload(
                    "conflict-001",
                    category="conflict_case",
                    expected_route="conflict_safe_response",
                ),
            ]
        ),
        encoding="utf-8",
    )

    task_cases = load_task_directory(
        tmp_path,
        category=AgentTaskCategory.CONFLICT_CASE,
    )

    assert [task.case_id for task in task_cases] == ["conflict-001"]
    assert task_cases[0].category is AgentTaskCategory.CONFLICT_CASE


def test_load_task_directory_returns_empty_list_for_empty_directory(
    tmp_path: Path,
) -> None:
    """An empty dataset directory is a valid empty collection."""

    task_cases = load_task_directory(tmp_path)

    assert task_cases == []


def test_load_task_directory_rejects_missing_directory(
    tmp_path: Path,
) -> None:
    """A missing dataset directory produces a domain-specific error."""

    missing_directory = tmp_path / "missing"

    with pytest.raises(
        TaskDatasetLoadError,
        match="does not exist",
    ):
        load_task_directory(missing_directory)


def test_load_all_task_cases_reads_known_category_directories(
    tmp_path: Path,
) -> None:
    """The root loader merges tasks from the known shared categories."""

    qa_directory = tmp_path / "qa"
    conflict_directory = tmp_path / "conflict-cases"

    qa_directory.mkdir()
    conflict_directory.mkdir()

    (qa_directory / "qa.json").write_text(
        json.dumps(
            [
                _task_payload(
                    "qa-001",
                    category="normal_policy_qa",
                )
            ]
        ),
        encoding="utf-8",
    )
    (conflict_directory / "conflict.json").write_text(
        json.dumps(
            [
                _task_payload(
                    "conflict-001",
                    category="conflict_case",
                    expected_route="conflict_safe_response",
                )
            ]
        ),
        encoding="utf-8",
    )

    task_cases = load_all_task_cases(tmp_path)

    assert [task.case_id for task in task_cases] == [
        "qa-001",
        "conflict-001",
    ]


def test_load_all_task_cases_rejects_duplicate_ids_across_directories(
    tmp_path: Path,
) -> None:
    """Duplicate IDs are rejected even when they occur in different categories."""

    qa_directory = tmp_path / "qa"
    conflict_directory = tmp_path / "conflict-cases"

    qa_directory.mkdir()
    conflict_directory.mkdir()

    (qa_directory / "qa.json").write_text(
        json.dumps(
            [
                _task_payload(
                    "same-001",
                    category="normal_policy_qa",
                )
            ]
        ),
        encoding="utf-8",
    )
    (conflict_directory / "conflict.json").write_text(
        json.dumps(
            [
                _task_payload(
                    "same-001",
                    category="conflict_case",
                    expected_route="conflict_safe_response",
                )
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        TaskDatasetLoadError,
        match="Duplicate case_id",
    ):
        load_all_task_cases(tmp_path)
