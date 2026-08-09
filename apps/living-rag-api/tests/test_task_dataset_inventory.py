import json
from collections import Counter
from pathlib import Path

from app.schemas.agent_task_case import AgentTaskCategory
from app.services.task_dataset_loader import load_all_task_cases

DATASET_ROOT = Path("/shared/datasets")


def test_shared_dataset_contains_at_least_fifty_structured_tasks() -> None:
    """The Day 16 shared dataset has the planned task inventory."""

    task_cases = load_all_task_cases(DATASET_ROOT)
    counts = Counter(task.category for task in task_cases)

    assert len(task_cases) == 71
    assert len({task.case_id for task in task_cases}) == len(task_cases)
    assert counts[AgentTaskCategory.NORMAL_POLICY_QA] >= 15
    assert counts[AgentTaskCategory.VERSION_AND_STALE_CONTENT] >= 8
    assert counts[AgentTaskCategory.CONFLICT_CASE] >= 10
    assert counts[AgentTaskCategory.ORDER_MEMBERSHIP_ELIGIBILITY] >= 10
    assert counts[AgentTaskCategory.HIGH_RISK_ACTION] >= 8
    assert counts[AgentTaskCategory.MULTI_TURN] >= 5
    assert counts[AgentTaskCategory.FAULT_INJECTION] >= 5
    assert counts[AgentTaskCategory.ADVERSARIAL] >= 10


def test_shared_dataset_has_required_category_directories() -> None:
    """All five planned shared dataset directories are present."""

    expected_directories = {
        "qa",
        "conflict-cases",
        "agent-tasks",
        "fault-injection",
        "adversarial",
    }

    actual_directories = {
        path.name
        for path in DATASET_ROOT.iterdir()
        if path.is_dir()
    }

    assert expected_directories <= actual_directories


def test_shared_task_files_are_valid_utf8_json_or_jsonl() -> None:
    """Every committed task file is parseable structured data."""

    task_files = sorted(
        path
        for path in DATASET_ROOT.rglob("*")
        if path.suffix in {".json", ".jsonl"}
    )

    assert task_files

    for task_file in task_files:
        content = task_file.read_text(encoding="utf-8")

        if task_file.suffix == ".json":
            payload = json.loads(content)
            assert isinstance(payload, list)
        else:
            for line in content.splitlines():
                if line.strip():
                    assert isinstance(json.loads(line), dict)
